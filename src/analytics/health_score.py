"""
Composite Financial Health Score Engine (0-100)
"""
import sqlite3
import pandas as pd
import numpy as np

def compute_financial_health_score(db_path: str = "data/nifty100.db") -> pd.DataFrame:
    conn = sqlite3.connect(db_path)
    query = """
    SELECT 
        r.company_id,
        r.return_on_equity_pct,
        r.return_on_capital_employed_pct,
        r.net_profit_margin_pct,
        r.debt_to_equity,
        r.interest_coverage,
        r.free_cash_flow_cr,
        r.cash_from_operations_cr,
        s.broad_sector
    FROM financial_ratios r
    JOIN (SELECT company_id, MAX(year) as max_year FROM financial_ratios GROUP BY company_id) latest
        ON r.company_id = latest.company_id AND r.year = latest.max_year
    LEFT JOIN sectors s ON r.company_id = s.company_id
    """
    df = pd.read_sql_query(query, conn)
    conn.close()

    results = []
    for _, row in df.iterrows():
        # 1. Profitability (35%)
        roe_score = min(max((row['return_on_equity_pct'] or 0) / 25.0 * 100, 0), 100) * 0.15
        roce_score = min(max((row['return_on_capital_employed_pct'] or 0) / 25.0 * 100, 0), 100) * 0.10
        npm_score = min(max((row['net_profit_margin_pct'] or 0) / 20.0 * 100, 0), 100) * 0.10
        prof_score = roe_score + roce_score + npm_score

        # 2. Cash Quality (30%)
        fcf = row['free_cash_flow_cr'] or 0
        cfo = row['cash_from_operations_cr'] or 0
        fcf_score = 100 if fcf > 0 else 20
        cfo_score = 100 if cfo > 0 else 0
        cash_score = (fcf_score * 0.15) + (cfo_score * 0.15)

        # 3. Leverage / Solvency (20%)
        if row['broad_sector'] == 'Financials':
            lev_score = 80.0 * 0.20
        else:
            de = row['debt_to_equity']
            if de is None or de == 0:
                d_score = 100
            elif de <= 0.5:
                d_score = 85
            elif de <= 1.0:
                d_score = 70
            elif de <= 2.0:
                d_score = 40
            else:
                d_score = 10
            lev_score = d_score * 0.20

        # 4. Base Stability / Efficiency (15%)
        eff_score = 75.0 * 0.15

        total_score = round(prof_score + cash_score + lev_score + eff_score, 1)
        total_score = min(max(total_score, 0.0), 100.0)

        if total_score >= 75:
            band = "Strong"
        elif total_score >= 50:
            band = "Stable"
        elif total_score >= 30:
            band = "Moderate"
        else:
            band = "High Risk"

        results.append({
            "company_id": row['company_id'],
            "financial_health_score": total_score,
            "health_band": band
        })

    score_df = pd.DataFrame(results)
    score_df.to_csv("output/financial_health_scores.csv", index=False)
    return score_df

if __name__ == "__main__":
    df = compute_financial_health_score()
    print(f"Generated Financial Health Scores for {len(df)} companies")