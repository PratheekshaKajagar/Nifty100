import pandas as pd


class DataValidator:

    def __init__(self):
        self.failures = []

    def log_failure(self, dataset, rule, severity, row, message):
        """Log failure."""
        self.failures.append(
            {"dataset": dataset, "rule": rule, "severity": severity, "row": row, "message": message}
        )

    def check_primary_key(self, df, dataset, key):
        """Check primary key."""
        if key not in df.columns:
            return

        duplicates = df[df[key].duplicated()]

        for idx in duplicates.index:
            self.log_failure(dataset, "DQ-01", "CRITICAL", idx, f"Duplicate primary key: {key}")

    def check_missing_values(self, df, dataset):
        """Check missing values."""
        for col in df.columns:

            missing = df[col].isna()

            for idx in df[missing].index:

                self.log_failure(dataset, "DQ-02", "WARNING", idx, f"Missing value in {col}")

    def check_negative_numeric(self, df, dataset):
        """Check negative numeric."""
        numeric = df.select_dtypes(include="number")

        for col in numeric.columns:

            invalid = numeric[col] < 0

            for idx in df[invalid].index:

                self.log_failure(dataset, "DQ-03", "WARNING", idx, f"Negative value in {col}")

    def check_year_range(self, df, dataset, column="year", min_year=2000, max_year=2026):
        """
        DQ-04: flag years outside a plausible range for this dataset.
        """
        if column not in df.columns:
            return

        numeric_years = pd.to_numeric(df[column], errors="coerce")

        invalid = numeric_years.notna() & ((numeric_years < min_year) | (numeric_years > max_year))

        for idx in df[invalid].index:
            self.log_failure(
                dataset,
                "DQ-04",
                "WARNING",
                idx,
                f"Year {df.loc[idx, column]} outside plausible range " f"[{min_year}, {max_year}]",
            )

    def check_percentage_bounds(self, df, dataset, lower=-1000, upper=1000):
        """
        DQ-05: flag percentage columns (name ends in '_pct' or 'pct')
        with implausible values (e.g. a typo turning 12.5% into
        1250%).
        """
        pct_columns = [
            col
            for col in df.columns
            if str(col).lower().endswith("pct") or str(col).lower().endswith("_pct")
        ]

        for col in pct_columns:

            numeric = pd.to_numeric(df[col], errors="coerce")

            invalid = numeric.notna() & ((numeric < lower) | (numeric > upper))

            for idx in df[invalid].index:
                self.log_failure(
                    dataset,
                    "DQ-05",
                    "WARNING",
                    idx,
                    f"Implausible percentage in {col}: {df.loc[idx, col]}",
                )

    def check_duplicate_rows(self, df, dataset):
        """
        DQ-06: flag fully duplicated rows (every column identical),
        which usually means a row was loaded twice.
        """
        duplicates = df[df.duplicated(keep="first")]

        for idx in duplicates.index:
            self.log_failure(dataset, "DQ-06", "WARNING", idx, "Fully duplicated row")

    def check_orphan_foreign_key(self, df, dataset, valid_ids, key="company_id"):
        """
        DQ-07: flag rows whose foreign key (default company_id) does
        not exist in the supplied set of valid IDs (e.g. the
        companies master list). Catches rows that reference a
        company that was never loaded.
        """
        if key not in df.columns or valid_ids is None:
            return

        valid_ids = set(valid_ids)
        invalid = ~df[key].isin(valid_ids)

        for idx in df[invalid].index:
            self.log_failure(
                dataset,
                "DQ-07",
                "CRITICAL",
                idx,
                f"Orphan foreign key: {key}={df.loc[idx, key]!r} not found in companies master",
            )

    def check_blank_text(self, df, dataset, columns=None):
        """
        DQ-08: flag empty-string or whitespace-only values in text
        columns that should always be populated (e.g. company_name).
        Distinct from DQ-02 (missing/NaN) - this catches the "" or
        "   " case that isna() does not.
        """
        columns = columns or [col for col in df.columns if df[col].dtype == object]

        for col in columns:
            if col not in df.columns:
                continue

            blank = df[col].apply(lambda v: isinstance(v, str) and v.strip() == "")

            for idx in df[blank].index:
                self.log_failure(
                    dataset, "DQ-08", "WARNING", idx, f"Blank/whitespace-only value in {col}"
                )

    def check_ratio_bounds(self, df, dataset, lower=-100, upper=100):
        """
        DQ-09: flag implausible values in ratio-style columns (name
        contains 'ratio', 'debt_to_equity', or 'coverage') that fall
        outside a sane numeric range - separate from DQ-05, which
        only looks at '*_pct' columns.
        """
        ratio_columns = [
            col
            for col in df.columns
            if any(token in str(col).lower() for token in ("ratio", "debt_to_equity", "coverage"))
        ]

        for col in ratio_columns:
            numeric = pd.to_numeric(df[col], errors="coerce")
            invalid = numeric.notna() & ((numeric < lower) | (numeric > upper))

            for idx in df[invalid].index:
                self.log_failure(
                    dataset,
                    "DQ-09",
                    "WARNING",
                    idx,
                    f"Implausible ratio in {col}: {df.loc[idx, col]}",
                )

    def check_non_numeric_junk(self, df, dataset, columns):
        """
        DQ-10: flag values in a column that is supposed to be
        numeric but contains non-numeric junk tokens such as 'N/A',
        '#DIV/0!', or a bare '-' (common spreadsheet export
        artifacts that silently become NaN if not caught early).
        """
        junk_tokens = {"n/a", "na", "#div/0!", "-", "--", "#value!", "#ref!"}

        for col in columns:
            if col not in df.columns:
                continue

            is_junk = df[col].apply(
                lambda v: isinstance(v, str) and v.strip().lower() in junk_tokens
            )

            for idx in df[is_junk].index:
                self.log_failure(
                    dataset,
                    "DQ-10",
                    "CRITICAL",
                    idx,
                    f"Non-numeric junk value in {col}: {df.loc[idx, col]!r}",
                )

    def check_id_formatting(self, df, dataset, key="company_id"):
        """
        DQ-11: flag company_id values with leading/trailing
        whitespace or lowercase letters, which cause silent join
        failures against the companies master table (tickers are
        stored upper-case, no padding).
        """
        if key not in df.columns:
            return

        def is_malformed(v):
            """Is malformed."""
            if not isinstance(v, str):
                return False
            return v != v.strip() or v != v.upper()

        malformed = df[key].apply(is_malformed)

        for idx in df[malformed].index:
            self.log_failure(
                dataset,
                "DQ-11",
                "WARNING",
                idx,
                f"Malformed {key} value: {df.loc[idx, key]!r} (expected trimmed, upper-case)",
            )

    def check_outlier_zscore(self, df, dataset, columns=None, threshold=5.0):
        """
        DQ-12: flag numeric values whose absolute Z-score (within
        this dataset/column) exceeds `threshold`. A looser, global
        cousin of the per-sector Z-score check used for
        output/outlier_report.csv (Day 37) - this one is dataset-wide
        and meant to catch gross data-entry errors during load.
        """
        numeric_cols = columns or df.select_dtypes(include="number").columns

        for col in numeric_cols:
            if col not in df.columns:
                continue

            series = pd.to_numeric(df[col], errors="coerce")
            std = series.std()

            if not std or pd.isna(std) or std == 0:
                continue

            z = (series - series.mean()) / std
            invalid = z.abs() > threshold

            for idx in df[invalid].index:
                self.log_failure(
                    dataset,
                    "DQ-12",
                    "WARNING",
                    idx,
                    f"Outlier in {col}: z-score {z.loc[idx]:.2f} exceeds {threshold}",
                )

    def check_required_columns(self, df, dataset, required_columns):
        """
        DQ-13: flag an entire dataset as failing schema validation
        if one or more required columns are missing outright (e.g.
        a source file was re-exported with a renamed column). Logged
        once per missing column rather than once per row, since
        there is no row to point to.
        """
        missing_cols = [col for col in required_columns if col not in df.columns]

        for col in missing_cols:
            self.log_failure(
                dataset, "DQ-13", "CRITICAL", None, f"Required column missing from dataset: {col}"
            )

    def check_duplicate_company_year(self, df, dataset, key="company_id", year_col="year"):
        """
        DQ-14: flag duplicate (company_id, year) pairs in a
        time-series dataset (P&L, balance sheet, cash flow, ratios,
        market cap) - a company should report at most one row per
        year.
        """
        if key not in df.columns or year_col not in df.columns:
            return

        duplicates = df[df.duplicated(subset=[key, year_col], keep="first")]

        for idx in duplicates.index:
            self.log_failure(
                dataset,
                "DQ-14",
                "WARNING",
                idx,
                f"Duplicate ({key}, {year_col}) pair: "
                f"({df.loc[idx, key]!r}, {df.loc[idx, year_col]!r})",
            )

    def validate(self, dataset_name, df, valid_company_ids=None, required_columns=None):
        """Validate."""
        if "id" in df.columns:
            self.check_primary_key(df, dataset_name, "id")

        self.check_missing_values(df, dataset_name)

        self.check_negative_numeric(df, dataset_name)

        self.check_year_range(df, dataset_name)

        self.check_percentage_bounds(df, dataset_name)

        self.check_duplicate_rows(df, dataset_name)

        self.check_orphan_foreign_key(df, dataset_name, valid_company_ids)

        self.check_blank_text(df, dataset_name)

        self.check_ratio_bounds(df, dataset_name)

        self.check_id_formatting(df, dataset_name)

        self.check_outlier_zscore(df, dataset_name)

        if required_columns:
            self.check_required_columns(df, dataset_name, required_columns)

        self.check_duplicate_company_year(df, dataset_name)

    def report(self):
        """Report."""
        columns = ["dataset", "rule", "severity", "row", "message"]

        if not self.failures:
            return pd.DataFrame(columns=columns)

        return pd.DataFrame(self.failures, columns=columns)
