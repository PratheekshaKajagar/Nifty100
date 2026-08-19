"""
tearsheet.py
------------
Day 33-34 - 2-page company tearsheet PDF, built with ReportLab.

Page 1: navy header, 6 KPI tiles (2x3), 10yr Revenue/Net Profit grouped
        bar chart, ROE/ROCE dual-axis line chart.
Page 2: Balance sheet composition stacked bar, Cash Flow waterfall,
        Pros (green) / Cons (red) bullet sections with wordwrap,
        Capital Allocation badge.

Batch generation writes one PDF per company to
reports/tearsheets/{company_id}_tearsheet.pdf, skipping companies with
fewer than 2 years of P&L history (logged to output/skipped_tearsheets.csv).
"""

import io
import sqlite3
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as pdfcanvas
from reportlab.platypus import Frame, Paragraph

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TEARSHEET_DIR = PROJECT_ROOT / "reports" / "tearsheets"
DEFAULT_SKIPPED_PATH = PROJECT_ROOT / "output" / "skipped_tearsheets.csv"

PAGE_W, PAGE_H = A4  # 595.27, 841.89

NAVY = colors.HexColor("#1F4E78")
LIGHT_GREY = colors.HexColor("#F2F2F2")
GREEN = colors.HexColor("#1E7B34")
RED = colors.HexColor("#B00020")
GOLD = colors.HexColor("#B8860B")

MIN_PNL_YEARS = 2


# =====================================================================
# Data loading
# =====================================================================


def load_company_data(db_path, company_id):
    """Load company data."""
    conn = sqlite3.connect(db_path)

    company = pd.read_sql(
        "SELECT company_id, company_name, roce_percentage, roe_percentage "
        "FROM companies WHERE company_id = ?",
        conn,
        params=(company_id,),
    )
    sector = pd.read_sql(
        "SELECT broad_sector FROM sectors WHERE company_id = ?", conn, params=(company_id,)
    )
    pnl = pd.read_sql(
        "SELECT year, sales, operating_profit, opm_percentage, net_profit, "
        "depreciation, eps FROM profitandloss WHERE company_id = ? AND year IS NOT NULL "
        "ORDER BY year",
        conn,
        params=(company_id,),
    )
    bs = pd.read_sql(
        "SELECT year, equity_capital, reserves, borrowings, other_liabilities, "
        "total_assets FROM balancesheet WHERE company_id = ? AND year IS NOT NULL "
        "ORDER BY year",
        conn,
        params=(company_id,),
    )
    cf = pd.read_sql(
        "SELECT year, operating_activity, investing_activity, financing_activity, "
        "net_cash_flow FROM cashflow WHERE company_id = ? AND year IS NOT NULL "
        "ORDER BY year",
        conn,
        params=(company_id,),
    )
    fr = pd.read_sql(
        "SELECT year, return_on_equity_pct, debt_to_equity, free_cash_flow_cr "
        "FROM financial_ratios WHERE company_id = ? AND year IS NOT NULL "
        "ORDER BY year",
        conn,
        params=(company_id,),
    )
    mc = pd.read_sql(
        "SELECT year, market_cap_crore, pe_ratio FROM market_cap "
        "WHERE company_id = ? AND year IS NOT NULL ORDER BY year",
        conn,
        params=(company_id,),
    )

    conn.close()

    return {
        "company": company,
        "sector": sector["broad_sector"].iloc[0] if not sector.empty else None,
        "pnl": pnl,
        "bs": bs,
        "cf": cf,
        "fr": fr,
        "mc": mc,
    }


def load_pros_cons(company_id, pros_cons_df):
    """Load pros cons."""
    sub = pros_cons_df[pros_cons_df.company_id == company_id]
    pros = sub[sub.type == "pro"]["text"].tolist()
    cons = sub[sub.type == "con"]["text"].tolist()
    return pros, cons


def load_capital_allocation_label(company_id, cashflow_intel_df):
    """Load capital allocation label."""
    row = cashflow_intel_df[cashflow_intel_df.company_id == company_id]
    if row.empty:
        return "Unknown"
    return row["capital_allocation_label"].iloc[0]


# =====================================================================
# Chart builders (matplotlib -> PNG bytes)
# =====================================================================


def _fig_to_reader(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


def chart_revenue_profit(pnl):
    """Chart revenue profit."""
    data = pnl.tail(10)
    fig, ax = plt.subplots(figsize=(6.6, 2.6))
    if not data.empty:
        years = data["year"].astype(int).astype(str)
        x = range(len(years))
        width = 0.38
        ax.bar([i - width / 2 for i in x], data["sales"], width, label="Revenue", color="#1F4E78")
        ax.bar(
            [i + width / 2 for i in x],
            data["net_profit"],
            width,
            label="Net Profit",
            color="#5B9BD5",
        )
        ax.set_xticks(list(x))
        ax.set_xticklabels(years, fontsize=7, rotation=45)
        ax.set_ylabel("₹ Cr", fontsize=8)
        ax.legend(fontsize=7, loc="upper left")
        ax.tick_params(axis="y", labelsize=7)
    ax.set_title("Revenue vs Net Profit (10yr)", fontsize=9, fontweight="bold")
    fig.tight_layout()
    return _fig_to_reader(fig)


def chart_roe_roce(pnl, bs):
    """Chart roe roce."""
    merged = pnl.merge(bs, on="year", how="inner").tail(10)
    fig, ax1 = plt.subplots(figsize=(6.6, 2.6))
    if not merged.empty:
        years = merged["year"].astype(int).astype(str)
        equity = merged["equity_capital"] + merged["reserves"]
        roe_series = (merged["net_profit"] / equity.replace(0, pd.NA)) * 100
        ebit = merged["operating_profit"] - merged["depreciation"].fillna(0)
        capital = merged["equity_capital"] + merged["reserves"] + merged["borrowings"]
        roce_series = (ebit / capital.replace(0, pd.NA)) * 100

        ax1.plot(years, roe_series, marker="o", color="#1F4E78", label="ROE %")
        ax1.set_ylabel("ROE %", fontsize=8, color="#1F4E78")
        ax1.tick_params(axis="y", labelsize=7, labelcolor="#1F4E78")
        ax1.tick_params(axis="x", labelsize=7, rotation=45)

        ax2 = ax1.twinx()
        ax2.plot(years, roce_series, marker="s", color="#C55A11", label="ROCE %")
        ax2.set_ylabel("ROCE %", fontsize=8, color="#C55A11")
        ax2.tick_params(axis="y", labelsize=7, labelcolor="#C55A11")

        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax1.legend(lines1 + lines2, labels1 + labels2, fontsize=7, loc="upper left")

    ax1.set_title("ROE vs ROCE (dual axis)", fontsize=9, fontweight="bold")
    fig.tight_layout()
    return _fig_to_reader(fig)


def chart_balance_sheet(bs):
    """Chart balance sheet."""
    data = bs.tail(10)
    fig, ax = plt.subplots(figsize=(6.6, 2.6))
    if not data.empty:
        years = data["year"].astype(int).astype(str)
        ax.bar(years, data["equity_capital"] + data["reserves"], label="Equity", color="#1F4E78")
        ax.bar(
            years,
            data["borrowings"],
            bottom=data["equity_capital"] + data["reserves"],
            label="Borrowings",
            color="#C55A11",
        )
        bottom2 = data["equity_capital"] + data["reserves"] + data["borrowings"]
        ax.bar(
            years,
            data["other_liabilities"],
            bottom=bottom2,
            label="Other Liabilities",
            color="#A9A9A9",
        )
        ax.set_xticks(range(len(years)))
        ax.set_xticklabels(years, fontsize=7, rotation=45)
        ax.set_ylabel("₹ Cr", fontsize=8)
        ax.tick_params(axis="y", labelsize=7)
        ax.legend(fontsize=7, loc="upper left")
    ax.set_title("Balance Sheet Composition", fontsize=9, fontweight="bold")
    fig.tight_layout()
    return _fig_to_reader(fig)


def chart_cashflow_waterfall(cf):
    """Chart cashflow waterfall."""
    fig, ax = plt.subplots(figsize=(6.6, 2.6))
    if not cf.empty:
        latest = cf.iloc[-1]
        labels = ["CFO", "CFI", "CFF", "Net Cash Flow"]
        values = [
            latest["operating_activity"],
            latest["investing_activity"],
            latest["financing_activity"],
            latest["net_cash_flow"],
        ]
        colors_bar = ["#1E7B34" if v >= 0 else "#B00020" for v in values]
        ax.bar(labels, values, color=colors_bar)
        ax.axhline(0, color="black", linewidth=0.6)
        ax.set_ylabel("₹ Cr", fontsize=8)
        ax.tick_params(labelsize=7)
        for i, v in enumerate(values):
            ax.text(i, v, f"{v:,.0f}", ha="center", va="bottom" if v >= 0 else "top", fontsize=7)
    ax.set_title(
        f"Cash Flow Waterfall (FY{int(cf.iloc[-1]['year']) if not cf.empty else '-'})",
        fontsize=9,
        fontweight="bold",
    )
    fig.tight_layout()
    return _fig_to_reader(fig)


# =====================================================================
# KPI tile computation
# =====================================================================


def compute_kpi_tiles(data):
    """Compute kpi tiles."""
    pnl = data["pnl"]
    bs = data["bs"]  # noqa: F841 (unused - balance sheet data not currently in any KPI tile)
    fr = data["fr"]
    mc = data["mc"]

    latest_pnl = pnl.iloc[-1] if not pnl.empty else None
    latest_fr = fr.iloc[-1] if not fr.empty else None
    latest_mc = mc.iloc[-1] if not mc.empty else None
    company_row = data["company"].iloc[0] if not data["company"].empty else None

    def fmt_pct(v):
        """Fmt pct."""
        return f"{v:.1f}%" if v is not None and pd.notna(v) else "N/A"

    def fmt_num(v, suffix=""):
        """Fmt num."""
        return f"{v:,.0f}{suffix}" if v is not None and pd.notna(v) else "N/A"

    # Prefer the latest computed ratio from financial_ratios (consistent with the
    # ROE/ROCE chart below); fall back to the companies table snapshot. This also
    # sidesteps isolated scale/data-entry errors in the companies table snapshot
    # (e.g. a value stored as a fraction instead of a percentage).
    roe_val = (
        latest_fr["return_on_equity_pct"]
        if latest_fr is not None and pd.notna(latest_fr.get("return_on_equity_pct"))
        else (company_row["roe_percentage"] if company_row is not None else None)
    )
    roce_val = company_row["roce_percentage"] if company_row is not None else None
    opm_val = latest_pnl["opm_percentage"] if latest_pnl is not None else None
    de_val = latest_fr["debt_to_equity"] if latest_fr is not None else None
    mcap_val = latest_mc["market_cap_crore"] if latest_mc is not None else None
    sales_val = latest_pnl["sales"] if latest_pnl is not None else None

    tiles = [
        ("ROE", fmt_pct(roe_val)),
        ("ROCE", fmt_pct(roce_val)),
        ("OPM (Latest)", fmt_pct(opm_val)),
        ("Debt / Equity", f"{de_val:.2f}" if de_val is not None and pd.notna(de_val) else "N/A"),
        ("Market Cap", fmt_num(mcap_val, " Cr")),
        ("Revenue (Latest)", fmt_num(sales_val, " Cr")),
    ]
    return tiles


# =====================================================================
# PDF drawing helpers
# =====================================================================


def _draw_header(c, company_name, company_id, subtitle=""):
    c.setFillColor(NAVY)
    c.rect(0, PAGE_H - 26 * mm, PAGE_W, 26 * mm, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(15 * mm, PAGE_H - 13 * mm, company_name.strip())
    c.setFont("Helvetica", 11)
    c.drawString(
        15 * mm, PAGE_H - 20 * mm, f"NSE: {company_id}" + (f"   |   {subtitle}" if subtitle else "")
    )


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


def _draw_image(c, img_reader, x, y, w, h):
    from reportlab.lib.utils import ImageReader

    c.drawImage(
        ImageReader(img_reader), x, y, width=w, height=h, preserveAspectRatio=True, anchor="c"
    )


def _wrapped_paragraph_block(c, title, items, x, y, w, h, color, bullet_char):
    styles_title = ParagraphStyle(
        "title", fontName="Helvetica-Bold", fontSize=10, textColor=color, spaceAfter=4
    )
    styles_body = ParagraphStyle(
        "body",
        fontName="Helvetica",
        fontSize=8,
        leading=10.5,
        textColor=colors.HexColor("#222222"),
        alignment=TA_LEFT,
        spaceAfter=4,
    )

    frame = Frame(
        x, y, w, h, showBoundary=0, leftPadding=2, rightPadding=2, topPadding=2, bottomPadding=2
    )
    flow = [Paragraph(title, styles_title)]
    if items:
        for item in items:
            flow.append(Paragraph(f"{bullet_char} {item}", styles_body))
    else:
        flow.append(Paragraph("None identified.", styles_body))
    frame.addFromList(flow, c)


def _draw_badge(c, label, x, y):
    text = f"Capital Allocation Pattern: {label}"
    c.setFont("Helvetica-Bold", 9)
    tw = c.stringWidth(text, "Helvetica-Bold", 9) + 10
    c.setFillColor(GOLD)
    c.roundRect(x, y, tw, 8 * mm, 3, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.drawCentredString(x + tw / 2, y + 2.6 * mm, text)
    return tw


# =====================================================================
# Tearsheet page assembly
# =====================================================================


def draw_page_1(c, company_id, data):
    """Draw page 1."""
    company_row = data["company"].iloc[0] if not data["company"].empty else None
    company_name = company_row["company_name"] if company_row is not None else company_id
    _draw_header(c, company_name, company_id, subtitle=data["sector"] or "")

    tiles = compute_kpi_tiles(data)
    after_tiles_y = _draw_kpi_tiles(c, tiles, top_y=PAGE_H - 30 * mm)

    chart1 = chart_revenue_profit(data["pnl"])
    _draw_image(c, chart1, 15 * mm, after_tiles_y - 78 * mm, PAGE_W - 30 * mm, 76 * mm)

    chart2 = chart_roe_roce(data["pnl"], data["bs"])
    _draw_image(c, chart2, 15 * mm, after_tiles_y - 158 * mm, PAGE_W - 30 * mm, 76 * mm)

    c.setFont("Helvetica", 7)
    c.setFillColor(colors.HexColor("#888888"))
    c.drawString(15 * mm, 8 * mm, "Nifty100 Data Foundation - Company Tearsheet - Page 1 of 2")


def draw_page_2(c, company_id, data, pros, cons, capital_label):
    """Draw page 2."""
    company_row = data["company"].iloc[0] if not data["company"].empty else None
    company_name = company_row["company_name"] if company_row is not None else company_id
    _draw_header(c, company_name, company_id, subtitle="Cash Flow & Qualitative Summary")

    chart1 = chart_balance_sheet(data["bs"])
    _draw_image(c, chart1, 15 * mm, PAGE_H - 110 * mm, PAGE_W - 30 * mm, 76 * mm)

    chart2 = chart_cashflow_waterfall(data["cf"])
    _draw_image(c, chart2, 15 * mm, PAGE_H - 190 * mm, PAGE_W - 30 * mm, 76 * mm)

    col_w = (PAGE_W - 30 * mm - 6 * mm) / 2
    bullets_top = PAGE_H - 198 * mm
    bullets_h = 60 * mm

    _wrapped_paragraph_block(
        c, "Pros", pros, 15 * mm, bullets_top - bullets_h, col_w, bullets_h, GREEN, "+"
    )
    _wrapped_paragraph_block(
        c,
        "Cons",
        cons,
        15 * mm + col_w + 6 * mm,
        bullets_top - bullets_h,
        col_w,
        bullets_h,
        RED,
        "-",
    )

    _draw_badge(c, capital_label, 15 * mm, bullets_top - bullets_h - 14 * mm)

    c.setFont("Helvetica", 7)
    c.setFillColor(colors.HexColor("#888888"))
    c.drawString(15 * mm, 8 * mm, "Nifty100 Data Foundation - Company Tearsheet - Page 2 of 2")


def generate_tearsheet(db_path, company_id, pros_cons_df, cashflow_intel_df, output_path):
    """Generate tearsheet."""
    data = load_company_data(db_path, company_id)
    pros, cons = load_pros_cons(company_id, pros_cons_df)
    capital_label = load_capital_allocation_label(company_id, cashflow_intel_df)

    c = pdfcanvas.Canvas(str(output_path), pagesize=A4)
    draw_page_1(c, company_id, data)
    c.showPage()
    draw_page_2(c, company_id, data, pros, cons, capital_label)
    c.showPage()
    c.save()


# =====================================================================
# Batch generation
# =====================================================================


def batch_generate_tearsheets(db_path, output_dir=None, skipped_path=None):
    """Batch generate tearsheets."""
    output_dir = Path(output_dir) if output_dir else DEFAULT_TEARSHEET_DIR
    skipped_path = Path(skipped_path) if skipped_path else DEFAULT_SKIPPED_PATH
    output_dir.mkdir(parents=True, exist_ok=True)
    skipped_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(db_path)
    companies = pd.read_sql("SELECT company_id FROM companies", conn)["company_id"].tolist()
    pnl_years = pd.read_sql(
        "SELECT company_id, COUNT(*) as n_years FROM profitandloss "
        "WHERE year IS NOT NULL GROUP BY company_id",
        conn,
    )
    conn.close()

    year_counts = dict(zip(pnl_years.company_id, pnl_years.n_years))

    pros_cons_df = pd.read_csv(PROJECT_ROOT / "output" / "pros_cons_generated.csv")
    cashflow_intel_df = pd.read_excel(PROJECT_ROOT / "output" / "cashflow_intelligence.xlsx")

    generated, skipped = [], []

    for company_id in companies:
        n_years = year_counts.get(company_id, 0)
        if n_years < MIN_PNL_YEARS:
            skipped.append(
                {"company_id": company_id, "reason": f"only {n_years} year(s) of P&L data"}
            )
            continue

        out_path = output_dir / f"{company_id}_tearsheet.pdf"
        try:
            generate_tearsheet(db_path, company_id, pros_cons_df, cashflow_intel_df, out_path)
            generated.append(company_id)
        except Exception as exc:
            skipped.append({"company_id": company_id, "reason": f"error: {exc}"})

    pd.DataFrame(skipped, columns=["company_id", "reason"]).to_csv(skipped_path, index=False)

    return generated, skipped, output_dir, skipped_path


if __name__ == "__main__":
    generated, skipped, output_dir, skipped_path = batch_generate_tearsheets(
        PROJECT_ROOT / "data" / "nifty100.db"
    )
    print(f"Generated {len(generated)} tearsheets in {output_dir}")
    print(f"Skipped {len(skipped)} -> {skipped_path}")
