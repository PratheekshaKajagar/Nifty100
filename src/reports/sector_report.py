"""
sector_report.py
-----------------
Day 34 - Sector-level PDF reports, built with ReportLab.

One PDF per broad_sector, saved to reports/sector/{sector_slug}_report.pdf.

Page 1: sector header, count of companies, median KPI tiles for the
        latest year (ROE, ROCE, OPM, D/E, Market Cap, PE), a market-cap
        bar chart of the sector's constituents.
Page(s) 2+: a wordwrap-safe table listing every company in the sector
        with 8 metrics each (ROE, ROCE, OPM, Net Profit Margin, D/E,
        Market Cap, PE, Dividend Yield), paginated so rows never
        overflow the page.

Note: the source data resolves to 10 distinct broad_sector values
(not 11 as originally scoped) - every one of the 92 companies maps
cleanly to one of these 10 sectors, so this module generates one PDF
per sector actually present in the data rather than fabricating an
11th category.
"""

import io
import re
import sqlite3
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas as pdfcanvas
from reportlab.platypus import Paragraph, Table, TableStyle

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SECTOR_DIR = PROJECT_ROOT / "reports" / "sector"

PAGE_W, PAGE_H = A4

NAVY = colors.HexColor("#1F4E78")
LIGHT_GREY = colors.HexColor("#F2F2F2")
ROW_ALT = colors.HexColor("#EAF1F8")

ROWS_PER_TABLE_PAGE = 30


# =====================================================================
# Data loading
# =====================================================================


def load_sector_data(db_path):
    """Return a single merged dataframe: one row per company with its
    latest-year financial ratios, market data, and sector label."""
    conn = sqlite3.connect(db_path)

    companies = pd.read_sql("SELECT company_id, company_name, roce_percentage FROM companies", conn)
    sectors = pd.read_sql("SELECT company_id, broad_sector FROM sectors", conn)

    fr_all = pd.read_sql(
        "SELECT company_id, year, net_profit_margin_pct, operating_profit_margin_pct, "
        "return_on_equity_pct, debt_to_equity FROM financial_ratios "
        "WHERE year IS NOT NULL",
        conn,
    )
    mc_all = pd.read_sql(
        "SELECT company_id, year, market_cap_crore, pe_ratio, dividend_yield_pct "
        "FROM market_cap WHERE year IS NOT NULL",
        conn,
    )
    conn.close()

    fr_latest = fr_all.sort_values("year").groupby("company_id", as_index=False).tail(1)
    mc_latest = mc_all.sort_values("year").groupby("company_id", as_index=False).tail(1)

    df = companies.merge(sectors, on="company_id", how="left")
    df = df.merge(fr_latest, on="company_id", how="left")
    df = df.merge(mc_latest, on="company_id", how="left", suffixes=("", "_mc"))
    return df


def slugify(sector_name):
    """Slugify."""
    return re.sub(r"[^A-Za-z0-9]+", "_", sector_name).strip("_")


# =====================================================================
# Chart
# =====================================================================


def chart_market_cap(sector_df):
    """Chart market cap."""
    data = sector_df.sort_values("market_cap_crore", ascending=False).dropna(
        subset=["market_cap_crore"]
    )
    fig, ax = plt.subplots(figsize=(6.6, 3.0))
    if not data.empty:
        ax.bar(data["company_id"], data["market_cap_crore"], color="#1F4E78")
        ax.set_xticks(range(len(data)))
        ax.set_xticklabels(data["company_id"], fontsize=6.5, rotation=60, ha="right")
        ax.set_ylabel("Market Cap (₹ Cr)", fontsize=8)
        ax.tick_params(axis="y", labelsize=7)
    ax.set_title("Market Capitalisation by Company", fontsize=9, fontweight="bold")
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


# =====================================================================
# PDF drawing helpers (shared visual language with tearsheet.py)
# =====================================================================


def _draw_header(c, title, subtitle):
    c.setFillColor(NAVY)
    c.rect(0, PAGE_H - 26 * mm, PAGE_W, 26 * mm, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(15 * mm, PAGE_H - 13 * mm, title)
    c.setFont("Helvetica", 11)
    c.drawString(15 * mm, PAGE_H - 20 * mm, subtitle)


def _draw_footer(c, text):
    c.setFont("Helvetica", 7)
    c.setFillColor(colors.HexColor("#888888"))
    c.drawString(15 * mm, 8 * mm, text)


def _draw_kpi_tiles(c, tiles, top_y):
    cols, rows = 3, 2
    margin = 15 * mm
    gap = 4 * mm
    tile_w = (PAGE_W - 2 * margin - (cols - 1) * gap) / cols
    tile_h = 16 * mm

    for idx, (label, value) in enumerate(tiles):
        row = idx // cols
        col = idx % cols
        x = margin + col * (tile_w + gap)
        y = top_y - row * (tile_h + gap) - tile_h

        c.setFillColor(LIGHT_GREY)
        c.roundRect(x, y, tile_w, tile_h, 3, fill=1, stroke=0)
        c.setFillColor(colors.HexColor("#555555"))
        c.setFont("Helvetica", 8)
        c.drawString(x + 4, y + tile_h - 11, label)
        c.setFillColor(NAVY)
        c.setFont("Helvetica-Bold", 13)
        c.drawString(x + 4, y + 5, value)

    return top_y - rows * (tile_h + gap)


def _fmt_pct(v):
    return f"{v:.1f}%" if pd.notna(v) else "N/A"


def _fmt_num(v, suffix=""):
    return f"{v:,.0f}{suffix}" if pd.notna(v) else "N/A"


def _fmt_ratio(v):
    return f"{v:.2f}" if pd.notna(v) else "N/A"


def compute_sector_medians(sector_df):
    """Compute sector medians."""
    return {
        "roe": sector_df["return_on_equity_pct"].median(skipna=True),
        "roce": sector_df["roce_percentage"].median(skipna=True),
        "opm": sector_df["operating_profit_margin_pct"].median(skipna=True),
        "de": sector_df["debt_to_equity"].median(skipna=True),
        "mcap": sector_df["market_cap_crore"].median(skipna=True),
        "pe": sector_df["pe_ratio"].median(skipna=True),
    }


# =====================================================================
# Table page(s): 8 metrics per company
# =====================================================================

TABLE_HEADERS = [
    "Company",
    "ROE %",
    "ROCE %",
    "OPM %",
    "NPM %",
    "D/E",
    "Mkt Cap (Cr)",
    "PE",
    "Div Yld %",
]
TABLE_COL_WIDTHS_MM = [40, 15, 15, 15, 15, 13, 26, 13, 18]


def _company_table_rows(sector_df):
    style_body = ParagraphStyle("body", fontName="Helvetica", fontSize=7.5, leading=9)
    rows = []
    for _, r in sector_df.sort_values("company_id").iterrows():
        name = (
            f"{r['company_name']} ({r['company_id']})"
            if pd.notna(r.get("company_name"))
            else r["company_id"]
        )
        rows.append(
            [
                Paragraph(name, style_body),
                _fmt_pct(r.get("return_on_equity_pct")),
                _fmt_pct(r.get("roce_percentage")),
                _fmt_pct(r.get("operating_profit_margin_pct")),
                _fmt_pct(r.get("net_profit_margin_pct")),
                _fmt_ratio(r.get("debt_to_equity")),
                _fmt_num(r.get("market_cap_crore")),
                _fmt_ratio(r.get("pe_ratio")),
                _fmt_pct(r.get("dividend_yield_pct")),
            ]
        )
    return rows


def _draw_company_table(c, rows_chunk, top_y):
    style_header = ParagraphStyle(
        "header",
        fontName="Helvetica-Bold",
        fontSize=7.5,
        textColor=colors.white,
        alignment=TA_CENTER,
    )
    header_row = [Paragraph(h, style_header) for h in TABLE_HEADERS]
    data = [header_row] + rows_chunk

    col_widths = [w * mm for w in TABLE_COL_WIDTHS_MM]
    table = Table(data, colWidths=col_widths, repeatRows=1)

    row_bg = []
    for i in range(1, len(data)):
        bg = ROW_ALT if i % 2 == 0 else colors.white
        row_bg.append(("BACKGROUND", (0, i), (-1, i), bg))

    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ALIGN", (1, 0), (-1, -1), "CENTER"),
                ("FONTSIZE", (0, 1), (-1, -1), 7.5),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CCCCCC")),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                *row_bg,
            ]
        )
    )

    w, h = table.wrapOn(c, PAGE_W - 30 * mm, top_y)
    table.drawOn(c, 15 * mm, top_y - h)
    return top_y - h


# =====================================================================
# Sector PDF assembly
# =====================================================================


def generate_sector_report(db_path, sector_name, all_df, output_path):
    """Generate sector report."""
    sector_df = all_df[all_df.broad_sector == sector_name].copy()

    c = pdfcanvas.Canvas(str(output_path), pagesize=A4)

    # --- Page 1: summary ---
    _draw_header(c, sector_name, f"{len(sector_df)} companies  |  Sector Summary (latest FY)")
    med = compute_sector_medians(sector_df)
    tiles = [
        ("Median ROE", _fmt_pct(med["roe"])),
        ("Median ROCE", _fmt_pct(med["roce"])),
        ("Median OPM", _fmt_pct(med["opm"])),
        ("Median D/E", _fmt_ratio(med["de"])),
        ("Median Market Cap", _fmt_num(med["mcap"], " Cr")),
        ("Median PE", _fmt_ratio(med["pe"])),
    ]
    after_tiles_y = _draw_kpi_tiles(c, tiles, top_y=PAGE_H - 30 * mm)

    chart = chart_market_cap(sector_df)
    _draw_image_h = 90 * mm
    c.drawImage(
        ImageReader(chart),
        15 * mm,
        after_tiles_y - _draw_image_h - 4 * mm,
        width=PAGE_W - 30 * mm,
        height=_draw_image_h,
        preserveAspectRatio=True,
        anchor="c",
    )

    _draw_footer(c, f"Nifty100 Data Foundation - {sector_name} Sector Report - Page 1")
    c.showPage()

    # --- Page(s) 2+: company table, paginated ---
    rows = _company_table_rows(sector_df)
    chunks = [
        rows[i : i + ROWS_PER_TABLE_PAGE] for i in range(0, len(rows), ROWS_PER_TABLE_PAGE)
    ] or [[]]

    for i, chunk in enumerate(chunks, start=1):
        _draw_header(c, sector_name, f"Constituent Companies ({i} of {len(chunks)})")
        _draw_company_table(c, chunk, top_y=PAGE_H - 34 * mm)
        _draw_footer(c, f"Nifty100 Data Foundation - {sector_name} Sector Report - Page {i + 1}")
        c.showPage()

    c.save()


def batch_generate_sector_reports(db_path, output_dir=None):
    """Batch generate sector reports."""
    output_dir = Path(output_dir) if output_dir else DEFAULT_SECTOR_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    all_df = load_sector_data(db_path)
    sectors = sorted(s for s in all_df.broad_sector.dropna().unique())

    generated = []
    for sector_name in sectors:
        out_path = output_dir / f"{slugify(sector_name)}_report.pdf"
        generate_sector_report(db_path, sector_name, all_df, out_path)
        generated.append((sector_name, out_path))

    return generated, output_dir


if __name__ == "__main__":
    generated, output_dir = batch_generate_sector_reports(PROJECT_ROOT / "data" / "nifty100.db")
    print(f"Generated {len(generated)} sector reports in {output_dir}")
    for sector_name, path in generated:
        print(f"  {sector_name} -> {path.name}")
