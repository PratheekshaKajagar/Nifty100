.PHONY: load ratios screener peers valuation clustering nlp capital cashflow reports test lint dashboard api clean

# Nifty 100 Financial Intelligence Platform — pipeline entry points.
# See Section 21 (Environment Setup & Quick-Start Guide) and Section 27
# (Coding Standards) of the project spec for the full step-by-step guide.

PY := PYTHONPATH=. python3

## Rebuild the SQLite database from data/raw + data/processed (idempotent).
load:
	$(PY) src/etl/backfill_financial_ratios.py
	$(PY) src/etl/load_to_sqlite.py

## Populate the financial_ratios-derived analytics tables/outputs.
## Run after `make load`, or after any KPI formula change.
ratios: capital
	$(PY) src/analytics/valuation.py
	$(PY) src/analytics/peer.py

## Screener presets + peer comparison workbook (Sprint 3, Modules 3-4).
screener:
	$(PY) src/screener/report.py

peers:
	$(PY) src/analytics/radar.py
	$(PY) src/analytics/peer_report.py

## Capital allocation classification (Module 2, D-06) and Cash Flow
## Intelligence summary (Module 7, D-13).
capital:
	$(PY) src/analytics/capital_allocation.py
	$(PY) src/analytics/cashflow_intelligence.py

cashflow: capital

## KMeans clustering (Module 10) — cluster_labels.csv, elbow plot, profiles.
clustering:
	$(PY) src/analytics/clustering.py
	$(PY) src/analytics/cluster_profiling.py

## NLP / qualitative-analysis module (Module 9) — pros/cons, CAGR parser.
nlp:
	$(PY) src/nlp/pros_cons_generator.py
	$(PY) src/nlp/parser.py

## Generate all PDF reports: 92 tearsheets + 11 sector PDFs + portfolio summary.
reports:
	$(PY) src/reports/tearsheet.py
	$(PY) src/reports/sector_report.py
	$(PY) src/reports/portfolio_summary.py

## Run the full pytest suite with an HTML report (Module 12).
test:
	$(PY) -m pytest tests/ --html=reports/pytest_report.html --self-contained-html

## Format + lint (Section 27: black, then ruff).
lint:
	black src/ tests/
	ruff check src/ tests/

## Start the Streamlit dashboard on localhost:8501 (Module 5 / Sprint 4).
dashboard:
	streamlit run src/dashboard/app.py

## Start the FastAPI/Uvicorn REST API on localhost:8000 (Module 11 / Sprint 6).
api:
	uvicorn src.api.main:app --reload --port 8000

## Remove build/test artifacts. Does NOT touch data/nifty100.db or output/.
clean:
	find . -type d -name '__pycache__' -exec rm -rf {} +
	find . -type f -name '*.pyc' -delete
	rm -rf .pytest_cache .ruff_cache
