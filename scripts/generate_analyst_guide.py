"""
scripts/generate_analyst_guide.py
-----------------------------------
Day 44 - builds docs/analyst_guide.pdf (10+ pages): how to use the
Streamlit screener, how to navigate each dashboard screen, how to
generate PDF tearsheets, how to call the API with example curl
commands, and troubleshooting common issues.

Run with:
    PYTHONPATH=. python3 scripts/generate_analyst_guide.py
"""

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
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
    ListFlowable,
    ListItem,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT_PATH = PROJECT_ROOT / "docs" / "analyst_guide.pdf"

styles = getSampleStyleSheet()
styles.add(
    ParagraphStyle(
        name="H1Custom",
        parent=styles["Heading1"],
        textColor=colors.HexColor("#1a3c5e"),
        spaceBefore=18,
        spaceAfter=10,
    )
)
styles.add(
    ParagraphStyle(
        name="H2Custom",
        parent=styles["Heading2"],
        textColor=colors.HexColor("#2b6ca3"),
        spaceBefore=14,
        spaceAfter=6,
    )
)
styles.add(
    ParagraphStyle(
        name="BodyCustom",
        parent=styles["BodyText"],
        alignment=TA_LEFT,
        leading=14,
        spaceAfter=8,
    )
)
styles.add(
    ParagraphStyle(
        name="CodeBlock",
        parent=styles["Code"],
        fontName="Courier",
        fontSize=8.5,
        leading=11,
        backColor=colors.HexColor("#f2f2f2"),
        borderPadding=6,
        spaceAfter=10,
    )
)
styles.add(
    ParagraphStyle(
        name="CoverTitle",
        parent=styles["Title"],
        fontSize=28,
        textColor=colors.HexColor("#1a3c5e"),
    )
)
styles.add(
    ParagraphStyle(
        name="CoverSub",
        parent=styles["Normal"],
        fontSize=14,
        textColor=colors.HexColor("#555555"),
        spaceBefore=10,
    )
)


def p(text, style="BodyCustom"):
    return Paragraph(text, styles[style])


def h1(text):
    return Paragraph(text, styles["H1Custom"])


def h2(text):
    return Paragraph(text, styles["H2Custom"])


def code(text):
    escaped = (
        text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )
    escaped = escaped.replace("\n", "<br/>")
    return Paragraph(escaped, styles["CodeBlock"])


def bullets(items):
    return ListFlowable(
        [ListItem(p(item)) for item in items],
        bulletType="bullet",
        leftIndent=18,
    )


def build():
    doc = SimpleDocTemplate(
        str(OUT_PATH),
        pagesize=letter,
        topMargin=0.9 * inch,
        bottomMargin=0.9 * inch,
        leftMargin=0.9 * inch,
        rightMargin=0.9 * inch,
        title="Nifty100 Data Foundation - Analyst Guide",
    )

    story = []

    # ---------------- Cover page ----------------
    story.append(Spacer(1, 2 * inch))
    story.append(Paragraph("Nifty100 Data Foundation", styles["CoverTitle"]))
    story.append(Paragraph("Analyst Guide", styles["CoverSub"]))
    story.append(Spacer(1, 0.3 * inch))
    story.append(
        p(
            "A practical guide to the Streamlit dashboard, PDF tearsheets, and "
            "REST API built on top of the Nifty 100 fundamentals data foundation. "
            "Covers 92 companies across 10 broad sectors, 2019-2024."
        )
    )
    story.append(Spacer(1, 1.5 * inch))
    story.append(p("Sprint 6 - Day 44 Documentation Deliverable", "CoverSub"))
    story.append(PageBreak())

    # ---------------- Table of contents ----------------
    story.append(h1("Table of Contents"))
    toc_items = [
        "1. Overview & Getting Started",
        "2. Using the Streamlit Screener",
        "3. Navigating Each Dashboard Screen",
        "   3.1 Home",
        "   3.2 Company Profile",
        "   3.3 Screener",
        "   3.4 Peer Comparison",
        "   3.5 Trend Analysis",
        "   3.6 Sector Analysis",
        "   3.7 Capital Allocation Map",
        "   3.8 Annual Reports",
        "4. Generating PDF Tearsheets",
        "5. Calling the REST API",
        "6. Troubleshooting Common Issues",
    ]
    story.append(bullets(toc_items))
    story.append(PageBreak())

    # ---------------- 1. Overview ----------------
    story.append(h1("1. Overview & Getting Started"))
    story.append(
        p(
            "The Nifty100 Data Foundation project loads fundamentals for 92 Nifty "
            "100-index companies (2019-2024) into a local SQLite database "
            "(<font face='Courier'>data/nifty100.db</font>), then layers three "
            "analyst-facing tools on top of it:"
        )
    )
    story.append(
        bullets(
            [
                "<b>Streamlit dashboard</b> (port 8501) - 8 interactive screens for "
                "browsing, screening, and comparing companies visually.",
                "<b>FastAPI REST API</b> (port 8000) - 16+ JSON endpoints for "
                "programmatic access, integrations, or scripting.",
                "<b>PDF tearsheets</b> - one-page-per-company summary reports, "
                "pre-generated for all 92 companies under "
                "<font face='Courier'>reports/tearsheets/</font>.",
            ]
        )
    )
    story.append(h2("Starting the dashboard"))
    story.append(code("streamlit run src/dashboard/app.py"))
    story.append(
        p("Opens automatically in your browser at http://localhost:8501.")
    )
    story.append(h2("Starting the API"))
    story.append(code("uvicorn src.api.main:app --port 8000"))
    story.append(
        p(
            "Interactive API docs (Swagger UI) are then available at "
            "http://localhost:8000/docs, and the raw OpenAPI schema at "
            "<font face='Courier'>docs/openapi.json</font>."
        )
    )
    story.append(
        p(
            "Both processes read the same SQLite file directly and don't talk to "
            "each other over HTTP, so they can be started, stopped, or restarted "
            "independently without port conflicts."
        )
    )

    # ---------------- 2. Screener ----------------
    story.append(h1("2. Using the Streamlit Screener"))
    story.append(
        p(
            "The Screener screen (<font face='Courier'>pages/03_screener.py</font>) "
            "is the fastest way to go from '92 companies' to 'the handful I actually "
            "want to look at'."
        )
    )
    story.append(h2("The 10 sliders"))
    story.append(
        bullets(
            [
                "ROE min - minimum return on equity (%)",
                "D/E max - maximum debt-to-equity ratio",
                "FCF min - minimum free cash flow (Cr)",
                "Revenue CAGR min - minimum 5-year revenue CAGR (%)",
                "PAT CAGR min - minimum 5-year profit CAGR (%)",
                "OPM min - minimum operating profit margin (%)",
                "P/E max - maximum price-to-earnings ratio",
                "P/B max - maximum price-to-book ratio",
                "Dividend Yield min - minimum dividend yield (%)",
                "ICR min - minimum interest coverage ratio",
            ]
        )
    )
    story.append(h2("The 6 presets"))
    story.append(
        p(
            "Click a preset button to auto-fill every slider at once, then fine-tune "
            "from there if you want:"
        )
    )
    story.append(
        bullets(
            [
                "<b>Quality</b> - high ROE, low leverage, consistent margins.",
                "<b>Value</b> - low P/E and P/B relative to fundamentals.",
                "<b>Growth</b> - high revenue and PAT CAGR.",
                "<b>Dividend</b> - high, sustainable dividend yield.",
                "<b>Debt-Free</b> - zero or near-zero debt-to-equity.",
                "<b>Turnaround</b> - improving trend on a previously weak metric "
                "(e.g. declining D/E year-over-year).",
            ]
        )
    )
    story.append(
        p(
            "The results table updates live as you move any slider, shows a "
            "'N companies match your filters' count above it, and every visible "
            "column can be exported with the <b>CSV download</b> button - useful "
            "for taking a shortlist into Excel or another tool."
        )
    )

    # ---------------- 3. Screens ----------------
    story.append(h1("3. Navigating Each Dashboard Screen"))

    story.append(h2("3.1 Home"))
    story.append(
        p(
            "Landing page. Shows 6 summary KPI tiles (average ROE, median P/E, "
            "median D/E, total companies, median 5yr revenue CAGR, debt-free "
            "company count), a sector breakdown donut chart, and a top-5 companies "
            "by composite quality score table. Use the year selector in the "
            "sidebar (2019-2024) to see how these headline numbers looked in past "
            "years."
        )
    )

    story.append(h2("3.2 Company Profile"))
    story.append(
        p(
            "Search any company by name or ticker (autocomplete as you type). "
            "Shows a company card (sector, sub-sector, NSE ticker, description), "
            "6 KPI tiles, a 10-year revenue/net-profit bar chart, a ROE/ROCE "
            "dual-axis line chart, and pros/cons as green-check / red-cross badges. "
            "An unknown ticker shows a friendly 'Ticker not found - please try "
            "another' message rather than an error."
        )
    )

    story.append(h2("3.3 Screener"))
    story.append(p("See Section 2 above for full detail on sliders and presets."))

    story.append(h2("3.4 Peer Comparison"))
    story.append(
        p(
            "Pick one of the 11 peer groups from the dropdown to see a radar chart "
            "(the selected company's 8 metrics vs. its peer group average) and a "
            "side-by-side KPI table for every company in that group, with the "
            "designated benchmark company's row highlighted."
        )
    )

    story.append(h2("3.5 Trend Analysis"))
    story.append(
        p(
            "Search a company, then choose up to 3 metrics to overlay on a "
            "10-year line chart, with YoY % change annotated at each data point - "
            "good for spotting inflection points (e.g. margin compression, a debt "
            "paydown, a growth re-acceleration)."
        )
    )

    story.append(h2("3.6 Sector Analysis"))
    story.append(
        p(
            "Pick a sector to see a bubble chart (X = revenue, Y = ROE, bubble "
            "size = market cap, colour = sub-sector) plus a sector median KPI bar "
            "chart underneath - a quick way to spot outliers within a sector."
        )
    )

    story.append(h2("3.7 Capital Allocation Map"))
    story.append(
        p(
            "A treemap of all 92 companies grouped into 8 capital allocation "
            "patterns (e.g. reinvestment-heavy, dividend-heavy, debt-reduction-"
            "focused). Click a pattern to see the list of companies in it."
        )
    )

    story.append(h2("3.8 Annual Reports"))
    story.append(
        p(
            "Search a company to see every year it has an annual report on file, "
            "with a clickable BSE PDF link. If a link is broken (returns a 404), "
            "it's shown with a red 'Report unavailable' badge instead of a dead "
            "link."
        )
    )
    story.append(PageBreak())

    # ---------------- 4. Tearsheets ----------------
    story.append(h1("4. Generating PDF Tearsheets"))
    story.append(
        p(
            "Every company has a pre-generated, one-page tearsheet PDF under "
            "<font face='Courier'>reports/tearsheets/{TICKER}_tearsheet.pdf</font> "
            "(92 files, each 30 KB+). To regenerate all of them from current data:"
        )
    )
    story.append(code("PYTHONPATH=. python3 -c \"\nfrom src.reports.tearsheet import batch_generate_tearsheets\nbatch_generate_tearsheets('data/nifty100.db')\n\""))
    story.append(
        p(
            "Each tearsheet includes revenue/profit history, ROE/ROCE trend, a "
            "balance-sheet snapshot, a cash-flow waterfall, and the same pros/cons "
            "shown on the Company Profile dashboard screen. You can also download "
            "a single company's tearsheet directly from the dashboard's Company "
            "Profile screen, or via the API (see below)."
        )
    )
    story.append(
        p(
            "Companies that were skipped during a batch run (missing minimum "
            "data) are logged to "
            "<font face='Courier'>output/skipped_tearsheets.csv</font> with a "
            "reason column, so nothing fails silently."
        )
    )

    # ---------------- 5. API ----------------
    story.append(h1("5. Calling the REST API"))
    story.append(
        p(
            "All endpoints are namespaced under "
            "<font face='Courier'>/api/v1</font>. Every route returns JSON. "
            "Full interactive docs live at "
            "<font face='Courier'>http://localhost:8000/docs</font> once the "
            "server is running."
        )
    )

    api_examples = [
        ("Health check", "curl http://localhost:8000/api/v1/health"),
        ("List all companies", "curl http://localhost:8000/api/v1/companies"),
        (
            "Search companies by name",
            'curl "http://localhost:8000/api/v1/companies?search=Tata"',
        ),
        (
            "Full company profile",
            "curl http://localhost:8000/api/v1/companies/TCS",
        ),
        (
            "P&L history for a date range",
            'curl "http://localhost:8000/api/v1/companies/TCS/pl?from_year=2020&to_year=2023"',
        ),
        (
            "Download a tearsheet PDF",
            "curl -o TCS_tearsheet.pdf "
            "http://localhost:8000/api/v1/companies/TCS/tearsheet",
        ),
        (
            "Run the ad-hoc screener",
            'curl "http://localhost:8000/api/v1/screener?min_roe=15&max_de=1&max_pe=40"',
        ),
        (
            "Run a named preset",
            'curl "http://localhost:8000/api/v1/screener/run?preset=Quality"',
        ),
        ("Sector medians", "curl http://localhost:8000/api/v1/sectors"),
        (
            "Companies in a sector",
            'curl "http://localhost:8000/api/v1/sectors/Information%20Technology/companies"',
        ),
        (
            "Peer group detail with percentile ranks",
            'curl "http://localhost:8000/api/v1/peers/IT%20Services"',
        ),
        (
            "Peer radar comparison for a company",
            "curl http://localhost:8000/api/v1/companies/TCS/peers/compare",
        ),
        (
            "Historical valuation multiples",
            "curl http://localhost:8000/api/v1/market-cap/TCS",
        ),
        (
            "Portfolio-wide percentile stats",
            "curl http://localhost:8000/api/v1/portfolio/stats",
        ),
        (
            "Annual report links for a company",
            "curl http://localhost:8000/api/v1/companies/TCS/documents",
        ),
    ]
    for label, cmd in api_examples:
        story.append(h2(label))
        story.append(code(cmd))

    story.append(
        p(
            "A ready-to-import Postman collection covering every GET endpoint "
            "(with example values pre-filled) is at "
            "<font face='Courier'>docs/postman_collection.json</font>."
        )
    )
    story.append(PageBreak())

    # ---------------- 6. Troubleshooting ----------------
    story.append(h1("6. Troubleshooting Common Issues"))

    trouble_rows = [
        ["Symptom", "Likely cause", "Fix"],
        [
            "Dashboard shows 'Ticker not found'",
            "Typo, or the ticker uses a different symbol than expected " "(e.g. 'M&M' vs 'MM').",
            "Use the autocomplete dropdown on the Company Profile screen " "instead of typing the full ticker.",
        ],
        [
            "API returns 404 for a company",
            "company_id is case-sensitive and must match exactly " "(tickers are stored upper-case).",
            "GET /api/v1/companies?search=... first to find the exact " "company_id.",
        ],
        [
            "Screener returns 0 matches",
            "Sliders/filters are set too strictly for the current data.",
            "Loosen one filter at a time, or start from a preset and " "adjust from there.",
        ],
        [
            "Chart overflows the page width",
            "Browser window narrower than the chart's fixed width.",
            "All dashboard charts use use_container_width=True; if one " "doesn't, that's a bug - flag it (see below).",
        ],
        [
            "'Address already in use' starting Streamlit or uvicorn",
            "A previous instance is still running on that port.",
            "Find and stop it (lsof -i :8501 or :8000), or start on a " "different port with --port.",
        ],
        [
            "Tearsheet download 404s",
            "Tearsheet PDF hasn't been generated for that company yet.",
            "Re-run batch_generate_tearsheets() (Section 4) and check " "output/skipped_tearsheets.csv for the reason.",
        ],
        [
            "CSV export from the screener looks garbled in Excel",
            "Excel misreads UTF-8 without a BOM for non-ASCII " "characters.",
            "Open the CSV via Excel's Data > From Text/CSV import " "instead of double-clicking it.",
        ],
        [
            "pytest fails with 'ModuleNotFoundError: src'",
            "Tests import from src.* but the project root isn't on " "PYTHONPATH.",
            "Run tests as PYTHONPATH=. python3 -m pytest tests/ from " "the project root.",
        ],
    ]
    table = Table(trouble_rows, colWidths=[1.6 * inch, 2.3 * inch, 2.3 * inch])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a3c5e")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [colors.white, colors.HexColor("#f5f7fa")],
                ),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(table)
    story.append(Spacer(1, 14))
    story.append(
        p(
            "For anything not covered here, check "
            "<font face='Courier'>output/perf_notes.md</font> for known "
            "performance characteristics, or "
            "<font face='Courier'>docs/acceptance_checklist.pdf</font> for the "
            "full list of verified acceptance gates and their current status."
        )
    )
    story.append(PageBreak())

    # ---------------- 7. Glossary ----------------
    story.append(h1("7. Glossary of Metrics"))
    story.append(
        p(
            "Quick reference for every KPI abbreviation used across the dashboard, "
            "tearsheets, and API responses."
        )
    )
    glossary_rows = [
        ["Term", "Meaning"],
        ["ROE", "Return on Equity - net profit / shareholder equity, as a %."],
        [
            "ROCE",
            "Return on Capital Employed - a broader profitability measure "
            "than ROE that also accounts for debt.",
        ],
        ["ROA", "Return on Assets - net profit / total assets, as a %."],
        [
            "D/E",
            "Debt-to-Equity ratio - total debt / shareholder equity. 0 means "
            "debt-free.",
        ],
        [
            "OPM",
            "Operating Profit Margin - operating profit / revenue, as a %.",
        ],
        [
            "FCF",
            "Free Cash Flow - cash from operations minus capital expenditure, "
            "in Rs. crore.",
        ],
        [
            "FCF Yield",
            "FCF / market capitalisation, as a % - how much free cash a "
            "company generates relative to its price.",
        ],
        [
            "CAGR",
            "Compound Annual Growth Rate - the smoothed annual growth rate "
            "over a multi-year period (e.g. Revenue CAGR 5yr).",
        ],
        [
            "ICR",
            "Interest Coverage Ratio - operating profit / interest expense. "
            "Undefined (shown as N/A) when a company has zero debt.",
        ],
        [
            "P/E",
            "Price-to-Earnings ratio - share price / earnings per share.",
        ],
        [
            "P/B",
            "Price-to-Book ratio - share price / book value per share.",
        ],
        [
            "EV/EBITDA",
            "Enterprise Value / EBITDA - a valuation multiple that, unlike "
            "P/E, is capital-structure neutral (accounts for debt and cash).",
        ],
        [
            "Composite Quality Score",
            "A single 0-100 score blending ROE, D/E, FCF, growth, and "
            "margin metrics, winsorized within each metric to reduce the "
            "influence of extreme outliers. Used to rank the screener and "
            "Home-screen 'top 5' table.",
        ],
        [
            "Overvaluation Flag",
            "Caution if P/E > 1.5x the company's sector median P/E; "
            "Discount if P/E < 0.7x the sector median; otherwise Fair.",
        ],
        [
            "Capital Allocation Pattern",
            "One of 8 archetypes (e.g. reinvestment-heavy, dividend-heavy) "
            "describing how a company has historically deployed free cash "
            "flow - see the Capital Allocation Map screen.",
        ],
    ]
    gtable = Table(glossary_rows, colWidths=[1.6 * inch, 4.6 * inch])
    gtable.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a3c5e")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [colors.white, colors.HexColor("#f5f7fa")],
                ),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(gtable)
    story.append(PageBreak())

    # ---------------- 8. Data appendix ----------------
    story.append(h1("8. Appendix: Database Tables"))
    story.append(
        p(
            "For analysts who want to query <font face='Courier'>data/nifty100.db"
            "</font> directly (e.g. with a SQLite browser, or pandas' "
            "<font face='Courier'>pd.read_sql</font>), here's what each table "
            "holds:"
        )
    )
    appendix_rows = [
        ["Table", "Contents"],
        ["companies", "One row per company - name, ticker, description, latest ROE/ROCE snapshot."],
        ["sectors", "broad_sector and sub_sector classification per company."],
        ["profitandloss", "Yearly P&L line items (2019-2024) per company."],
        ["balancesheet", "Yearly balance sheet line items per company."],
        ["cashflow", "Yearly cash flow statement line items per company."],
        ["financial_ratios", "Pre-computed KPIs per company per year (ROE, D/E, OPM, etc.)."],
        ["market_cap", "Yearly market cap and valuation multiples (P/E, P/B, EV/EBITDA)."],
        ["stock_prices", "Daily/periodic stock price history."],
        ["peer_groups", "Peer group membership (11 groups) and benchmark-company flag."],
        ["peer_percentiles", "Percentile rank per company, per peer group, per metric (10 metrics)."],
        ["prosandcons", "Auto-generated pros/cons text per company, with a confidence score."],
        ["documents", "Annual report links per company per year."],
    ]
    atable = Table(appendix_rows, colWidths=[1.6 * inch, 4.6 * inch])
    atable.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a3c5e")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, 1), (0, -1), "Courier"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [colors.white, colors.HexColor("#f5f7fa")],
                ),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(atable)
    story.append(Spacer(1, 12))
    story.append(
        p(
            "See <font face='Courier'>db/schema.sql</font> for full column-level "
            "definitions, primary/foreign keys, and indexes."
        )
    )

    doc.build(story)
    return OUT_PATH


if __name__ == "__main__":
    (PROJECT_ROOT / "docs").mkdir(exist_ok=True)
    out = build()
    print(f"Wrote {out}")
