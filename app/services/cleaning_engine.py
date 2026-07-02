"""
DataInsight API — Data Cleaning Engine
==========================================
A production-quality, extensible data cleaning engine built around the
**Strategy design pattern**.

Architecture:
┌─────────────────────────────────────────────────────────────────────────┐
│                        DataCleaningEngine                               │
│  ┌──────────────────┐   ┌──────────────────────────────────────────┐    │
│  │ IssueDetector    │   │  CleaningPipeline (ordered strategies)   │    │
│  │ (read-only scan) │   │  ┌─────────────────────────────────────┐ │    │
│  └──────────────────┘   │  │ 1. DropHighMissingColumnsStrategy   │ │    │
│                          │  │ 2. DuplicateRemovalStrategy         │ │    │
│                          │  │ 3. MissingValueFillStrategy         │ │    │
│                          │  │ 4. StringNormalisationStrategy      │ │    │
│                          │  │ 5. DateConversionStrategy           │ │    │
│                          │  └─────────────────────────────────────┘ │    │
│                          └──────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────┘

SOLID Principles Applied:
  S — Each class has one job (detect, or apply one specific cleaning op).
  O — New strategies can be added by subclassing CleaningStrategy without
      modifying DataCleaningEngine.
  L — All strategies are interchangeable via the CleaningStrategy interface.
  I — CleaningStrategy exposes only `apply()` and `name`.
  D — DataCleaningEngine depends on the CleaningStrategy abstraction.

Extensibility:
  To add a new cleaning technique:
    1. Subclass CleaningStrategy.
    2. Implement `apply(df, report)` → pd.DataFrame.
    3. Register an instance in DataCleaningEngine._build_pipeline().
"""

from __future__ import annotations

import io
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd

from app.schemas.cleaning import (
    CleaningAction,
    CleaningReport,
    CleaningRequest,
    DatasetIssueReport,
    ColumnIssue,
    DateConversionConfig,
    DateFormatHint,
    DropColumnConfig,
    FillStrategy,
    MissingValueConfig,
    StringNormConfig,
)
from app.utils.data_utils import (
    column_has_whitespace_issues,
    compute_missing_stats,
    count_duplicate_rows,
    detect_date_formats_in_column,
    find_empty_columns,
    infer_column_type_label,
    is_likely_date_column,
    get_sample_bad_values,
    safe_scalar,
    _is_string_like_dtype,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)


# ===========================================================================
# Cleaning Strategy — Abstract Base Class
# ===========================================================================

class CleaningStrategy(ABC):
    """
    Abstract base class for all data cleaning strategies.

    Each subclass encapsulates a single, focused cleaning operation.
    The engine calls `apply()` in a deterministic order and accumulates
    CleaningAction records in the shared CleaningReport.

    To add a new technique:
        class MyCustomStrategy(CleaningStrategy):
            @property
            def name(self) -> str:
                return "my_custom_operation"

            def apply(self, df: pd.DataFrame, report: CleaningReport) -> pd.DataFrame:
                # mutate df, append to report.actions, return df
                ...
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique, machine-readable name for this strategy."""
        ...

    @abstractmethod
    def apply(self, df: pd.DataFrame, report: CleaningReport) -> pd.DataFrame:
        """
        Apply the cleaning operation to the DataFrame in-place or by copy.

        Args:
            df:     The DataFrame to clean.
            report: Shared CleaningReport to append CleaningAction records to.

        Returns:
            The (possibly modified) DataFrame.
        """
        ...

    # ------------------------------------------------------------------
    # Shared helper
    # ------------------------------------------------------------------

    def _log_action(
        self,
        report: CleaningReport,
        target: str,
        description: str,
        before_value: Any = None,
        after_value: Any = None,
        rows_affected: int = 0,
    ) -> None:
        """
        Append a CleaningAction to the shared report and log it.

        Args:
            report:        The shared CleaningReport instance.
            target:        Column name or 'dataset' for row-level ops.
            description:   Human-readable summary of the change.
            before_value:  Metric before the operation.
            after_value:   Metric after the operation.
            rows_affected: Number of rows changed/removed.
        """
        action = CleaningAction(
            operation=self.name,
            target=target,
            description=description,
            before_value=safe_scalar(before_value),
            after_value=safe_scalar(after_value),
            rows_affected=rows_affected,
        )
        report.actions.append(action)
        report.total_actions += 1
        logger.info(
            f"[{self.name}] {description}",
            target=target,
            rows_affected=rows_affected,
        )


# ===========================================================================
# Strategy 1 — Drop High-Missing Columns
# ===========================================================================

class DropHighMissingColumnsStrategy(CleaningStrategy):
    """
    Drop columns where the fraction of missing values exceeds `threshold`.

    Example: threshold=0.5 drops any column with > 50 % missing values.
    Empty columns (100 % missing) are always included.
    """

    def __init__(self, config: DropColumnConfig) -> None:
        self._config = config

    @property
    def name(self) -> str:
        return "drop_high_missing_columns"

    def apply(self, df: pd.DataFrame, report: CleaningReport) -> pd.DataFrame:
        total_rows: int = len(df)
        if total_rows == 0:
            return df

        cols_to_drop: list[str] = []
        for col in df.columns:
            missing_frac: float = df[col].isna().sum() / total_rows
            if missing_frac > self._config.threshold:
                cols_to_drop.append(col)

        if not cols_to_drop:
            logger.info("No columns exceeded the missing-value threshold")
            return df

        df = df.drop(columns=cols_to_drop)

        for col in cols_to_drop:
            self._log_action(
                report=report,
                target=col,
                description=(
                    f"Column '{col}' dropped: missing fraction exceeded "
                    f"{self._config.threshold:.0%} threshold."
                ),
                before_value=col,
                after_value="<dropped>",
            )

        return df


# ===========================================================================
# Strategy 2 — Duplicate Row Removal
# ===========================================================================

class DuplicateRemovalStrategy(CleaningStrategy):
    """
    Remove exact duplicate rows, keeping the first occurrence of each.
    Reports the number of rows removed.
    """

    @property
    def name(self) -> str:
        return "remove_duplicates"

    def apply(self, df: pd.DataFrame, report: CleaningReport) -> pd.DataFrame:
        before: int = len(df)
        df = df.drop_duplicates(keep="first").reset_index(drop=True)
        removed: int = before - len(df)

        if removed > 0:
            self._log_action(
                report=report,
                target="dataset",
                description=f"Removed {removed} duplicate row(s). {len(df)} row(s) remain.",
                before_value=before,
                after_value=len(df),
                rows_affected=removed,
            )
        else:
            logger.info("No duplicate rows found")

        return df


# ===========================================================================
# Strategy 3 — Missing Value Imputation
# ===========================================================================

class MissingValueFillStrategy(CleaningStrategy):
    """
    Impute missing values using one of several strategies.

    Numeric columns:  mean / median / mode / zero / ffill / bfill / custom
    String columns:   use config.string_fill value (if provided)

    Per-column custom values in config.custom_values always take priority
    over the global strategy for that specific column.
    """

    def __init__(self, config: MissingValueConfig) -> None:
        self._config = config

    @property
    def name(self) -> str:
        return "fill_missing_values"

    def apply(self, df: pd.DataFrame, report: CleaningReport) -> pd.DataFrame:
        target_cols: list[str] = (
            self._config.apply_to_columns
            if self._config.apply_to_columns
            else list(df.columns)
        )

        for col in target_cols:
            if col not in df.columns:
                report.warnings.append(
                    f"fill_missing: column '{col}' not found — skipped."
                )
                continue

            missing_before: int = int(df[col].isna().sum())
            if missing_before == 0:
                continue

            fill_value: Any = self._resolve_fill_value(df, col)

            if fill_value is None:
                logger.info(f"No fill value resolved for column '{col}' — skipped")
                continue

            # Apply fill (ffill/bfill are series methods, not scalar fills)
            if self._config.strategy in (FillStrategy.FFILL, FillStrategy.BFILL):
                method: str = (
                    "ffill"
                    if self._config.strategy == FillStrategy.FFILL
                    else "bfill"
                )
                df[col] = df[col].ffill() if method == "ffill" else df[col].bfill()
            else:
                df[col] = df[col].fillna(fill_value)

            filled: int = missing_before - int(df[col].isna().sum())

            self._log_action(
                report=report,
                target=col,
                description=(
                    f"Filled {filled} missing value(s) in '{col}' "
                    f"using strategy='{self._config.strategy.value}' "
                    f"(fill_value={repr(fill_value)})."
                ),
                before_value=missing_before,
                after_value=int(df[col].isna().sum()),
                rows_affected=filled,
            )

        return df

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _resolve_fill_value(self, df: pd.DataFrame, col: str) -> Any:
        """
        Determine the fill value for a given column.

        Priority order:
          1. Per-column custom override (config.custom_values[col])
          2. Global strategy (mean/median/mode/zero/ffill/bfill)
          3. string_fill for object columns

        Returns None if no appropriate fill value can be determined.
        """
        series: pd.Series = df[col]

        # 1. Per-column custom override always wins
        if col in self._config.custom_values:
            return self._config.custom_values[col]

        is_numeric: bool = pd.api.types.is_numeric_dtype(series)
        is_string:  bool = pd.api.types.is_object_dtype(series)

        # 2. Global numeric strategy
        if is_numeric:
            non_null = series.dropna()
            if non_null.empty:
                return None

            strategy = self._config.strategy
            if strategy == FillStrategy.MEAN:
                return safe_scalar(non_null.mean())
            if strategy == FillStrategy.MEDIAN:
                return safe_scalar(non_null.median())
            if strategy == FillStrategy.MODE:
                mode_vals = non_null.mode()
                return safe_scalar(mode_vals.iloc[0]) if not mode_vals.empty else None
            if strategy == FillStrategy.ZERO:
                return 0
            if strategy in (FillStrategy.FFILL, FillStrategy.BFILL):
                return FillStrategy.FFILL  # sentinel — actual fill handled above

        # 3. String columns
        if is_string and self._config.string_fill is not None:
            return self._config.string_fill

        return None


# ===========================================================================
# Strategy 4 — String Normalisation
# ===========================================================================

class StringNormalisationStrategy(CleaningStrategy):
    """
    Clean string columns by:
      - Stripping leading/trailing whitespace (default: on)
      - Converting to lowercase (default: off)

    Operates only on object (string) dtype columns.
    """

    def __init__(self, config: StringNormConfig) -> None:
        self._config = config

    @property
    def name(self) -> str:
        return "normalize_strings"

    def apply(self, df: pd.DataFrame, report: CleaningReport) -> pd.DataFrame:
        # Determine which columns to process
        if self._config.apply_to_columns:
            target_cols = [
                c for c in self._config.apply_to_columns if c in df.columns
            ]
        else:
            # Default: all object/string columns (covers both pandas <3 and >=3)
            target_cols = [
                c for c in df.columns
                if _is_string_like_dtype(df[c])
            ]

        for col in target_cols:
            series: pd.Series = df[col]
            if not _is_string_like_dtype(series):
                report.warnings.append(
                    f"normalize_strings: '{col}' is not a string column — skipped."
                )
                continue

            original: pd.Series = series.copy()
            modified: pd.Series = series.copy()

            if self._config.strip_whitespace:
                modified = modified.str.strip()

            if self._config.lowercase:
                modified = modified.str.lower()

            changed_mask: pd.Series = (
                (original != modified) & original.notna() & modified.notna()
            )
            rows_changed: int = int(changed_mask.sum())

            if rows_changed > 0:
                df[col] = modified
                ops: list[str] = []
                if self._config.strip_whitespace:
                    ops.append("strip whitespace")
                if self._config.lowercase:
                    ops.append("lowercase")

                self._log_action(
                    report=report,
                    target=col,
                    description=(
                        f"Normalised {rows_changed} value(s) in '{col}': "
                        + ", ".join(ops) + "."
                    ),
                    before_value=rows_changed,
                    after_value=0,
                    rows_affected=rows_changed,
                )

        return df


# ===========================================================================
# Strategy 5 — Date Conversion
# ===========================================================================

class DateConversionStrategy(CleaningStrategy):
    """
    Parse string columns that contain date values into pandas datetime64.

    Behaviour:
      - If config.columns is specified, only those columns are processed.
      - Otherwise, auto-detect likely date columns using is_likely_date_column().
      - Already datetime64 columns are skipped (logged as no-op).
      - Bad values are coerced to NaT when config.errors='coerce'.
    """

    def __init__(self, config: DateConversionConfig) -> None:
        self._config = config

    @property
    def name(self) -> str:
        return "convert_dates"

    def apply(self, df: pd.DataFrame, report: CleaningReport) -> pd.DataFrame:
        # Resolve which columns to attempt
        if self._config.columns:
            target_cols: list[str] = [
                c for c in self._config.columns if c in df.columns
            ]
            for missing in self._config.columns:
                if missing not in df.columns:
                    report.warnings.append(
                        f"convert_dates: column '{missing}' not found — skipped."
                    )
        else:
            # Auto-detect: look for string columns that look like dates
            target_cols = [
                c for c in df.columns
                if _is_string_like_dtype(df[c])
                and is_likely_date_column(df[c])
            ]

        for col in target_cols:
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                logger.info(f"Column '{col}' is already datetime — skipped")
                continue

            original_dtype: str = str(df[col].dtype)
            null_before: int = int(df[col].isna().sum())

            try:
                if self._config.format_hint == DateFormatHint.AUTO:
                    converted = pd.to_datetime(
                        df[col],
                        errors=self._config.errors,
                        format="mixed",
                        dayfirst=False,
                    )
                else:
                    converted = pd.to_datetime(
                        df[col],
                        format=self._config.format_hint.value,
                        errors=self._config.errors,
                    )

                null_after: int = int(converted.isna().sum())
                newly_null: int = null_after - null_before
                successful: int = int(converted.notna().sum()) - int(
                    pd.to_datetime(df[col], errors="coerce").notna().sum()
                    if null_before == 0
                    else max(0, len(df) - null_before - newly_null)
                )

                df[col] = converted

                self._log_action(
                    report=report,
                    target=col,
                    description=(
                        f"Converted '{col}' from {original_dtype} to datetime64. "
                        f"Format hint: {self._config.format_hint.value}. "
                        + (
                            f"{newly_null} value(s) could not be parsed (→ NaT)."
                            if newly_null > 0
                            else "All values parsed successfully."
                        )
                    ),
                    before_value=original_dtype,
                    after_value="datetime64[ns]",
                    rows_affected=len(df) - null_before,
                )

            except Exception as exc:
                report.warnings.append(
                    f"convert_dates: failed to convert '{col}': {exc}"
                )

        return df


# ===========================================================================
# Issue Detector (read-only, no mutations)
# ===========================================================================

class IssueDetector:
    """
    Performs a comprehensive, non-destructive inspection of a DataFrame
    and produces a DatasetIssueReport.

    This class only READS the data — it never mutates the DataFrame.
    """

    def inspect(self, df: pd.DataFrame, dataset_id: str) -> DatasetIssueReport:
        """
        Scan the DataFrame and build a full DatasetIssueReport.

        Args:
            df:         The DataFrame to inspect.
            dataset_id: UUID of the source dataset (for report identification).

        Returns:
            A DatasetIssueReport with per-column and summary-level findings.
        """
        logger.info("Starting dataset inspection", dataset_id=dataset_id)

        missing_stats = compute_missing_stats(df)
        empty_cols    = find_empty_columns(df)
        dup_count     = count_duplicate_rows(df)
        column_issues: list[ColumnIssue] = []

        for col in df.columns:
            series: pd.Series = df[col]
            m_count: int   = missing_stats[col]["count"]
            m_pct: float   = missing_stats[col]["pct"]
            ws_issues: bool = column_has_whitespace_issues(series)
            likely_date: bool = is_likely_date_column(series)
            date_formats: list[str] = (
                detect_date_formats_in_column(series)
                if pd.api.types.is_object_dtype(series)
                else []
            )
            sample_bad = get_sample_bad_values(series, n=5)

            column_issues.append(
                ColumnIssue(
                    column=col,
                    dtype=str(series.dtype),
                    missing_count=m_count,
                    missing_pct=m_pct,
                    has_whitespace_issues=ws_issues,
                    unique_values=int(series.nunique(dropna=True)),
                    is_likely_date=likely_date,
                    inconsistent_date_formats=date_formats,
                    sample_bad_values=sample_bad,
                )
            )

        # Columns that mix date formats (more than one format detected)
        ambiguous_date_cols = [
            c.column for c in column_issues
            if len(c.inconsistent_date_formats) > 1
        ]

        summary: dict[str, Any] = {
            "total_missing_cells": int(df.isna().sum().sum()),
            "missing_pct_overall": round(
                df.isna().sum().sum() / max(df.size, 1) * 100, 2
            ),
            "duplicate_rows": dup_count,
            "empty_columns": len(empty_cols),
            "columns_with_whitespace_issues": sum(
                1 for c in column_issues if c.has_whitespace_issues
            ),
            "likely_date_columns": sum(
                1 for c in column_issues if c.is_likely_date
            ),
            "ambiguous_date_columns": ambiguous_date_cols,
            "columns_above_50pct_missing": [
                c.column for c in column_issues if c.missing_pct > 50.0
            ],
        }

        logger.info(
            "Inspection complete",
            dataset_id=dataset_id,
            issues=summary["total_missing_cells"],
            duplicates=dup_count,
        )

        return DatasetIssueReport(
            dataset_id=dataset_id,
            total_rows=len(df),
            total_columns=len(df.columns),
            duplicate_rows=dup_count,
            empty_columns=empty_cols,
            columns=column_issues,
            summary=summary,
        )


# ===========================================================================
# Cleaning Pipeline
# ===========================================================================

class CleaningPipeline:
    """
    An ordered list of CleaningStrategy instances.

    Iterates through each strategy in sequence, passing the DataFrame and
    the shared CleaningReport.  Any strategy can be inserted, removed, or
    reordered without modifying this class.
    """

    def __init__(self, strategies: list[CleaningStrategy]) -> None:
        """
        Args:
            strategies: Ordered list of CleaningStrategy instances to execute.
        """
        self._strategies: list[CleaningStrategy] = strategies

    def run(self, df: pd.DataFrame, report: CleaningReport) -> pd.DataFrame:
        """
        Execute all strategies in order, threading the DataFrame through.

        Args:
            df:     Input DataFrame.
            report: Shared report to accumulate actions in.

        Returns:
            The fully cleaned DataFrame.
        """
        for strategy in self._strategies:
            logger.info(f"Running strategy: {strategy.name}")
            df = strategy.apply(df, report)
        return df

    def add_strategy(self, strategy: CleaningStrategy, index: int | None = None) -> None:
        """
        Register a new strategy at a given position (default: append to end).

        This is the primary extensibility hook — callers can add custom
        strategies without subclassing DataCleaningEngine.

        Args:
            strategy: A CleaningStrategy instance.
            index:    Position to insert at (None = append).
        """
        if index is None:
            self._strategies.append(strategy)
        else:
            self._strategies.insert(index, strategy)


# ===========================================================================
# DataCleaningEngine — Top-Level Orchestrator
# ===========================================================================

class DataCleaningEngine:
    """
    Orchestrates the full data cleaning lifecycle:
      1. Build a CleaningPipeline from the caller's CleaningRequest.
      2. Run the pipeline, producing a cleaned DataFrame.
      3. Optionally persist the cleaned data as a new dataset.
      4. Return a comprehensive CleaningReport.

    Usage:
        engine = DataCleaningEngine(dataset_service=service)
        report = engine.clean(dataset_id="abc-123", request=CleaningRequest(...))

    Extensibility:
        engine.pipeline.add_strategy(MyCustomStrategy())
    """

    def __init__(self, dataset_service: Any) -> None:
        """
        Args:
            dataset_service: An instance of DatasetService, used to load
                             DataFrames and (optionally) save cleaned data.
        """
        self._dataset_service = dataset_service
        # Pipeline is built fresh per request (no shared mutable state)
        self.pipeline: CleaningPipeline | None = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def inspect(self, dataset_id: str) -> DatasetIssueReport:
        """
        Perform a read-only inspection of a dataset and return an issue report.

        Args:
            dataset_id: UUID of the dataset to inspect.

        Returns:
            DatasetIssueReport with detected issues and per-column breakdown.
        """
        df: pd.DataFrame = self._dataset_service.load_dataframe(dataset_id)
        detector = IssueDetector()
        return detector.inspect(df, dataset_id)

    def clean(
        self,
        dataset_id: str,
        request: CleaningRequest,
    ) -> CleaningReport:
        """
        Apply the requested cleaning operations and return a full report.

        Pipeline execution order (regardless of request field order):
          1. drop_high_missing_columns
          2. remove_duplicates
          3. fill_missing_values
          4. normalize_strings
          5. convert_dates

        Args:
            dataset_id: UUID of the source dataset.
            request:    CleaningRequest specifying which operations to run.

        Returns:
            CleaningReport with all actions, shape changes, and warnings.
        """
        df: pd.DataFrame = self._dataset_service.load_dataframe(dataset_id)

        original_shape: tuple[int, int] = df.shape

        # Initialise the shared report
        report = CleaningReport(
            source_dataset_id=dataset_id,
            original_shape=original_shape,
            cleaned_shape=original_shape,  # updated after cleaning
        )

        # Build and run the pipeline
        strategies = self._build_pipeline(request, report)
        self.pipeline = CleaningPipeline(strategies)
        df = self.pipeline.run(df, report)

        # Update final shape
        report.cleaned_shape = df.shape

        # Optionally save the cleaned data as a new dataset
        if request.save_cleaned:
            cleaned_id: str | None = self._persist_cleaned(
                df=df,
                source_dataset_id=dataset_id,
                report=report,
            )
            report.cleaned_dataset_id = cleaned_id

        logger.info(
            "Cleaning complete",
            source_id=dataset_id,
            actions=report.total_actions,
            original_shape=str(original_shape),
            cleaned_shape=str(report.cleaned_shape),
        )

        return report

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_pipeline(
        self,
        request: CleaningRequest,
        report: CleaningReport,
    ) -> list[CleaningStrategy]:
        """
        Construct the ordered list of strategies from the CleaningRequest.

        Strategies are always applied in the canonical order defined here,
        regardless of the order fields appear in the request JSON.

        Args:
            request: The caller's cleaning configuration.
            report:  The shared report (used to record skipped operations).

        Returns:
            Ordered list of CleaningStrategy instances.
        """
        strategies: list[CleaningStrategy] = []

        # 1. Drop high-missing columns first (reduces problem size)
        if request.drop_high_missing_columns is not None:
            strategies.append(
                DropHighMissingColumnsStrategy(request.drop_high_missing_columns)
            )
        else:
            report.skipped_operations.append(
                {"operation": "drop_high_missing_columns", "reason": "not requested"}
            )

        # 2. Duplicate removal
        if request.remove_duplicates:
            strategies.append(DuplicateRemovalStrategy())
        else:
            report.skipped_operations.append(
                {"operation": "remove_duplicates", "reason": "not requested"}
            )

        # 3. Missing value imputation
        if request.fill_missing is not None:
            strategies.append(MissingValueFillStrategy(request.fill_missing))
        else:
            report.skipped_operations.append(
                {"operation": "fill_missing_values", "reason": "not requested"}
            )

        # 4. String normalisation
        if request.normalize_strings is not None:
            strategies.append(StringNormalisationStrategy(request.normalize_strings))
        else:
            report.skipped_operations.append(
                {"operation": "normalize_strings", "reason": "not requested"}
            )

        # 5. Date conversion (last — works on cleaned/normalised strings)
        if request.convert_dates is not None:
            strategies.append(DateConversionStrategy(request.convert_dates))
        else:
            report.skipped_operations.append(
                {"operation": "convert_dates", "reason": "not requested"}
            )

        return strategies

    def _persist_cleaned(
        self,
        df: pd.DataFrame,
        source_dataset_id: str,
        report: CleaningReport,
    ) -> str | None:
        """
        Serialise the cleaned DataFrame to CSV bytes and register it as a new
        dataset via DatasetService.

        The new dataset filename is prefixed with 'cleaned_' so users can
        distinguish it from the original upload.

        Args:
            df:                  The cleaned DataFrame.
            source_dataset_id:   UUID of the original dataset.
            report:              The shared report (warnings appended on failure).

        Returns:
            The UUID of the newly registered dataset, or None on failure.
        """
        try:
            # Retrieve original filename for the new dataset label
            original_meta = self._dataset_service.get_dataset(source_dataset_id)
            new_filename: str = f"cleaned_{original_meta.original_filename}"

            # Serialise to CSV bytes
            csv_buffer = io.StringIO()
            df.to_csv(csv_buffer, index=False)
            csv_bytes: bytes = csv_buffer.getvalue().encode("utf-8")

            # Register via DatasetService (handles UUID generation, disk write, metadata)
            new_meta = self._dataset_service.upload_csv(
                file_content=csv_bytes,
                original_filename=new_filename,
            )
            logger.info(
                "Cleaned dataset saved",
                cleaned_dataset_id=new_meta.dataset_id,
                rows=new_meta.row_count,
            )
            return new_meta.dataset_id

        except Exception as exc:
            report.warnings.append(
                f"Could not persist cleaned dataset: {exc}"
            )
            logger.warning("Failed to persist cleaned dataset", error=str(exc))
            return None
