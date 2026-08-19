"""
Alerts & Watchlist Engine (Module 12)
"""
import sqlite3
import pandas as pd

def generate_alerts(db_path: str = "data/nifty100.db") -> pd.DataFrame:
    conn = sqlite3.connect(db_path)
    # Join profitandloss to get the raw sales metric alongside ratios
    query = """
    SELECT 
        r.company_id,
        r.year,
        p.sales,
        r.return_on_equity_pct,
        r.debt_to_equity,
        r.free_cash_flow_cr
    FROM financial_ratios r
    LEFT JOIN profitandloss p 
        ON r.company_id = p.company_id AND r.year = p.year
    ORDER BY r.company_id, r.year ASC
    """
    df = pd.read_sql_query(query, conn)
    conn.close()

    alerts = []
    for company, group in df.groupby('company_id'):
        if len(group) < 2:
            continue
        curr = group.iloc[-1]
        prev = group.iloc[-2]

        # 1. Check ROE deterioration > 500 bps
        if curr['return_on_equity_pct'] is not None and prev['return_on_equity_pct'] is not None:
            if (prev['return_on_equity_pct'] - curr['return_on_equity_pct']) > 5.0:
                alerts.append({"company_id": company, "alert_type": "ROE Deterioration", "severity": "WARNING"})

        # 2. Check Sales / Revenue Decline
        if curr['sales'] is not None and prev['sales'] is not None:
            if curr['sales'] < prev['sales']:
                alerts.append({"company_id": company, "alert_type": "Revenue Contraction", "severity": "WARNING"})

        # 3. Check Debt Surge > 25%
        if curr['debt_to_equity'] is not None and prev['debt_to_equity'] is not None and prev['debt_to_equity'] > 0:
            if ((curr['debt_to_equity'] - prev['debt_to_equity']) / prev['debt_to_equity']) > 0.25:
                alerts.append({"company_id": company, "alert_type": "Debt Surge", "severity": "WARNING"})

        # 4. Check 3-year Persistent Negative Free Cash Flow
        if len(group) >= 3:
            last_3_fcf = group['free_cash_flow_cr'].tail(3).tolist()
            if all(f is not None and f < 0 for f in last_3_fcf):
                alerts.append({"company_id": company, "alert_type": "Persistent Negative FCF", "severity": "CRITICAL"})

    alerts_df = pd.DataFrame(alerts)
    alerts_df.to_csv("output/alerts_watchlist.csv", index=False)
    return alerts_df

if __name__ == "__main__":
    df = generate_alerts()
    print(f"[OK] Generated {len(df)} active alerts")