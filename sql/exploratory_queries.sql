-- ======================================================
-- 1. Total Companies
-- ======================================================

SELECT COUNT(*) AS total_companies
FROM companies;


-- ======================================================
-- 2. Companies by Sector
-- ======================================================

SELECT
    broad_sector,
    COUNT(*) AS total_companies
FROM sectors
GROUP BY broad_sector
ORDER BY total_companies DESC;


-- ======================================================
-- 3. Top 10 Companies by Market Cap
-- ======================================================

SELECT
    company_id,
    market_cap_crore
FROM market_cap
ORDER BY market_cap_crore DESC
LIMIT 10;


-- ======================================================
-- 4. Highest ROE
-- ======================================================

SELECT
    company_id,
    return_on_equity_pct
FROM financial_ratios
ORDER BY return_on_equity_pct DESC
LIMIT 10;


-- ======================================================
-- 5. Highest Revenue
-- ======================================================

SELECT
    company_id,
    year,
    sales
FROM profitandloss
ORDER BY sales DESC
LIMIT 10;


-- ======================================================
-- 6. Highest Net Profit
-- ======================================================

SELECT
    company_id,
    year,
    net_profit
FROM profitandloss
ORDER BY net_profit DESC
LIMIT 10;


-- ======================================================
-- 7. Companies with Highest Debt
-- ======================================================

SELECT
    company_id,
    borrowings
FROM balancesheet
ORDER BY borrowings DESC
LIMIT 10;


-- ======================================================
-- 8. Cash Flow Analysis
-- ======================================================

SELECT
    company_id,
    operating_activity,
    investing_activity,
    financing_activity
FROM cashflow
LIMIT 20;


-- ======================================================
-- 9. Stock Price Summary
-- ======================================================

SELECT
    company_id,
    AVG(close_price) AS average_close_price,
    MAX(high_price) AS highest_price,
    MIN(low_price) AS lowest_price
FROM stock_prices
GROUP BY company_id
ORDER BY average_close_price DESC;


-- ======================================================
-- 10. Companies with Annual Reports
-- ======================================================

SELECT
    company_id,
    COUNT(*) AS reports
FROM documents
GROUP BY company_id
ORDER BY reports DESC;