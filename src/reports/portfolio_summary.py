"""
portfolio_summary.py
---------------------
Day 35 - Portfolio summary PDF: one page per company, alphabetical by
ticker, saved to reports/portfolio/portfolio_summary.pdf.

Each page: company name, sector, top 6 KPIs (ROE, ROCE, OPM, Net Profit
Margin, D/E, EPS), each with a trend arrow comparing the latest fiscal
year to the prior one.

Trend-arrow logic: arrows are direction-of-value by default (up = value
rose, down = value fell, right = flat within 2%), EXCEPT for Debt/Equity,
where a lower value is the favourable outcome, so a fall in D/E is shown
as an "improved" up arrow and a rise is shown as a declined down arrow.
This keeps the arrow's meaning ("improved" vs "declined") consistent
with what the metric means for the business, per the sprint spec.
"""

import sqlite3
from pathlib import Path

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as pdfcanvas

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "reports" / "portfolio" / "portfolio_summary.pdf"

PAGE_W, PAGE_H = A4

NAVY = colors.HexColor("#1F4E78")
LIGHT_GREY = colors.HexColor("#F2F2F2")
GREEN = colors.HexColor("#1E7B34")
RED = colors.HexColor("#B00020")
GREY_FLAT = colors.HexColor("#8A8A8A")

FLAT_BAND_PCT = 2.0  # within +/-2% of prior value counts as "flat"

# metric_key -> (column, label, format, lower_is_better)
METRICS = [
    ("roe", "return_on_equity_pct", "ROE", "pct", False),
    ("roce", "roce_percentage", "ROCE", "pct", False),  # company-level snapshot (see note below)
    ("opm", "operating_profit_margin_pct", "OPM", "pct", False),
    ("npm", "net_profit_margin_pct", "Net Profit Margin", "pct", False),
    ("de", "debt_to_equity", "Debt / Equity", "ratio", True),
    ("eps", "earnings_per_share", "EPS", "num", False),
]


# =====================================================================
# Data loading
# =====================================================================


def load_portfolio_data(db_path):
    """Load portfolio data."""
    conn = sqlite3.connect(db_path)
    companies = pd.read_sql("SELECT company_id, company_name FROM companies", conn)
    sectors = pd.read_sql("SELECT company_id, broad_sector FROM sectors", conn)
    fr_all = pd.read_sql(
        "SELECT company_id, year, return_on_equity_pct, operating_profit_margin_pct, "
        "net_profit_margin_pct, debt_to_equity, earnings_per_share FROM financial_ratios "
        "WHERE year IS NOT NULL ORDER BY company_id, year",
        conn,
    )
    conn.close()

    companies = companies.merge(sectors, on="company_id", how="left")
    return companies, fr_all


def latest_two_years(fr_all, company_id):
    """Latest two years."""
    sub = fr_all[fr_all.company_id == company_id].sort_values("year")
    if sub.empty:
        return None, None
    latest = sub.iloc[-1]
    prior = sub.iloc[-2] if len(sub) >= 2 else None
    return latest, prior


# =====================================================================
# Trend arrow logic
# =====================================================================


def trend_arrow(latest_val, prior_val, lower_is_better):
    """Return ('up'|'down'|'flat'|'na', delta_pct)."""
    if latest_val is None or prior_val is None or pd.isna(latest_val) or pd.isna(prior_val):
        return "na", None
    if prior_val == 0:
        return "na", None

    delta_pct = (latest_val - prior_val) / abs(prior_val) * 100

    if abs(delta_pct) <= FLAT_BAND_PCT:
        return "flat", delta_pct

    rose = delta_pct > 0
    improved = (not lower_is_better and rose) or (lower_is_better and not rose)
    return ("up" if improved else "down"), delta_pct


def fmt_metric(value, kind):
    """Fmt metric."""
    if value is None or pd.isna(value):
        return "N/A"
    if kind == "pct":
        return f"{value:.1f}%"
    if kind == "ratio":
        return f"{value:.2f}"
    return f"{value:.2f}"


# =====================================================================
# PDF drawing
# =====================================================================


def _draw_header(c, company_name, company_id, sector):
    c.setFillColor(NAVY)
    c.rect(0, PAGE_H - 26 * mm, PAGE_W, 26 * mm, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(15 * mm, PAGE_H - 13 * mm, company_name.strip())
    c.setFont("Helvetica", 11)
    c.drawString(15 * mm, PAGE_H - 20 * mm, f"NSE: {company_id}   |   {sector or 'Unclassified'}")


def _draw_arrow_glyph(c, kind, cx, cy, size=3.2 * mm):
    if kind == "up":
        color = GREEN
    elif kind == "down":
        color = RED
    else:
        color = GREY_FLAT

    c.setFillColor(color)
    c.setStrokeColor(color)
    if kind == "up":
        c.setLineWidth(1.6)
        c.line(cx, cy - size / 2, cx, cy + size / 2)
        p = c.beginPath()
        p.moveTo(cx - size / 2.4, cy + size / 6)
        p.lineTo(cx, cy + size / 2)
        p.lineTo(cx + size / 2.4, cy + size / 6)
        c.drawPath(p, fill=0, stroke=1)
    elif kind == "down":
        c.setLineWidth(1.6)
        c.line(cx, cy - size / 2, cx, cy + size / 2)
        p = c.beginPath()
        p.moveTo(cx - size / 2.4, cy - size / 6)
        p.lineTo(cx, cy - size / 2)
        p.lineTo(cx + size / 2.4, cy - size / 6)
        c.drawPath(p, fill=0, stroke=1)
    elif kind == "flat":
        c.setLineWidth(1.6)
        c.line(cx - size / 2, cy, cx + size / 2, cy)
        p = c.beginPath()
        p.moveTo(cx + size / 2 - size / 3, cy + size / 4)
        p.lineTo(cx + size / 2, cy)
        p.lineTo(cx + size / 2 - size / 3, cy - size / 4)
        c.drawPath(p, fill=0, stroke=1)
    else:
        c.setFont("Helvetica", 8)
        c.setFillColor(GREY_FLAT)
        c.drawCentredString(cx, cy - 3, "-")


def _draw_kpi_tiles_with_trend(c, tile_data, top_y):
    """tile_data: list of (label, value_str, arrow_kind)."""
    cols, rows = 3, 2
    margin = 15 * mm
    gap = 4 * mm
    tile_w = (PAGE_W - 2 * margin - (cols - 1) * gap) / cols
    tile_h = 20 * mm

    for idx, (label, value, arrow_kind) in enumerate(tile_data):
        row = idx // cols
        col = idx % cols
        x = margin + col * (tile_w + gap)
        y = top_y - row * (tile_h + gap) - tile_h

        c.setFillColor(LIGHT_GREY)
        c.roundRect(x, y, tile_w, tile_h, 3, fill=1, stroke=0)
        c.setFillColor(colors.HexColor("#555555"))
        c.setFont("Helvetica", 8.5)
        c.drawString(x + 5, y + tile_h - 12, label)
        c.setFillColor(NAVY)
        c.setFont("Helvetica-Bold", 15)
        c.drawString(x + 5, y + 6, value)
        _draw_arrow_glyph(c, arrow_kind, x + tile_w - 10, y + tile_h / 2)

    return top_y - rows * (tile_h + gap)


def _draw_legend(c, y):
    x = 15 * mm
    c.setFont("Helvetica-Oblique", 7.5)
    c.setFillColor(colors.HexColor("#666666"))
    _draw_arrow_glyph(c, "up", x + 2 * mm, y, size=2.6 * mm)
    c.drawString(x + 6 * mm, y - 2.5, "Improved YoY")
    _draw_arrow_glyph(c, "down", x + 40 * mm, y, size=2.6 * mm)
    c.drawString(x + 44 * mm, y - 2.5, "Declined YoY")
    _draw_arrow_glyph(c, "flat", x + 78 * mm, y, size=2.6 * mm)
    c.drawString(x + 82 * mm, y - 2.5, f"Flat (within {FLAT_BAND_PCT:.0f}%)")
    c.drawString(x + 122 * mm, y - 2.5, "For Debt/Equity, a fall counts as improved.")


def draw_company_page(c, company_row, fr_all, roce_lookup):
    """Draw company page."""
    company_id = company_row["company_id"]
    company_name = company_row["company_name"] or company_id
    sector = company_row.get("broad_sector")

    _draw_header(c, company_name, company_id, sector)

    latest, prior = latest_two_years(fr_all, company_id)
    year_label = (
        f"FY{int(latest['year'])}" if latest is not None and pd.notna(latest["year"]) else "N/A"
    )

    c.setFont("Helvetica", 9)
    c.setFillColor(colors.HexColor("#666666"))
    c.drawString(15 * mm, PAGE_H - 32 * mm, f"Latest reported year: {year_label}  (vs. prior year)")

    tile_data = []
    for key, col, label, kind, lower_is_better in METRICS:
        if key == "roce":
            latest_val = roce_lookup.get(company_id)
            prior_val = None  # only a point-in-time snapshot is available for ROCE
        else:
            latest_val = latest[col] if latest is not None else None
            prior_val = prior[col] if prior is not None else None

        arrow_kind, _ = trend_arrow(latest_val, prior_val, lower_is_better)
        tile_data.append((label, fmt_metric(latest_val, kind), arrow_kind))

    after_tiles_y = _draw_kpi_tiles_with_trend(c, tile_data, top_y=PAGE_H - 40 * mm)
    _draw_legend(c, after_tiles_y - 6 * mm)

    c.setFont("Helvetica", 7)
    c.setFillColor(colors.HexColor("#888888"))
    c.drawString(15 * mm, 8 * mm, "Nifty100 Data Foundation - Portfolio Summary")


# =====================================================================
# Batch generation
# =====================================================================


def generate_portfolio_summary(db_path, output_path=None):
    """Generate portfolio summary."""
    output_path = Path(output_path) if output_path else DEFAULT_OUTPUT_PATH
    output_path.parent.mkdir(parents=True, exist_ok=True)

    companies, fr_all = load_portfolio_data(db_path)
    companies = companies.sort_values("company_id").reset_index(drop=True)

    conn = sqlite3.connect(db_path)
    roce_df = pd.read_sql("SELECT company_id, roce_percentage FROM companies", conn)
    conn.close()
    roce_lookup = dict(zip(roce_df.company_id, roce_df.roce_percentage))

    c = pdfcanvas.Canvas(str(output_path), pagesize=A4)
    for _, company_row in companies.iterrows():
        draw_company_page(c, company_row, fr_all, roce_lookup)
        c.showPage()
    c.save()

    return output_path, len(companies)


if __name__ == "__main__":
    output_path, n = generate_portfolio_summary(PROJECT_ROOT / "data" / "nifty100.db")
    print(f"Generated {n}-page portfolio summary -> {output_path}")
