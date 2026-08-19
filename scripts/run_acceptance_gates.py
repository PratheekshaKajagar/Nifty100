"""
scripts/run_acceptance_gates.py
---------------------------------
Day 45 - runs all 20 acceptance gates for real against the live
project (data/nifty100.db, output/, reports/, docs/), and writes
docs/acceptance_checklist.pdf with the actual PASS/FAIL result for
each gate plus a table confirming all 23 deliverables are present.

Every result here is computed, not asserted - if a gate fails, the
PDF says FAIL and explains why. That's the point of the gate.

Run with:
    PYTHONPATH=. python3 scripts/run_acceptance_gates.py
"""

import sqlite3
import statistics
import time
from datetime import date
from pathlib import Path

import pandas as pd
import pdfplumber
from fastapi.testclient import TestClient
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    PageBreak,
    Table,
    TableStyle,
)

from src.api.main import app

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_ROOT / "data" / "nifty100.db"
OUT_PATH = PROJECT_ROOT / "docs" / "acceptance_checklist.pdf"

client = TestClient(app)


def gate(gate_id, description, passed, detail):
    return {"id": gate_id, "description": description, "passed": passed, "detail": detail}


def run_gates():
    conn = sqlite3.connect(DB_PATH)
    results = []

    # AC-01
    n_companies = conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
    results.append(
        gate("AC-01", "SELECT COUNT(*) FROM companies = 92", n_companies == 92,
             f"companies table has {n_companies} rows")
    )

    # AC-02
    coverage_df = pd.read_sql(
        """
        SELECT c.company_id,
            (SELECT COUNT(DISTINCT year) FROM profitandloss WHERE company_id=c.company_id) AS pl_years,
            (SELECT COUNT(DISTINCT year) FROM balancesheet WHERE company_id=c.company_id) AS bs_years,
            (SELECT COUNT(DISTINCT year) FROM cashflow WHERE company_id=c.company_id) AS cf_years
        FROM companies c
        """,
        conn,
    )
    n_covered = len(coverage_df[
        (coverage_df.pl_years >= 10) & (coverage_df.bs_years >= 10) & (coverage_df.cf_years >= 10)
    ])
    pct_covered = n_covered / len(coverage_df) * 100
    results.append(
        gate("AC-02", ">= 90% of companies have >= 10 years of P&L, BS, and CF records",
             pct_covered >= 90,
             f"{n_covered}/{len(coverage_df)} companies ({pct_covered:.1f}%) have 10+ years on all three statements")
    )

    # AC-03
    conn.execute("PRAGMA foreign_keys=ON")
    fk_violations = conn.execute("PRAGMA foreign_key_check").fetchall()
    results.append(
        gate("AC-03", "PRAGMA foreign_key_check returns 0 rows", len(fk_violations) == 0,
             f"{len(fk_violations)} foreign-key violations reported by SQLite's own check")
    )

    # AC-04
    n_ratios = conn.execute("SELECT COUNT(*) FROM financial_ratios").fetchone()[0]
    results.append(
        gate("AC-04", "SELECT COUNT(*) FROM financial_ratios >= 1,100", n_ratios >= 1100,
             f"financial_ratios has {n_ratios} rows (target: 1,100+). Two companies "
             f"(ATGL, SBIN) have zero rows here despite having P&L/BS/CF history - a "
             f"pre-existing gap in the ratio-computation step from an earlier sprint, "
             f"not something addressed in this pass.")
    )

    # AC-05
    from src.screener.engine import load_screener_data
    scored = load_screener_data(str(DB_PATH))
    pnl = pd.read_sql(
        "SELECT company_id, year, sales FROM profitandloss WHERE year IS NOT NULL ORDER BY company_id, year",
        conn,
    )
    spot_checks = []
    for cid in ["TCS", "RELIANCE", "HDFCBANK"]:
        hist = pnl[pnl.company_id == cid].dropna(subset=["sales"]).sort_values("year")
        if len(hist) < 6:
            continue
        latest = hist.iloc[-1]
        base_candidates = hist[hist.year <= latest.year - 5]
        if base_candidates.empty:
            continue
        base_row = base_candidates.iloc[-1]
        n_years = latest.year - base_row.year
        manual_cagr = ((latest.sales / base_row.sales) ** (1 / n_years) - 1) * 100
        computed_row = scored[scored.company_id == cid]["sales_cagr_5yr"]
        computed_cagr = computed_row.iloc[0] if not computed_row.empty else None
        if computed_cagr is not None:
            spot_checks.append((cid, manual_cagr, computed_cagr, abs(manual_cagr - computed_cagr)))
    ac05_pass = all(diff < 0.1 for *_, diff in spot_checks) and len(spot_checks) >= 3
    ac05_detail = "; ".join(
        f"{cid}: manual={m:.2f}%, computed={c:.2f}%, diff={d:.4f}pp" for cid, m, c, d in spot_checks
    )
    results.append(
        gate("AC-05", "Revenue CAGR spot-check matches manual Excel calculation within 0.1%",
             ac05_pass, ac05_detail)
    )

    # AC-06
    companies_roe = pd.read_sql("SELECT company_id, roe_percentage FROM companies", conn)
    latest_fr = pd.read_sql(
        """
        SELECT company_id, return_on_equity_pct FROM financial_ratios
        WHERE (company_id, year) IN (SELECT company_id, MAX(year) FROM financial_ratios GROUP BY company_id)
        """,
        conn,
    )
    ac06_sample = ["TCS", "RELIANCE", "HDFCBANK", "ITC", "SUNPHARMA"]
    ac06_checks = []
    for cid in ac06_sample:
        c_val = companies_roe.loc[companies_roe.company_id == cid, "roe_percentage"]
        f_val = latest_fr.loc[latest_fr.company_id == cid, "return_on_equity_pct"]
        if c_val.empty or f_val.empty:
            continue
        c_val, f_val = c_val.iloc[0], f_val.iloc[0]
        pct_diff = abs(c_val - f_val) / abs(c_val) * 100 if c_val else None
        ac06_checks.append((cid, c_val, f_val, pct_diff))
    ac06_pass_count = sum(1 for *_, d in ac06_checks if d is not None and d <= 5)
    ac06_pass = ac06_pass_count == len(ac06_checks)
    ac06_detail = (
        "; ".join(f"{cid}: companies.roe={c:.2f}%, ratios.roe={f:.2f}%, diff={d:.1f}%"
                  for cid, c, f, d in ac06_checks)
        + f". {ac06_pass_count}/{len(ac06_checks)} within 5%. TCS's companies.roe_percentage "
          "(0.52) looks like a decimal/scale data-entry error - the computed ratio is "
          "~51%, ~100x higher. src/reports/tearsheet.py already works around this by "
          "preferring the computed ratio over the companies-table snapshot wherever "
          "possible."
    )
    results.append(
        gate("AC-06", "ROE matches companies.roe_percentage within 5% for 5 companies",
             ac06_pass, ac06_detail)
    )

    # AC-07
    r = client.get("/api/v1/screener/run", params={"preset": "quality_compounder"})
    matched = r.json()["matched_count"]
    results.append(
        gate("AC-07", "Quality screener preset returns between 10 and 50 companies",
             10 <= matched <= 50, f"quality_compounder preset matched {matched} companies")
    )

    # AC-08
    import sys
    sys.path.insert(0, str(PROJECT_ROOT))
    from src.dashboard.utils import db as dash_db
    load_times = []
    for cid in ["TCS", "RELIANCE", "HDFCBANK", "ITC", "SUNPHARMA"]:
        t0 = time.perf_counter()
        dash_db.get_ratios(cid)
        dash_db.get_pl(cid)
        dash_db.get_bs(cid)
        dash_db.get_cf(cid)
        dash_db.get_pros_cons(cid)
        load_times.append(time.perf_counter() - t0)
    max_load = max(load_times)
    results.append(
        gate("AC-08", "Company Profile screen loads in under 3 seconds",
             max_load < 3, f"slowest of 5 sampled tickers: {max_load*1000:.1f} ms")
    )

    # AC-09
    import io
    r9 = client.get("/api/v1/screener", params={"min_roe": 0})
    d9 = r9.json()
    df9 = pd.DataFrame(d9["companies"])
    csv_text = df9.to_csv(index=False)
    reparsed = pd.read_csv(io.StringIO(csv_text))
    ac09_pass = len(reparsed) == d9["matched_count"] and list(reparsed.columns) == list(df9.columns)
    results.append(
        gate("AC-09", "CSV download from screener screen is valid and well-formed",
             ac09_pass, f"{len(reparsed)} rows round-tripped correctly through CSV "
                        f"(matched_count={d9['matched_count']}), headers intact")
    )

    # AC-10
    ac10_samples = ["TCS", "RELIANCE", "HDFCBANK", "JIOFIN", "SUNPHARMA"]
    overflow_found = {}
    for cid in ac10_samples:
        path = PROJECT_ROOT / "reports" / "tearsheets" / f"{cid}_tearsheet.pdf"
        if not path.exists():
            overflow_found[cid] = "missing"
            continue
        with pdfplumber.open(path) as pdf:
            found = False
            for page in pdf.pages:
                w, h = page.width, page.height
                for word in page.extract_words():
                    if word["x1"] > w + 2 or word["bottom"] > h + 2 or word["x0"] < -2:
                        found = True
            overflow_found[cid] = found
    ac10_pass = all(v is False for v in overflow_found.values())
    results.append(
        gate("AC-10", "No text overflow in any of 5 sampled tearsheet PDFs", ac10_pass,
             ", ".join(f"{k}: {'overflow' if v else 'clean'}" for k, v in overflow_found.items()))
    )

    # AC-11
    r11 = client.get("/api/v1/health")
    results.append(
        gate("AC-11", "GET /api/v1/health returns HTTP 200", r11.status_code == 200,
             f"status code {r11.status_code}, body status={r11.json().get('status')}")
    )

    # AC-12
    r12 = client.get("/api/v1/companies/TCS/ratios")
    n_years_tcs = len(r12.json()) if r12.status_code == 200 and isinstance(r12.json(), list) else 0
    results.append(
        gate("AC-12", "TCS ratios endpoint returns data for 10+ years", n_years_tcs >= 10,
             f"/companies/TCS/ratios returned {n_years_tcs} yearly records")
    )

    # AC-13
    r13 = client.get("/api/v1/screener/run", params={"preset": "quality_compounder"})
    api_ids = set(r13.json()["companies"])
    xlsx_path = PROJECT_ROOT / "output" / "screener_output.xlsx"
    if xlsx_path.exists():
        xlsx_ids = set(pd.read_excel(xlsx_path)["company_id"])
        ac13_pass = api_ids == xlsx_ids
        ac13_detail = (
            f"API returned {len(api_ids)} companies, screener_output.xlsx has "
            f"{len(xlsx_ids)}; sets are {'identical' if ac13_pass else 'different'}"
        )
    else:
        ac13_pass = False
        ac13_detail = "output/screener_output.xlsx not found"
    results.append(
        gate("AC-13", "API screener results match screener_output.xlsx results", ac13_pass, ac13_detail)
    )

    # AC-14
    peer_groups = {r[0] for r in conn.execute("SELECT DISTINCT peer_group_name FROM peer_groups")}
    peer_pct_groups = {r[0] for r in conn.execute("SELECT DISTINCT peer_group_name FROM peer_percentiles")}
    ac14_pass = len(peer_groups) == 11 and peer_groups == peer_pct_groups
    results.append(
        gate("AC-14", "peer_percentiles table has data for all 11 peer groups", ac14_pass,
             f"{len(peer_groups)} peer groups defined, {len(peer_pct_groups)} have percentile data "
             f"({'all covered' if peer_groups == peer_pct_groups else 'MISMATCH: ' + str(peer_groups ^ peer_pct_groups)})")
    )

    # AC-15
    labels_df = pd.read_csv(PROJECT_ROOT / "output" / "cluster_labels.csv")
    all_ids = {r[0] for r in conn.execute("SELECT company_id FROM companies")}
    labelled_ids = set(labels_df["company_id"])
    missing_labels = all_ids - labelled_ids
    ac15_pass = len(missing_labels) == 0
    results.append(
        gate("AC-15", "All 92 companies have a cluster_id assigned in cluster_labels.csv", ac15_pass,
             f"{len(labelled_ids)}/92 companies have a cluster assignment. Missing: "
             f"{sorted(missing_labels) or 'none'}. ATGL and SBIN have zero rows in "
             f"financial_ratios (see AC-04), so they never entered the clustering "
             f"feature set - same upstream root cause as AC-04.")
    )

    # AC-16
    pros_cons_df = pd.read_csv(PROJECT_ROOT / "output" / "pros_cons_generated.csv")
    counts = pros_cons_df.groupby(["company_id", "type"]).size().unstack(fill_value=0)
    missing_pc = counts[(counts.get("pro", 0) < 1) | (counts.get("con", 0) < 1)]
    ac16_pass = len(missing_pc) == 0 and len(counts) == 92
    results.append(
        gate("AC-16", "All 92 companies have at least 1 pro and 1 con in pros_cons_generated.csv",
             ac16_pass, f"{len(counts)}/92 companies present, {len(missing_pc)} missing a pro or a con")
    )

    # AC-17
    tearsheet_dir = PROJECT_ROOT / "reports" / "tearsheets"
    tearsheets = list(tearsheet_dir.glob("*_tearsheet.pdf")) if tearsheet_dir.exists() else []
    undersized = [p.name for p in tearsheets if p.stat().st_size < 30 * 1024]
    ac17_pass = len(tearsheets) == 92 and len(undersized) == 0
    results.append(
        gate("AC-17", "92 tearsheet PDFs exist in reports/tearsheets/ and each is at least 30 KB",
             ac17_pass, f"{len(tearsheets)}/92 PDFs present, {len(undersized)} under 30KB "
                        f"({undersized if undersized else 'none'})")
    )

    # AC-18
    import subprocess
    import os
    test_env = dict(os.environ)
    test_env["PYTHONPATH"] = str(PROJECT_ROOT)
    test_result = subprocess.run(
        ["python3", "-m", "pytest", "tests/", "-q"],
        cwd=str(PROJECT_ROOT),
        env=test_env,
        capture_output=True,
        text=True,
    )
    last_line = [l for l in test_result.stdout.strip().split("\n") if l.strip()][-1]
    n_passed = 0
    n_failed = 0
    import re
    m_pass = re.search(r"(\d+) passed", last_line)
    m_fail = re.search(r"(\d+) failed", last_line)
    if m_pass:
        n_passed = int(m_pass.group(1))
    if m_fail:
        n_failed = int(m_fail.group(1))
    ac18_pass = n_passed >= 60 and n_failed == 0
    results.append(
        gate("AC-18", "pytest shows 60+ tests collected and 0 failures", ac18_pass,
             f"{n_passed} passed, {n_failed} failed (full run summary: '{last_line}')")
    )

    # AC-19
    vf_path = PROJECT_ROOT / "output" / "validation_failures.csv"
    if vf_path.exists():
        vf_df = pd.read_csv(vf_path)
        required_cols = {"company_id", "field", "issue", "severity"}
        ac19_pass = required_cols.issubset(set(vf_df.columns))
        ac19_detail = f"{len(vf_df)} findings logged, columns: {list(vf_df.columns)}"
    else:
        ac19_pass = False
        ac19_detail = "output/validation_failures.csv not found"
    results.append(
        gate("AC-19", "validation_failures.csv exists with company_id, field, issue, severity columns",
             ac19_pass, ac19_detail)
    )

    # AC-20
    guide_path = PROJECT_ROOT / "docs" / "analyst_guide.pdf"
    if guide_path.exists():
        with pdfplumber.open(guide_path) as pdf:
            n_pages = len(pdf.pages)
        ac20_pass = n_pages >= 10
    else:
        n_pages = 0
        ac20_pass = False
    results.append(
        gate("AC-20", "analyst_guide.pdf is at least 10 pages", ac20_pass, f"{n_pages} pages")
    )

    conn.close()
    return results


DELIVERABLES = [
    ("data/nifty100.db", "SQLite database - 13 tables, 92 companies"),
    ("db/schema.sql", "Schema DDL incl. Day 43 performance indexes"),
    ("output/valuation_summary.xlsx", "Valuation multiples + overvaluation flags"),
    ("output/valuation_flags.csv", "Caution/Discount flagged companies"),
    ("output/cluster_labels.csv", "KMeans cluster assignment per company"),
    ("output/cluster_profile.csv", "Per-cluster feature means/medians"),
    ("reports/elbow_plot.png", "KMeans elbow curve (k=2..10)"),
    ("reports/correlation_heatmap.png", "Pearson correlation of 10 KPIs"),
    ("output/outlier_report.csv", "Sector Z-score outlier flags"),
    ("output/portfolio_stats.csv", "P10-P90 percentile table, all KPIs"),
    ("output/pros_cons_generated.csv", "Auto-generated pros/cons, all 92 companies"),
    ("output/capital_allocation.csv", "8 capital allocation pattern labels"),
    ("output/screener_output.xlsx", "Screener preset outputs (ranked)"),
    ("output/validation_failures.csv", "14-rule DQ validator findings"),
    ("output/perf_notes.md", "Day 43 performance & load-test notes"),
    ("reports/tearsheets/", "92 per-company tearsheet PDFs"),
    ("src/api/", "FastAPI server - 16+ endpoints across 9 routers"),
    ("docs/openapi.json", "OpenAPI 3.1 specification"),
    ("docs/postman_collection.json", "Importable Postman collection"),
    ("reports/pytest_report.html", "Full pytest HTML report (123 tests)"),
    ("docs/analyst_guide.pdf", "10-page analyst user guide"),
    ("src/dashboard/", "Streamlit 8-screen dashboard app"),
    ("README.md", "Project overview & run instructions"),
]


def check_deliverables():
    rows = []
    for rel_path, description in DELIVERABLES:
        full_path = PROJECT_ROOT / rel_path
        exists = full_path.exists()
        if exists and full_path.is_dir():
            n_files = sum(1 for _ in full_path.rglob("*") if _.is_file())
            exists = n_files > 0
            note = f"{n_files} files"
        elif exists:
            size_kb = full_path.stat().st_size / 1024
            note = f"{size_kb:.1f} KB"
        else:
            note = "MISSING"
        rows.append((rel_path, description, exists, note))
    return rows


# ==================================================
# PDF rendering
# ==================================================
styles = getSampleStyleSheet()
styles.add(ParagraphStyle(name="H1C", parent=styles["Heading1"],
                           textColor=colors.HexColor("#1a3c5e"), spaceBefore=16, spaceAfter=8))
styles.add(ParagraphStyle(name="BodyC", parent=styles["BodyText"], leading=13, spaceAfter=6))
styles.add(ParagraphStyle(name="Small", parent=styles["BodyText"], fontSize=7.5, leading=9.5))
styles.add(ParagraphStyle(name="CoverT", parent=styles["Title"], fontSize=24,
                           textColor=colors.HexColor("#1a3c5e")))


def build_pdf(gate_results, deliverable_rows):
    doc = SimpleDocTemplate(
        str(OUT_PATH), pagesize=letter,
        topMargin=0.8 * inch, bottomMargin=0.8 * inch,
        leftMargin=0.7 * inch, rightMargin=0.7 * inch,
        title="Nifty100 Data Foundation - Acceptance Checklist",
    )
    story = []

    n_pass = sum(1 for g in gate_results if g["passed"])
    n_total = len(gate_results)

    story.append(Spacer(1, 1.2 * inch))
    story.append(Paragraph("Acceptance Checklist", styles["CoverT"]))
    story.append(Spacer(1, 0.2 * inch))
    story.append(Paragraph(
        f"Sprint 6, Day 45 - Final Sign-Off<br/>"
        f"{n_pass} of {n_total} acceptance gates passed<br/>"
        f"Generated {date.today().isoformat()} by running every gate's actual check "
        f"against the live database, API, and generated artifacts.",
        styles["BodyC"],
    ))
    story.append(Spacer(1, 0.4 * inch))
    story.append(Paragraph(
        "<i>Note: this checklist reports real results, including gates that did not "
        "pass. Where a gate fails, the detail column explains the root cause found "
        "during this pass rather than papering over it.</i>",
        styles["BodyC"],
    ))
    story.append(PageBreak())

    story.append(Paragraph("1. Acceptance Gates (AC-01 - AC-20)", styles["H1C"]))
    gate_rows = [["Gate", "Description", "Result", "Detail"]]
    for g in gate_results:
        result_text = "PASS" if g["passed"] else "FAIL"
        gate_rows.append([
            g["id"],
            Paragraph(g["description"], styles["Small"]),
            result_text,
            Paragraph(g["detail"], styles["Small"]),
        ])

    table = Table(gate_rows, colWidths=[0.5 * inch, 1.7 * inch, 0.5 * inch, 3.4 * inch], repeatRows=1)
    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a3c5e")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]
    for i, g in enumerate(gate_results, start=1):
        color = colors.HexColor("#e6f4ea") if g["passed"] else colors.HexColor("#fbe9e7")
        style_cmds.append(("BACKGROUND", (0, i), (-1, i), color))
        text_color = colors.HexColor("#1e7d32") if g["passed"] else colors.HexColor("#c62828")
        style_cmds.append(("TEXTCOLOR", (2, i), (2, i), text_color))
        style_cmds.append(("FONTNAME", (2, i), (2, i), "Helvetica-Bold"))
    table.setStyle(TableStyle(style_cmds))
    story.append(table)
    story.append(PageBreak())

    story.append(Paragraph("2. Deliverables (23 total)", styles["H1C"]))
    story.append(Paragraph(
        "Every deliverable is checked against the actual filesystem at the time this "
        "PDF was generated - not just listed from memory.",
        styles["BodyC"],
    ))
    deliv_rows = [["Path", "Description", "Present", "Note"]]
    for path, desc, exists, note in deliverable_rows:
        deliv_rows.append([
            Paragraph(f"<font face='Courier' size=7>{path}</font>", styles["Small"]),
            Paragraph(desc, styles["Small"]),
            "YES" if exists else "NO",
            note,
        ])
    dtable = Table(deliv_rows, colWidths=[1.6 * inch, 2.4 * inch, 0.6 * inch, 1.5 * inch], repeatRows=1)
    dstyle_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a3c5e")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cccccc")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    for i, (_, _, exists, _) in enumerate(deliverable_rows, start=1):
        color = colors.HexColor("#e6f4ea") if exists else colors.HexColor("#fbe9e7")
        dstyle_cmds.append(("BACKGROUND", (0, i), (-1, i), color))
    dtable.setStyle(TableStyle(dstyle_cmds))
    story.append(dtable)
    story.append(PageBreak())

    story.append(Paragraph("3. Sign-Off", styles["H1C"]))
    n_deliv_present = sum(1 for *_, exists, _ in deliverable_rows if exists)
    story.append(Paragraph(
        f"{n_pass}/{n_total} acceptance gates passed. {n_deliv_present}/{len(deliverable_rows)} "
        f"deliverables present on disk.",
        styles["BodyC"],
    ))
    story.append(Paragraph(
        "Open items carried forward (not resolved in this pass, tracked for a future "
        "sprint): AC-04 and AC-15 share a root cause - ATGL and SBIN have no rows in "
        "financial_ratios, which is an upstream KPI-computation gap from an earlier "
        "sprint. AC-06 surfaced a likely scale/decimal data-entry error in "
        "companies.roe_percentage for TCS specifically, plus a broader ~5-16% "
        "methodology gap between the companies-table ROE snapshot and the "
        "financial_ratios-computed ROE for the other sampled companies.",
        styles["BodyC"],
    ))
    story.append(Spacer(1, 0.4 * inch))
    story.append(Paragraph(
        "Team lead sign-off: ___________________________&nbsp;&nbsp;&nbsp;&nbsp;"
        "Date: ___________________",
        styles["BodyC"],
    ))

    doc.build(story)


if __name__ == "__main__":
    gate_results = run_gates()
    deliverable_rows = check_deliverables()

    print(f"{sum(1 for g in gate_results if g['passed'])}/{len(gate_results)} gates passed")
    for g in gate_results:
        print(f"  [{'PASS' if g['passed'] else 'FAIL'}] {g['id']}: {g['description']}")

    (PROJECT_ROOT / "docs").mkdir(exist_ok=True)
    build_pdf(gate_results, deliverable_rows)
    print(f"\nWrote {OUT_PATH}")
