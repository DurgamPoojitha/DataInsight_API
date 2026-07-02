"""
DataInsight API — Data Utilities
==================================
Stateless helper functions for DataFrame inspection, type inference,
and date-format detection.  Used by the cleaning engine and analysis services.

SOLID Principle Applied:
    Single Responsibility — pure data-inspection logic only;
    no I/O, no side effects, no business decisions.
"""

from __future__ import annotations

import re
from typing import Any

import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Dtype helpers (pandas 3.x compatibility)
# ---------------------------------------------------------------------------

def _is_string_like_dtype(series: pd.Series) -> bool:
    """
    Return True for string/object columns under both the legacy 'object' dtype
    (pandas < 3) and the new native StringDtype (pandas >= 3, str dtype).

    Args:
        series: Any pandas Series.

    Returns:
        True if the column holds string values.
    """
    if pd.api.types.is_object_dtype(series):
        return True
    # pandas 3.x: dtype.name == 'str' or pd.StringDtype
    dtype_name = str(series.dtype).lower()
    return dtype_name in ("string", "str", "string[python]", "string[pyarrow]")


# ---------------------------------------------------------------------------
# Date-format detection
# ---------------------------------------------------------------------------

# Ordered list of common date format patterns to probe
_DATE_FORMATS: list[str] = [
    "%Y-%m-%d",           # ISO 8601 — 2024-01-15
    "%Y/%m/%d",           # 2024/01/15
    "%d-%m-%Y",           # 15-01-2024
    "%d/%m/%Y",           # 15/01/2024
    "%m/%d/%Y",           # 01/15/2024
    "%m-%d-%Y",           # 01-15-2024
    "%Y-%m-%d %H:%M:%S",  # 2024-01-15 10:30:00
    "%d-%m-%Y %H:%M:%S",  # 15-01-2024 10:30:00
    "%m/%d/%Y %H:%M:%S",  # 01/15/2024 10:30:00
    "%Y%m%d",             # 20240115
    "%b %d, %Y",          # Jan 15, 2024
    "%d %b %Y",           # 15 Jan 2024
    "%B %d, %Y",          # January 15, 2024
]

# Regex patterns that strongly suggest a column contains dates
_DATE_HINT_PATTERNS: list[re.Pattern] = [
    re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),           # 2024-01-15
    re.compile(r"\b\d{2}/\d{2}/\d{4}\b"),            # 01/15/2024
    re.compile(r"\b\d{2}-\d{2}-\d{4}\b"),            # 15-01-2024
    re.compile(r"\b\d{4}/\d{2}/\d{2}\b"),            # 2024/01/15
    re.compile(r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\b", re.I),
]


def detect_date_formats_in_column(series: pd.Series) -> list[str]:
    """
    Probe a string column for date-format patterns and return all formats
    that successfully parse at least one non-null value.

    Args:
        series: A pandas Series (should be object/string dtype).

    Returns:
        List of format strings that successfully matched at least one value.
        Empty list if no date patterns detected.
    """
    sample: pd.Series = series.dropna().head(50).astype(str)
    if sample.empty:
        return []

    matched_formats: list[str] = []
    for fmt in _DATE_FORMATS:
        try:
            parsed = pd.to_datetime(sample, format=fmt, errors="coerce")
            if parsed.notna().sum() > 0:
                matched_formats.append(fmt)
        except Exception:
            continue

    return matched_formats


def is_likely_date_column(series: pd.Series) -> bool:
    """
    Heuristic check: does this column look like it contains dates?

    Checks:
      1. Already a datetime dtype → True
      2. Is a string/object column → regex-probe the first 30 non-null values.

    Args:
        series: Any pandas Series.

    Returns:
        True if the column likely contains date values.
    """
    if pd.api.types.is_datetime64_any_dtype(series):
        return True

    if not _is_string_like_dtype(series):
        return False

    sample_values: list[str] = (
        series.dropna().head(30).astype(str).tolist()
    )

    for val in sample_values:
        for pattern in _DATE_HINT_PATTERNS:
            if pattern.search(val):
                return True

    # Also try pandas inference on a small sample
    try:
        parsed = pd.to_datetime(sample_values[:20], errors="coerce", format="mixed")
        if parsed.notna().mean() > 0.5:
            return True
    except Exception:
        pass

    return False


# ---------------------------------------------------------------------------
# Whitespace detection
# ---------------------------------------------------------------------------

def column_has_whitespace_issues(series: pd.Series) -> bool:
    """
    Check whether any string values in the column have leading or trailing
    whitespace (a common data-entry problem).

    Args:
        series: Any pandas Series.

    Returns:
        True if at least one non-null string value has surrounding whitespace.
    """
    if not _is_string_like_dtype(series):
        return False

    non_null: pd.Series = series.dropna().astype(str)
    if non_null.empty:
        return False

    return bool((non_null != non_null.str.strip()).any())


# ---------------------------------------------------------------------------
# Type inference helpers
# ---------------------------------------------------------------------------

def infer_column_type_label(series: pd.Series) -> str:
    """
    Return a human-readable type label for a column.

    Returns one of: 'integer', 'float', 'boolean', 'datetime',
                    'string', 'mixed', 'empty'.

    Args:
        series: Any pandas Series.

    Returns:
        A string label describing the column's effective type.
    """
    if series.dropna().empty:
        return "empty"
    if pd.api.types.is_bool_dtype(series):
        return "boolean"
    if pd.api.types.is_datetime64_any_dtype(series):
        return "datetime"
    if pd.api.types.is_integer_dtype(series):
        return "integer"
    if pd.api.types.is_float_dtype(series):
        return "float"
    if _is_string_like_dtype(series):
        # Check for mixed numeric/string content
        non_null = series.dropna()
        numeric_count = pd.to_numeric(non_null, errors="coerce").notna().sum()
        if numeric_count > 0 and numeric_count < len(non_null):
            return "mixed"
        return "string"
    return str(series.dtype)


def get_sample_bad_values(series: pd.Series, n: int = 5) -> list[Any]:
    """
    Return a small sample of values that are likely problematic:
    NaN, strings that look numeric but have extra spaces, mixed types, etc.

    Args:
        series: Any pandas Series.
        n:      Maximum number of sample values to return.

    Returns:
        List of up to n problematic values (as Python native types).
    """
    bad: list[Any] = []

    # Collect NaN positions (represented as None for JSON safety)
    null_positions = series[series.isna()].head(n).index.tolist()
    bad.extend([None] * min(len(null_positions), n))

    if len(bad) >= n:
        return bad[:n]

    # Collect whitespace-padded strings
    if _is_string_like_dtype(series):
        non_null = series.dropna().astype(str)
        padded = non_null[non_null != non_null.str.strip()].head(n - len(bad))
        bad.extend(padded.tolist())

    return bad[:n]


# ---------------------------------------------------------------------------
# DataFrame summary helpers
# ---------------------------------------------------------------------------

def compute_missing_stats(df: pd.DataFrame) -> dict[str, dict[str, float]]:
    """
    Compute per-column missing value counts and percentages.

    Args:
        df: Any pandas DataFrame.

    Returns:
        Dict mapping column_name → {"count": int, "pct": float}.
        Percentage is 0.0–100.0.
    """
    total: int = len(df)
    result: dict[str, dict[str, float]] = {}
    for col in df.columns:
        count: int = int(df[col].isna().sum())
        pct: float = round((count / total * 100) if total > 0 else 0.0, 2)
        result[col] = {"count": count, "pct": pct}
    return result


def find_empty_columns(df: pd.DataFrame) -> list[str]:
    """
    Return the names of columns where ALL values are null/NaN.

    Args:
        df: Any pandas DataFrame.

    Returns:
        List of column names that are entirely empty.
    """
    return [col for col in df.columns if df[col].isna().all()]


def count_duplicate_rows(df: pd.DataFrame) -> int:
    """
    Count the number of rows that are exact duplicates of a previous row.

    Args:
        df: Any pandas DataFrame.

    Returns:
        Number of duplicate rows (first occurrence not counted).
    """
    return int(df.duplicated().sum())


def safe_scalar(value: Any) -> Any:
    """
    Convert numpy scalars to native Python types for JSON serialisation.

    Args:
        value: Any value that might be a numpy scalar.

    Returns:
        A JSON-safe Python native type.
    """
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, float) and np.isnan(value):
        return None
    return value
