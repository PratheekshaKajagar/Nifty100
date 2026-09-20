# import pandas as pd


# def normalize_column_names(df):

#     """
#     Convert column names to lowercase with underscores.
#     """

#     df.columns = (
#         df.columns
#         .str.strip()
#         .str.lower()
#         .str.replace(" ", "_")
#         .str.replace("%", "pct")
#         .str.replace("-", "_")
#         .str.replace("/", "_")
#     )

#     return df


# def normalize_year(df, column="year"):
#     """
#     Convert values like 'Dec 2020', 'Mar 2021' to integer year.
#     """

#     if column not in df.columns:
#         return df

#     df[column] = (
#         df[column]
#         .astype(str)
#         .str.extract(r"(\d{4})")[0]
#     )

#     df[column] = pd.to_numeric(df[column], errors="coerce")

#     return df


# def normalize_company_id(df):
#     """
#     Standardize company_id values.
#     """

#     if "company_id" not in df.columns:
#         return df

#     df["company_id"] = (
#         df["company_id"]
#         .astype(str)
#         .str.strip()
#         .str.upper()
#     )

#     return df


# def normalize_numeric_columns(df):
#     """
#     Convert object columns containing numbers into numeric.
#     """

#     for col in df.columns:

#         if df[col].dtype == "object":

#             cleaned = (
#                 df[col]
#                 .astype(str)
#                 .str.replace(",", "", regex=False)
#                 .str.replace("%", "", regex=False)
#                 .str.strip()
#             )

#             numeric = pd.to_numeric(cleaned, errors="ignore")

#             df[col] = numeric

#     return df


# def normalize_dataframe(dataset_name, df):
#     """
#     Apply all normalization steps.
#     """

#     df = normalize_column_names(df)


#     # Dataset-specific fixes
#     if dataset_name == "companies":
#         if "id" in df.columns:
#             df = df.rename(columns={"id": "company_id"})

#     df = normalize_company_id(df)
#     df = normalize_year(df)
#     df = normalize_numeric_columns(df)

#     return df

#     df = normalize_company_id(df)

#     df = normalize_year(df)

#     df = normalize_numeric_columns(df)

#     return df
"""
normaliser.py
--------------
Contains all data normalization functions for the Nifty100 ETL pipeline.
"""

import pandas as pd

# ---------------------------------------------------------------------
# Column Name Normalization
# ---------------------------------------------------------------------

# def normalize_column_names(df):

# df.columns = (
#     df.columns
#     .str.strip()
#     .str.lower()
#     .str.replace(" ", "_", regex=False)
#     .str.replace("%", "_pct", regex=False)
#     .str.replace("-", "_", regex=False)
#     .str.replace("/", "_", regex=False)
#     .str.replace(r"[^a-zA-Z0-9_]", "", regex=True)
# )


# return df
def normalize_column_names(df):
    """Normalize column names."""
    df.columns = (
        df.columns.str.strip()
        .str.lower()
        .str.replace(" ", "_", regex=False)
        .str.replace("%", "pct", regex=False)
        .str.replace("-", "_", regex=False)
        .str.replace("/", "_", regex=False)
    )

    df.columns = df.columns.str.replace("__", "_", regex=False).str.strip("_")

    return df


# ---------------------------------------------------------------------
# Company ID Normalization
# ---------------------------------------------------------------------


def normalize_company_id(df):
    """
    Standardize company_id values.
    """

    if "company_id" not in df.columns:
        return df

    df["company_id"] = df["company_id"].astype(str).str.strip().str.upper()

    return df


# ---------------------------------------------------------------------
# Year Normalization
# ---------------------------------------------------------------------


def normalize_year(df, column="year"):
    """
    Convert values like:
        Dec 2020
        Mar 2021
    into

        2020
        2021
    """

    if column not in df.columns:
        return df

    df[column] = df[column].astype(str).str.extract(r"(\d{4})")[0]

    df[column] = pd.to_numeric(df[column], errors="coerce")

    return df


# ---------------------------------------------------------------------
# Numeric Column Normalization
# ---------------------------------------------------------------------

# def normalize_numeric_columns(df):
#     """
#     Convert numeric-looking object columns into numeric.
#     Removes commas and percentage signs.
#     """

#     for col in df.columns:

#         if df[col].dtype == "object":

#             cleaned = (
#                 df[col]
#                 .astype(str)
#                 .str.replace(",", "", regex=False)
#                 .str.replace("%", "", regex=False)
#                 .str.strip()
#             )

#             converted = pd.to_numeric(
#                 cleaned,
#                 errors="coerce"
#             )

#             # Only replace if conversion actually worked
#             if converted.notna().sum() > 0:
#                 df[col] = converted

#     return df
# def normalize_numeric_columns(df):

#     for col in df.columns:

#         if df[col].dtype == "object":

#             cleaned = (
#                 df[col]
#                 .astype(str)
#                 .str.replace(",", "", regex=False)
#                 .str.replace("%", "", regex=False)
#                 .str.strip()
#             )

#             converted = pd.to_numeric(
#                 cleaned,
#                 errors="coerce"
#             )

#             if converted.notna().sum() > 0:
#                 df[col] = converted

#     return df

# def normalize_numeric_columns(df):

#     for col in df.columns:

#         if df[col].dtype == object:

#             # Remove commas and %
#             df[col] = (
#                 df[col]
#                 .astype(str)
#                 .str.replace(",", "", regex=False)
#                 .str.replace("%", "", regex=False)
#                 .str.strip()
#             )

#             # Convert to numeric where possible
#             try:
#                 df[col] = df[col].astype(float)

#                 # Convert whole numbers to int
#                 if (df[col] % 1 == 0).all():
#                     df[col] = df[col].astype(int)

#             except ValueError:
#                 pass

#     return df
from pandas.api.types import (
    is_object_dtype,
    is_string_dtype,
)


def normalize_numeric_columns(df):
    """Normalize numeric columns."""
    for col in df.columns:

        if is_object_dtype(df[col]) or is_string_dtype(df[col]):

            cleaned = (
                df[col]
                .astype(str)
                .str.replace(",", "", regex=False)
                .str.replace("%", "", regex=False)
                .str.strip()
            )

            converted = pd.to_numeric(cleaned, errors="coerce")

            # Keep converted values only if every non-null value converted
            if converted.notna().sum() == cleaned.notna().sum():
                df[col] = converted

    return df


# ---------------------------------------------------------------------
# Main Normalization Pipeline
# ---------------------------------------------------------------------


def normalize_dataframe(dataset_name, df):
    """
    Apply all normalization rules.
    """

    # Standardize column names
    df = normalize_column_names(df)

    # Companies dataset:
    # id actually stores stock ticker (ABB, TCS, etc.)
    if dataset_name == "companies":

        if "id" in df.columns:
            df = df.rename(columns={"id": "company_id"})

    # Standardize company_id values
    df = normalize_company_id(df)

    # Normalize year
    df = normalize_year(df)

    # Convert numeric columns
    df = normalize_numeric_columns(df)

    return df
