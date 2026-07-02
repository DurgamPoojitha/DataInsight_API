"""
DataInsight API — Data Cleaning Schemas
=========================================
Pydantic models that define the request/response contract for the
data cleaning engine endpoints.

Design:
  - CleaningRequest  : what the caller wants done (fully optional fields)
  - CleaningReport   : what actually happened (detailed action log)
  - IssueReport      : what was detected before any cleaning
"""

from __future__ import annotations

from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class FillStrategy(str, Enum):
    """Strategy used to impute missing values in numeric columns."""
    MEAN   = "mean"
    MEDIAN = "median"
    MODE   = "mode"
    CUSTOM = "custom"   # use caller-supplied value per column
    ZERO   = "zero"
    FFILL  = "ffill"    # forward-fill (time-series friendly)
    BFILL  = "bfill"    # backward-fill


class DateFormatHint(str, Enum):
    """Common date format strings the engine will attempt."""
    ISO       = "%Y-%m-%d"
    US        = "%m/%d/%Y"
    EU        = "%d/%m/%Y"
    DATETIME  = "%Y-%m-%d %H:%M:%S"
    AUTO      = "auto"   # let pandas infer with mixed_format=True


# ---------------------------------------------------------------------------
# Request sub-models
# ---------------------------------------------------------------------------

class MissingValueConfig(BaseModel):
    """
    Configuration for missing-value imputation.

    Attributes:
        strategy (FillStrategy):
            Algorithm used to compute fill values for numeric columns.
        custom_values (dict[str, Any]):
            Column-specific overrides: {"col_name": fill_value}.
            When provided and strategy=CUSTOM, these values are used directly.
        string_fill (str | None):
            Value to use for string/object columns (e.g. "Unknown", "N/A").
            Defaults to None (skip string columns).
        apply_to_columns (list[str]):
            Restrict imputation to these specific column names.
            Empty list = apply to all columns.
    """
    strategy: FillStrategy = Field(
        default=FillStrategy.MEAN,
        description="Imputation strategy for numeric columns",
    )
    custom_values: dict[str, Any] = Field(
        default_factory=dict,
        description="Per-column override values (used with strategy=custom)",
    )
    string_fill: str | None = Field(
        default=None,
        description="Fill value for string columns (None = skip)",
    )
    apply_to_columns: list[str] = Field(
        default_factory=list,
        description="Restrict imputation to these columns (empty = all)",
    )


class DropColumnConfig(BaseModel):
    """
    Configuration for dropping columns that exceed a missing-value threshold.

    Attributes:
        threshold (float):
            Fraction of missing values above which a column is dropped.
            E.g. 0.5 drops any column with > 50 % missing values.
    """
    threshold: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Missing-value fraction above which the column is dropped",
    )


class StringNormConfig(BaseModel):
    """
    Configuration for string column normalisation.

    Attributes:
        strip_whitespace (bool): Remove leading/trailing whitespace.
        lowercase (bool):        Convert to lowercase.
        apply_to_columns (list[str]): Limit to these columns (empty = all string cols).
    """
    strip_whitespace: bool = Field(default=True, description="Strip leading/trailing whitespace")
    lowercase: bool = Field(default=False, description="Convert to lowercase")
    apply_to_columns: list[str] = Field(
        default_factory=list,
        description="Specific columns to normalise (empty = all string columns)",
    )


class DateConversionConfig(BaseModel):
    """
    Configuration for date column detection and conversion.

    Attributes:
        columns (list[str]):
            Column names to attempt datetime conversion on.
            Empty list = auto-detect likely date columns.
        format_hint (DateFormatHint):
            Preferred strptime format string.  Use AUTO to let pandas infer.
        errors (str):
            How to handle un-parseable values ('coerce' → NaT, 'raise' → error).
    """
    columns: list[str] = Field(
        default_factory=list,
        description="Columns to convert (empty = auto-detect)",
    )
    format_hint: DateFormatHint = Field(
        default=DateFormatHint.AUTO,
        description="Preferred date format or AUTO for inference",
    )
    errors: str = Field(
        default="coerce",
        description="'coerce' turns bad dates into NaT; 'raise' throws an error",
    )


# ---------------------------------------------------------------------------
# Main cleaning request
# ---------------------------------------------------------------------------

class CleaningRequest(BaseModel):
    """
    Top-level cleaning configuration sent by the caller.

    Each field is fully optional — omitting it skips that operation.
    Operations are applied in the following deterministic order:
      1. drop_high_missing_columns
      2. remove_duplicates
      3. fill_missing_values
      4. normalize_strings
      5. convert_dates

    Attributes:
        remove_duplicates (bool):
            Drop exact-duplicate rows, keeping the first occurrence.
        fill_missing (MissingValueConfig | None):
            Impute missing values.  None = skip.
        drop_high_missing_columns (DropColumnConfig | None):
            Remove columns exceeding the missing-value threshold.  None = skip.
        normalize_strings (StringNormConfig | None):
            Strip whitespace / lowercase string columns.  None = skip.
        convert_dates (DateConversionConfig | None):
            Parse date strings into datetime64.  None = skip.
        save_cleaned (bool):
            If True, persist the cleaned DataFrame as a new dataset and
            return a new dataset_id in the response.
    """
    remove_duplicates: bool = Field(
        default=False,
        description="Remove exact duplicate rows",
    )
    fill_missing: MissingValueConfig | None = Field(
        default=None,
        description="Impute missing values (None = skip)",
    )
    drop_high_missing_columns: DropColumnConfig | None = Field(
        default=None,
        description="Drop columns with excessive missing values (None = skip)",
    )
    normalize_strings: StringNormConfig | None = Field(
        default=None,
        description="Normalise string columns (None = skip)",
    )
    convert_dates: DateConversionConfig | None = Field(
        default=None,
        description="Parse date strings into datetime64 (None = skip)",
    )
    save_cleaned: bool = Field(
        default=True,
        description="Save the cleaned data as a new dataset",
    )


# ---------------------------------------------------------------------------
# Detected-issues schema (inspection, no changes)
# ---------------------------------------------------------------------------

class ColumnIssue(BaseModel):
    """Issues detected in a single column."""
    column: str
    dtype: str
    missing_count: int
    missing_pct: float
    has_whitespace_issues: bool
    unique_values: int
    is_likely_date: bool
    inconsistent_date_formats: list[str]
    sample_bad_values: list[Any]


class DatasetIssueReport(BaseModel):
    """
    Full pre-cleaning inspection report for a dataset.

    Attributes:
        dataset_id (str):     Source dataset.
        total_rows (int):     Total row count.
        total_columns (int):  Total column count.
        duplicate_rows (int): Number of exact duplicate rows.
        empty_columns (list): Column names that are 100 % empty.
        columns (list):       Per-column issue breakdown.
        summary (dict):       High-level counts for quick scan.
    """
    dataset_id: str
    total_rows: int
    total_columns: int
    duplicate_rows: int
    empty_columns: list[str]
    columns: list[ColumnIssue]
    summary: dict[str, Any]


# ---------------------------------------------------------------------------
# Cleaning action log
# ---------------------------------------------------------------------------

class CleaningAction(BaseModel):
    """
    A single atomic cleaning action that was executed.

    Attributes:
        operation (str):     Name of the cleaning operation.
        target (str):        Column name or 'dataset' for row-level ops.
        description (str):   Human-readable description of what changed.
        before_value (Any):  Relevant metric BEFORE the operation.
        after_value (Any):   Relevant metric AFTER the operation.
        rows_affected (int): Number of rows modified/removed.
    """
    operation: str
    target: str
    description: str
    before_value: Any = None
    after_value: Any = None
    rows_affected: int = 0


class CleaningReport(BaseModel):
    """
    Full report returned after applying cleaning operations to a dataset.

    Attributes:
        source_dataset_id (str):  Original dataset UUID.
        cleaned_dataset_id (str | None):
            UUID of the persisted cleaned dataset (None if save_cleaned=False).
        original_shape (tuple):   (rows, columns) before cleaning.
        cleaned_shape (tuple):    (rows, columns) after cleaning.
        actions (list):           Ordered log of every action taken.
        skipped_operations (list):Operations requested but skipped (with reason).
        warnings (list):          Non-fatal issues encountered.
        total_actions (int):      Count of actions performed.
    """
    source_dataset_id: str
    cleaned_dataset_id: str | None = None
    original_shape: tuple[int, int]
    cleaned_shape: tuple[int, int]
    actions: list[CleaningAction] = Field(default_factory=list)
    skipped_operations: list[dict[str, str]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    total_actions: int = 0
