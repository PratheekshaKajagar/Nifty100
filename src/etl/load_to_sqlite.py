import sqlite3
from pathlib import Path

import pandas as pd

# ==========================================================
# Paths
# ==========================================================

PROJECT_ROOT = Path(__file__).resolve().parents[2]

PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
OUTPUT_DIR = PROJECT_ROOT / "data" / "output"

DB_PATH = PROJECT_ROOT / "data" / "nifty100.db"
SCHEMA_PATH = PROJECT_ROOT / "db" / "schema.sql"

OUTPUT_DIR.mkdir(exist_ok=True)

# ==========================================================
# CSV -> SQLite Table Mapping
# ==========================================================

TABLES = [
    "companies",
    "profitandloss",
    "balancesheet",
    "cashflow",
    "analysis",
    "documents",
    "financial_ratios",
    "market_cap",
    "peer_groups",
    "prosandcons",
    "sectors",
    "stock_prices",
]

# ==========================================================
# Create Database
# ==========================================================


def create_database():
    """Create database."""
    if DB_PATH.exists():
        DB_PATH.unlink()

    conn = sqlite3.connect(DB_PATH)

    conn.execute("PRAGMA foreign_keys = OFF;")

    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        conn.executescript(f.read())

    conn.commit()
    conn.close()


# ==========================================================
# Load One Table
# ==========================================================


def load_table(conn, table_name):
    """Load table."""
    csv_file = PROCESSED_DIR / f"{table_name}.csv"

    if not csv_file.exists():

        return {
            "table": table_name,
            "status": "Missing CSV",
            "rows_loaded": 0,
        }

    df = pd.read_csv(csv_file)

    # -------------------------
    # Convert year
    # -------------------------

    if "year" in df.columns:

        df["year"] = pd.to_numeric(df["year"], errors="coerce")

    # -------------------------
    # Convert date
    # -------------------------

    if "date" in df.columns:

        df["date"] = pd.to_datetime(df["date"], errors="coerce")

        df["date"] = df["date"].dt.strftime("%Y-%m-%d")

    # -------------------------
    # Load table
    # -------------------------

    # Remove invalid foreign keys
    if table_name != "companies" and "company_id" in df.columns:

        companies = pd.read_sql("SELECT company_id FROM companies", conn)

        valid = set(companies["company_id"])

        before = len(df)

        df = df[df["company_id"].isin(valid)]

        print(f"{table_name}: removed {before-len(df)} invalid rows")

    df.to_sql(table_name, conn, if_exists="append", index=False)

    return {
        "table": table_name,
        "status": "Loaded",
        "rows_loaded": len(df),
    }


# ==========================================================
# Load All Tables
# ==========================================================


def load_database():
    """Load database."""
    conn = sqlite3.connect(DB_PATH)

    conn.execute("PRAGMA foreign_keys = OFF;")

    audit = []

    print("\nLoading Tables\n")

    for table in TABLES:

        print(f"Loading {table}...")

        result = load_table(conn, table)

        audit.append(result)

    conn.commit()
    conn.close()

    audit_df = pd.DataFrame(audit)

    audit_df.to_csv(OUTPUT_DIR / "load_audit.csv", index=False)

    return audit_df


# ==========================================================
# Main
# ==========================================================

if __name__ == "__main__":

    print("=" * 60)
    print("NIFTY100 DATABASE LOADER")
    print("=" * 60)

    create_database()

    audit = load_database()

    print("\n")
    print(audit)

    print("\nDatabase Created Successfully!")

    print(DB_PATH)
