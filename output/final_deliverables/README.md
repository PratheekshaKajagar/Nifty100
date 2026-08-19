# Nifty100 Financial Data Platform

End-to-end financial data engineering, screening, and analytics platform covering all 92 companies in the Nifty 100 universe.

Author: Jaya Nidhi

---

## Sprint 1 — Data Foundation
- Data ingestion from raw Excel sources (`data/raw/`)
- ETL pipeline (`src/etl/`): loading, normalisation, validation
- Data quality rules (14 unit tests, `tests/etl/test_validator.py`)
- SQLite database (`data/nifty100.db`)

## Sprint 3 — Screener & Peer Engine
- `src/screener/engine.py` — 15-metric filter engine, 6 preset screeners, composite quality score (35% Profitability / 30% Cash Quality / 20% Growth / 15% Leverage, P10/P90 winsorised, plus a sector-relative variant)
- `src/screener/report.py` — generates `output/screener_output.xlsx` (one sheet per preset, colour-coded)
- `src/analytics/peer.py` — peer percentile rankings across 11 peer groups / 10 metrics, written to the `peer_percentiles` table
- `src/analytics/peer_report.py` — generates `output/peer_comparison.xlsx` (11 sheets)
- `src/analytics/radar.py` — generates an 8-axis radar chart per company (`reports/radar_charts/`)

## Sprint 4 — Dashboard & Valuation Module

### Running the dashboard

```bash
pip install -r requirements.txt
streamlit run src/dashboard/app.py
```

The app opens at `http://localhost:8501`. The sidebar lists all 8 screens (Streamlit auto-discovers `src/dashboard/pages/`).

### Screens

| # | Screen | File | Description |
|---|--------|------|-------------|
| 1 | 🏠 Home | `pages/01_home.py` | 6 universe-level KPI tiles, sector donut chart, top-5 companies by composite score, year selector (2019–2024) |
| 2 | 🏢 Company Profile | `pages/02_profile.py` | Search/autocomplete, company card, 6 KPI tiles, 10yr Revenue & Net Profit bar chart, ROE/ROCE trend, pros & cons badges |
| 3 | 🔍 Screener | `pages/03_screener.py` | 10 sliders, 6 one-click presets, live-updating results table, CSV download |
| 4 | 🤝 Peer Comparison | `pages/04_peers.py` | Peer-group dropdown, radar chart (company vs. peer average), KPI table with benchmark row highlighted |
| 5 | 📈 Trend Analysis | `pages/05_trends.py` | Search + up-to-3-metric overlay, 10yr line chart with YoY% annotations |
| 6 | 🏭 Sector Analysis | `pages/06_sectors.py` | Revenue vs ROE bubble chart (size = market cap, colour = sub-sector), sector median KPI bar chart |
| 7 | 🗺️ Capital Allocation Map | `pages/07_capital.py` | Treemap of all companies across 8 capital-allocation patterns, click-through company list |
| 8 | 📄 Annual Reports | `pages/08_reports.py` | Search, clickable BSE filing links per year, live availability check (red badge if unreachable) |

### Data layer
- `src/dashboard/utils/db.py` — every query function is wrapped in `@st.cache_data(ttl=600)` so navigating between screens doesn't re-hit SQLite.

### Valuation module
- `src/analytics/valuation.py` — computes FCF yield (`FCF / market_cap × 100`), each company's own 5yr median P/E, and its sector's median P/E (latest year), then flags:
  - **Caution** if P/E > sector median × 1.5
  - **Discount** if P/E < sector median × 0.7
  - **Fair** otherwise
- Outputs: `output/valuation_summary.xlsx` (all 92 companies) and `output/valuation_flags.csv` (Caution/Discount only)

### QA notes (Sprint 4, Day 27)
- All 8 screens verified with `streamlit.testing.v1.AppTest` — no uncaught exceptions across a mix of IT, Financials, FMCG, Energy, and Healthcare tickers.
- Verified against a partial-history company (`JIOFIN`, 2 years of data only) — no crash; a "⚠️ Only N years of data available" note is shown wherever a 10-year chart has fewer than 10 points.
- Screener tested at both slider extremes (all-min and all-max) — no crash, table simply shows 0 or all rows.
- Company Profile load time measured at ~1.7–2.3s across 5 tickers (TCS, HDFCBANK, JIOFIN, ABB, NESTLEIND) — under the 3s target.
- Annual Reports screen degrades gracefully to "Availability not verified" if the sandbox/network can't reach BSE — it never crashes the page.

### Known limitations
- ROCE is only available in the source data as a single current-year figure (not a historical series per year), so the Company Profile ROE/ROCE chart shows ROCE as a flat reference line rather than a true trend — this is called out in-app with a caption.

## Sprint 6 — Clustering + REST API + QA + Sign-Off

### Running the API

```bash
pip install -r requirements.txt
uvicorn src.api.main:app --port 8000
```

Interactive docs (Swagger UI): `http://localhost:8000/docs`. Raw spec: `docs/openapi.json`. A ready-to-import Postman collection is at `docs/postman_collection.json`.

Both the dashboard (`:8501`) and the API (`:8000`) read `data/nifty100.db` directly and don't call each other over HTTP, so they can be started/stopped independently with no port conflicts.

### Clustering (Day 36–37)
- `src/analytics/clustering.py` — KMeans (k=5, `random_state=42`) on 5 features (ROE, D/E, revenue CAGR 5yr, FCF CAGR 5yr, OPM), sector-median imputation, `StandardScaler`. Outputs `output/cluster_labels.csv` and `reports/elbow_plot.png`.
- `src/analytics/cluster_profiling.py` — per-cluster feature profile (`output/cluster_profile.csv`), `reports/correlation_heatmap.png`, per-sector Z-score outlier detection (`output/outlier_report.csv`), and portfolio-wide percentile stats (`output/portfolio_stats.csv`).
- **Known gap:** ATGL and SBIN have zero rows in `financial_ratios` (an upstream KPI-computation issue from an earlier sprint, not something addressed here), so they're excluded from clustering — 90/92 companies have a cluster assignment. See `docs/acceptance_checklist.pdf`, gate AC-15.

### REST API (Day 38–40)
- `src/api/main.py` — FastAPI app, CORS (all origins, internal use), request-logging middleware, 9 routers mounted under `/api/v1`.
- 16+ GET endpoints across companies, screener, sectors, peers, valuation/market-cap, portfolio, documents, and health — see `docs/openapi.json` for the full, generated spec, or the Analyst Guide (Section 5) for example `curl` commands.
- `GET /api/v1/screener` supports the same ad-hoc filters as the dashboard sliders (`min_roe`, `max_de`, `min_fcf`, `sector`, `min_rev_cagr_5yr`, `min_pat_cagr_5yr`, `max_pe`); `GET /api/v1/screener/run?preset=...` runs a named preset instead.

### Tests (Day 41–42)
- `tests/etl/`, `tests/kpi/`, `tests/dq/` (14 data-quality rules, one test per rule), `tests/api/` (health, companies, screener, sectors), `tests/analytics/` — **123 tests, 0 failures**.
- Run everything: `PYTHONPATH=. python3 -m pytest tests/ -v`
- HTML report: `PYTHONPATH=. python3 -m pytest tests/ --html=reports/pytest_report.html --self-contained-html`

### Performance (Day 43)
- Added SQLite indexes on `year` and `(company_id, year)` for every large time-series table (see `db/schema.sql`).
- 10 concurrent `/api/v1/screener` calls complete in well under 1 second combined (target: 10s) — see `output/perf_notes.md` for the full write-up, including the one-time (~600ms) cold-start cost of scoring the screener universe.
- Company Profile screen data load: <10ms per ticker across 5 sampled sectors (target: 3s).

### Documentation & code quality (Day 44)
- `docs/analyst_guide.pdf` (10 pages) — screener usage, all 8 dashboard screens, tearsheet generation, API examples, troubleshooting, metric glossary, and a database-table appendix.
- Every public function across `src/` has a one-line docstring.
- `black src/ tests/` and `ruff check src/ tests/` both run clean (see `pyproject.toml` for the small set of documented, intentional lint exceptions — e.g. `sys.path.insert()` before imports in every test file).

### Sign-off (Day 45)
- `docs/acceptance_checklist.pdf` — all 20 acceptance gates (AC-01–AC-20) run for real against the live database/API/artifacts, plus a presence check for all 23 deliverables. **17/20 gates pass**; the 3 that don't (AC-04, AC-06, AC-15) are documented with their actual root cause rather than hidden.
- `output/validation_failures.csv` — output of the full 14-rule `DataValidator` run across every processed source table (`scripts/run_validation.py`), 7,263 findings with `company_id, field, issue, severity` columns.
- `output/final_deliverables/` — archived copy of all 23 (+1) sign-off deliverables.

### Regenerating Sprint 6 artifacts
```bash
export PYTHONPATH=.
python3 -m src.analytics.clustering          # cluster_labels.csv, elbow_plot.png
python3 -m src.analytics.cluster_profiling   # cluster_profile.csv, correlation_heatmap.png, outlier_report.csv, portfolio_stats.csv
python3 scripts/export_api_docs.py           # docs/openapi.json, docs/postman_collection.json
python3 scripts/run_validation.py            # output/validation_failures.csv
python3 scripts/generate_analyst_guide.py    # docs/analyst_guide.pdf
python3 scripts/run_acceptance_gates.py      # docs/acceptance_checklist.pdf (also archives deliverables when re-run)
python3 -m pytest tests/ --html=reports/pytest_report.html --self-contained-html
```
