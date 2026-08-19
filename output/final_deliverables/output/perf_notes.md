# Performance & Integration Testing Notes — Day 43

## 1. Screener API load test — 10 concurrent calls

Ran 10 concurrent `GET /api/v1/screener?min_roe=10` requests via Python
`threading` against an in-process `TestClient` (equivalent latency profile
to a local `uvicorn` server, since both go through the same FastAPI routing
+ SQLite/pandas path — no network hop either way on `localhost`).

| Metric | Result |
|---|---|
| Requests | 10 concurrent |
| All completed within | **0.065 s** total wall time |
| Slowest individual request | **0.061 s** |
| Target | all 10 complete within 10 s |
| Result | **PASS** — over 150x faster than the target |

**Why so fast:** the first request to `/screener` triggers `load_screener_data()`
(a handful of SQL joins + CAGR feature engineering over 92 companies) and
`calculate_composite_score()`, which together take ~550-600ms. That scored
DataFrame is cached in-process (`_SCREENER_CACHE`) for the lifetime of the
server, so every subsequent request — including the 10 concurrent ones in
this test — is just a `pandas` boolean-mask filter over an already-computed
92-row DataFrame, which is essentially free.

**Caveat:** the very first request after a cold server start pays the ~600ms
one-time cost. If the API is deployed behind a process manager that restarts
workers frequently, consider warming the cache on startup (an
`@app.on_event("startup")` hook calling `_get_scored_universe()` once) so the
first real user request isn't the one that pays for it.

## 2. Dashboard — Company Profile screen load time

Measured the data-loading path used by `pages/02_profile.py`
(`get_ratios`, `get_pl`, `get_bs`, `get_cf`, `get_pros_cons`, plus the
company lookup from `get_companies()`) for 5 tickers spanning different
sectors (IT, Energy, Financials, FMCG, Healthcare):

| Ticker | Sector | Load time |
|---|---|---|
| TCS | Information Technology | 0.0098 s |
| RELIANCE | Energy | 0.0080 s |
| HDFCBANK | Financials | 0.0079 s |
| ITC | Consumer Staples | 0.0077 s |
| SUNPHARMA | Healthcare | 0.0077 s |

**Target:** under 3 seconds each. **Result: PASS** — all 5 tickers loaded
in under 10 milliseconds, ~300x inside the budget. `@st.cache_data(ttl=600)`
on every query function in `src/dashboard/utils/db.py` means a *second*
navigation to the same ticker is served entirely from memory; even the
uncached first hit is fast because each query is a single indexed
`company_id` lookup against a small (≤1,500 row) table.

## 3. Port conflicts — Streamlit (8501) + FastAPI (8000) together

Both processes were started independently:

```
streamlit run src/dashboard/app.py   # binds :8501
uvicorn src.api.main:app --port 8000 # binds :8000
```

No port conflict — they bind different ports and share nothing but the
read-only SQLite file at `data/nifty100.db` (SQLite handles concurrent
readers natively; neither process writes to the DB at runtime). The
dashboard does **not** currently call the FastAPI server over HTTP — it
reads SQLite directly via `src/dashboard/utils/db.py` — so the two
processes are independent and one can be restarted without affecting the
other.

## 4. SQLite query optimisation

Added indexes on the `year` column (and composite `(company_id, year)`
indexes) for every large time-series table, since almost every API/dashboard
query filters by ticker and/or year range:

- `profitandloss`, `balancesheet`, `cashflow`, `financial_ratios`,
  `market_cap`: added `idx_*_year` and `idx_*_company_year`
- `stock_prices`: added `idx_stock_date` (5,520 rows, the largest table)
- `documents`: added `idx_docs_year`

Applied directly to `data/nifty100.db` and added to `db/schema.sql` so a
fresh rebuild (`make build-db` / `src/etl/load_to_sqlite.py`) picks them up
automatically. 23 indexes total now exist (up from 11).

## 5. Bottlenecks found

- The only measurable cost in the whole stack is the one-time
  `load_screener_data()` + `calculate_composite_score()` pass (~550-600ms)
  the first time `/api/v1/screener` (or any dashboard screen that reuses the
  same scored universe) is hit after a cold start. Not a bottleneck under
  load — it's paid once, not per-request — but worth a startup warm-up hook
  if response-time consistency on the very first request matters.
- No N+1 query patterns found in the API routers; all endpoints issue a
  single SQL statement (or, for `/sectors`, one aggregate query per sector —
  10 sectors, negligible).
- No chart-sizing or dashboard rendering bottlenecks were observed in this
  pass; all profiling here is on the data-loading path, which was the
  documented risk area for both the 3-second Company Profile gate (AC-08)
  and the 10-second concurrent-screener gate.
