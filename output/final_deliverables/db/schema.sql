-- ==========================================================
-- NIFTY100 DATA FOUNDATION
-- SQLite Schema
-- ==========================================================

PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS analysis;
DROP TABLE IF EXISTS balancesheet;
DROP TABLE IF EXISTS cashflow;
DROP TABLE IF EXISTS companies;
DROP TABLE IF EXISTS documents;
DROP TABLE IF EXISTS financial_ratios;
DROP TABLE IF EXISTS market_cap;
DROP TABLE IF EXISTS peer_groups;
DROP TABLE IF EXISTS profitandloss;
DROP TABLE IF EXISTS prosandcons;
DROP TABLE IF EXISTS sectors;
DROP TABLE IF EXISTS stock_prices;

-- ==========================================================
-- Companies
-- ==========================================================

CREATE TABLE companies (

    company_id TEXT PRIMARY KEY,

    company_logo TEXT,

    company_name TEXT NOT NULL,

    chart_link TEXT,

    about_company TEXT,

    website TEXT,

    nse_profile TEXT,

    bse_profile TEXT,

    face_value REAL,

    book_value REAL,

    roce_percentage REAL,

    roe_percentage REAL

);

-- ==========================================================
-- Profit & Loss
-- ==========================================================

CREATE TABLE profitandloss (

    id INTEGER PRIMARY KEY,

    company_id TEXT NOT NULL,

    year INTEGER,

    sales REAL,

    expenses REAL,

    operating_profit REAL,

    opm_percentage REAL,

    other_income REAL,

    interest REAL,

    depreciation REAL,

    profit_before_tax REAL,

    tax_percentage REAL,

    net_profit REAL,

    eps REAL,

    dividend_payout REAL,

    FOREIGN KEY(company_id)
        REFERENCES companies(company_id)

);

-- ==========================================================
-- Balance Sheet
-- ==========================================================

CREATE TABLE balancesheet (

    id INTEGER PRIMARY KEY,

    company_id TEXT NOT NULL,

    year INTEGER,

    equity_capital REAL,

    reserves REAL,

    borrowings REAL,

    other_liabilities REAL,

    total_liabilities REAL,

    fixed_assets REAL,

    cwip REAL,

    investments REAL,

    other_asset REAL,

    total_assets REAL,

    FOREIGN KEY(company_id)
        REFERENCES companies(company_id)

);

-- ==========================================================
-- Cash Flow
-- ==========================================================

CREATE TABLE cashflow (

    id INTEGER PRIMARY KEY,

    company_id TEXT NOT NULL,

    year INTEGER,

    operating_activity REAL,

    investing_activity REAL,

    financing_activity REAL,

    net_cash_flow REAL,

    FOREIGN KEY(company_id)
        REFERENCES companies(company_id)

);

-- ==========================================================
-- Analysis
-- ==========================================================

CREATE TABLE analysis (

    id INTEGER PRIMARY KEY,

    company_id TEXT NOT NULL,

    compounded_sales_growth TEXT,

    compounded_profit_growth TEXT,

    stock_price_cagr TEXT,

    roe TEXT,

    FOREIGN KEY(company_id)
        REFERENCES companies(company_id)

);

-- ==========================================================
-- Documents
-- ==========================================================

CREATE TABLE documents (

    id INTEGER PRIMARY KEY,

    company_id TEXT NOT NULL,

    year INTEGER,

    annual_report TEXT,

    FOREIGN KEY(company_id)
        REFERENCES companies(company_id)

);

-- ==========================================================
-- Financial Ratios
-- ==========================================================

CREATE TABLE financial_ratios (

    id INTEGER PRIMARY KEY,

    company_id TEXT NOT NULL,

    year INTEGER,

    net_profit_margin_pct REAL,

    operating_profit_margin_pct REAL,

    return_on_equity_pct REAL,

    debt_to_equity REAL,

    interest_coverage REAL,

    asset_turnover REAL,

    free_cash_flow_cr REAL,

    capex_cr REAL,

    earnings_per_share REAL,

    book_value_per_share REAL,

    dividend_payout_ratio_pct REAL,

    total_debt_cr REAL,

    cash_from_operations_cr REAL,

    FOREIGN KEY(company_id)
        REFERENCES companies(company_id)

);

-- ==========================================================
-- Market Cap
-- ==========================================================

CREATE TABLE market_cap (

    id INTEGER PRIMARY KEY,

    company_id TEXT NOT NULL,

    year INTEGER,

    market_cap_crore REAL,

    enterprise_value_crore REAL,

    pe_ratio REAL,

    pb_ratio REAL,

    ev_ebitda REAL,

    dividend_yield_pct REAL,

    FOREIGN KEY(company_id)
        REFERENCES companies(company_id)

);

-- ==========================================================
-- Peer Groups
-- ==========================================================

CREATE TABLE peer_groups (

    id INTEGER PRIMARY KEY,

    peer_group_name TEXT,

    company_id TEXT NOT NULL,

    is_benchmark BOOLEAN,

    FOREIGN KEY(company_id)
        REFERENCES companies(company_id)

);

-- ==========================================================
-- Pros & Cons
-- ==========================================================

CREATE TABLE prosandcons (

    id INTEGER PRIMARY KEY,

    company_id TEXT NOT NULL,

    pros TEXT,

    cons TEXT,

    FOREIGN KEY(company_id)
        REFERENCES companies(company_id)

);

-- ==========================================================
-- Sectors
-- ==========================================================

CREATE TABLE sectors (

    id INTEGER PRIMARY KEY,

    company_id TEXT NOT NULL,

    broad_sector TEXT,

    sub_sector TEXT,

    index_weight_pct REAL,

    market_cap_category TEXT,

    FOREIGN KEY(company_id)
        REFERENCES companies(company_id)

);

-- ==========================================================
-- Stock Prices
-- ==========================================================

CREATE TABLE stock_prices (

    id INTEGER PRIMARY KEY,

    company_id TEXT NOT NULL,

    date TEXT,

    open_price REAL,

    high_price REAL,

    low_price REAL,

    close_price REAL,

    volume INTEGER,

    adjusted_close REAL,

    FOREIGN KEY(company_id)
        REFERENCES companies(company_id)

);

-- ==========================================================
-- Indexes
-- ==========================================================

CREATE INDEX idx_profit_company
ON profitandloss(company_id);

CREATE INDEX idx_balance_company
ON balancesheet(company_id);

CREATE INDEX idx_cash_company
ON cashflow(company_id);

CREATE INDEX idx_analysis_company
ON analysis(company_id);

CREATE INDEX idx_docs_company
ON documents(company_id);

CREATE INDEX idx_ratio_company
ON financial_ratios(company_id);

CREATE INDEX idx_market_company
ON market_cap(company_id);

CREATE INDEX idx_peer_company
ON peer_groups(company_id);

CREATE INDEX idx_sector_company
ON sectors(company_id);

CREATE INDEX idx_pros_company
ON prosandcons(company_id);

CREATE INDEX idx_stock_company
ON stock_prices(company_id);

-- ==========================================================
-- Day 43 performance indexes - year columns on the large,
-- frequently-filtered time-series tables (screener/API endpoints
-- filter on year ranges constantly).
-- ==========================================================

CREATE INDEX idx_profit_year
ON profitandloss(year);

CREATE INDEX idx_balance_year
ON balancesheet(year);

CREATE INDEX idx_cash_year
ON cashflow(year);

CREATE INDEX idx_ratio_year
ON financial_ratios(year);

CREATE INDEX idx_market_year
ON market_cap(year);

CREATE INDEX idx_stock_date
ON stock_prices(date);

CREATE INDEX idx_docs_year
ON documents(year);

-- Composite (company_id, year) indexes - the most common lookup
-- pattern across the API (e.g. "this company's row for this year").
CREATE INDEX idx_profit_company_year
ON profitandloss(company_id, year);

CREATE INDEX idx_balance_company_year
ON balancesheet(company_id, year);

CREATE INDEX idx_cash_company_year
ON cashflow(company_id, year);

CREATE INDEX idx_ratio_company_year
ON financial_ratios(company_id, year);

CREATE INDEX idx_market_company_year
ON market_cap(company_id, year);