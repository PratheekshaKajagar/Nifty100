# from pathlib import Path
# import pandas as pd


# def read_excel_preview(file_path, rows=5):
#     """
#     Read the first few rows of an Excel file
#     without assuming any header.
#     """
#     return pd.read_excel(
#         file_path,
#         header=None,
#         nrows=rows
#     )


# def has_title_row(preview_df):
#     """
#     Detect whether the first row is a title row.
#     """

#     first_row = preview_df.iloc[0].fillna("").astype(str).tolist()

#     title = " ".join(first_row)

#     return "Bluestock" in title


# def load_excel(file_path):
#     """
#     Load an Excel file using the correct header.
#     """
#     preview = read_excel_preview(file_path)

#     if has_title_row(preview):
#         df = pd.read_excel(file_path, header=1)
#     else:
#         df = pd.read_excel(file_path)

#     return df
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------
# Files that contain a title row above the actual column headers
# ---------------------------------------------------------------------

HEADER_ROWS = {
    "analysis.xlsx": 1,
    "balancesheet.xlsx": 1,
    "cashflow.xlsx": 1,
    "companies.xlsx": 1,
    "documents.xlsx": 1,
    "profitandloss.xlsx": 1,
    "prosandcons.xlsx": 1,
}


def load_excel(file_path):
    """
    Load an Excel file using the correct header row.

    Parameters
    ----------
    file_path : str or Path
        Path to the Excel file.

    Returns
    -------
    pandas.DataFrame
    """

    file_path = Path(file_path)

    header_row = HEADER_ROWS.get(file_path.name, 0)

    df = pd.read_excel(file_path, header=header_row)

    return df


def load_all_excels(raw_data_dir):
    """
    Load all Excel files from the raw data directory.

    Parameters
    ----------
    raw_data_dir : str or Path

    Returns
    -------
    dict
        Dictionary of DataFrames.
    """

    raw_data_dir = Path(raw_data_dir)

    datasets = {}

    excel_files = sorted(raw_data_dir.glob("*.xlsx"))

    for file in excel_files:
        datasets[file.stem] = load_excel(file)

    return datasets


def dataset_summary(datasets):
    """
    Generate a summary of all loaded datasets.

    Parameters
    ----------
    datasets : dict

    Returns
    -------
    pandas.DataFrame
    """

    summary = []

    for name, df in datasets.items():

        summary.append(
            {
                "Dataset": name,
                "Rows": len(df),
                "Columns": len(df.columns),
                "Missing Values": int(df.isna().sum().sum()),
                "Duplicate Rows": int(df.duplicated().sum()),
            }
        )

    return pd.DataFrame(summary)
