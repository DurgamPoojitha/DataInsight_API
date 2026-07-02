"""
DataInsight API — Statistical Analysis Schemas
================================================
Pydantic models for the statistical analysis engine request and response
contracts.

Design:
  - AnalysisRequest   : caller specifies which columns to analyse + options
  - ColumnStatistics  : full descriptive stats for one numeric column
  - DatasetStatistics : top-level response wrapping all column stats
"""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Request
# ---------------------------------------------------------------------------

class AnalysisRequest(BaseModel):
    """
    Configuration for a statistical analysis run.

    Attributes:
        columns (list[str]):
            Specific column names to analyse.
            Empty list = analyse all numeric columns automatically.
        percentiles (list[float]):
            Additional percentile points (0–100) to compute beyond the fixed
            set (1, 5, 10, 25, 50, 75, 90, 95, 99).
            Values outside [0, 100] are silently clamped.
        include_frequency_table (bool):
            If True, include a value-frequency table for each column
            (top 10 most frequent values).  Can be expensive on high-cardinality
            columns; defaults to False.
        nan_policy (str):
            How to handle NaN values before computing statistics.
            'omit'  — drop NaN rows for each column independently (default).
            'zero'  — treat NaN as 0.
        large_dataset_threshold (int):
            Row count above which the engine switches to memory-efficient
            NumPy array processing instead of pandas Series operations.
            Default: 100_000.
    """
    columns: list[str] = Field(
        default_factory=list,
        description="Columns to analyse (empty = all numeric columns)",
    )
    percentiles: list[float] = Field(
        default_factory=list,
        description="Additional percentile points (0–100) beyond the default set",
    )
    include_frequency_table: bool = Field(
        default=False,
        description="Include top-10 value-frequency table per column",
    )
    nan_policy: str = Field(
        default="omit",
        description="'omit' (drop NaN) or 'zero' (treat NaN as 0)",
    )
    large_dataset_threshold: int = Field(
        default=100_000,
        ge=1,
        description="Row count above which NumPy fast-path is used",
    )


# ---------------------------------------------------------------------------
# Per-column statistics
# ---------------------------------------------------------------------------

class QuartileStats(BaseModel):
    """Quartile breakdown for a single column."""
    q1: float | None = Field(None, description="25th percentile (Q1)")
    q2: float | None = Field(None, description="50th percentile / median (Q2)")
    q3: float | None = Field(None, description="75th percentile (Q3)")
    iqr: float | None = Field(None, description="Interquartile range (Q3 – Q1)")


class OutlierStats(BaseModel):
    """IQR-based outlier bounds and counts."""
    lower_fence: float | None = Field(None, description="Q1 – 1.5 × IQR")
    upper_fence: float | None = Field(None, description="Q3 + 1.5 × IQR")
    outlier_count: int = Field(0, description="Number of values outside the fences")
    outlier_pct: float = Field(0.0, description="Percentage of values that are outliers")


class DistributionShape(BaseModel):
    """Measures describing the shape of the distribution."""
    skewness: float | None = Field(
        None,
        description=(
            "Fisher–Pearson skewness coefficient. "
            "Positive → right-skewed, Negative → left-skewed"
        ),
    )
    kurtosis: float | None = Field(
        None,
        description=(
            "Excess kurtosis (Fisher definition, normal = 0). "
            "Positive → leptokurtic (heavy tails), Negative → platykurtic"
        ),
    )
    skewness_interpretation: str = Field(
        "",
        description="Human-readable interpretation of the skewness value",
    )
    kurtosis_interpretation: str = Field(
        "",
        description="Human-readable interpretation of the kurtosis value",
    )


class ColumnStatistics(BaseModel):
    """
    Full descriptive statistics for a single numeric column.

    All float fields use None to indicate that computation was not possible
    (e.g. fewer than 2 non-NaN values for variance/std).
    """
    # Identity
    column: str = Field(description="Column name")
    dtype: str = Field(description="Original pandas dtype string")

    # Data quality
    total_count: int = Field(description="Total number of rows (including NaN)")
    valid_count: int = Field(description="Number of non-NaN values used in analysis")
    nan_count: int = Field(description="Number of NaN / missing values")
    nan_pct: float = Field(description="Percentage of NaN values (0–100)")

    # Central tendency
    mean: float | None = Field(None, description="Arithmetic mean of valid values")
    median: float | None = Field(None, description="50th percentile (median)")
    mode: list[float] = Field(
        default_factory=list,
        description="Mode(s) — one or more values that appear most frequently",
    )
    mode_count: int = Field(0, description="Number of modal values")

    # Spread
    minimum: float | None = Field(None, description="Minimum value")
    maximum: float | None = Field(None, description="Maximum value")
    range: float | None = Field(None, description="Maximum – Minimum")
    variance: float | None = Field(None, description="Sample variance (ddof=1)")
    std_dev: float | None = Field(None, description="Sample standard deviation (ddof=1)")
    coeff_of_variation: float | None = Field(
        None,
        description="Coefficient of variation (std_dev / |mean| × 100) as a percentage",
    )

    # Quartiles and IQR
    quartiles: QuartileStats = Field(default_factory=QuartileStats)

    # Percentiles (fixed + caller-requested)
    percentiles: dict[str, float | None] = Field(
        default_factory=dict,
        description="Percentile values keyed by 'p{N}' (e.g. p5, p25, p95)",
    )

    # Distribution shape
    distribution: DistributionShape = Field(default_factory=DistributionShape)

    # Outliers
    outliers: OutlierStats = Field(default_factory=OutlierStats)

    # Optional frequency table
    frequency_table: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Top-10 value-frequency pairs (only when include_frequency_table=True)",
    )

    # Unique values
    unique_count: int = Field(0, description="Number of distinct values")


# ---------------------------------------------------------------------------
# Dataset-level statistics
# ---------------------------------------------------------------------------

class PerformanceInfo(BaseModel):
    """Metadata about the analysis run's performance."""
    total_rows: int
    total_columns_analysed: int
    numeric_columns_found: int
    skipped_columns: list[str] = Field(default_factory=list)
    fast_path_used: bool = Field(
        description="True when the NumPy large-dataset fast path was used"
    )
    elapsed_ms: float = Field(description="Wall-clock time in milliseconds")


class DatasetStatistics(BaseModel):
    """
    Top-level response: statistical profiles for all requested numeric columns.

    Attributes:
        dataset_id (str):         Source dataset UUID.
        columns (dict):           Map of column_name → ColumnStatistics.
        performance (PerformanceInfo): Timing and execution metadata.
        warnings (list[str]):     Non-fatal issues (e.g. skipped columns).
    """
    dataset_id: str
    columns: dict[str, ColumnStatistics] = Field(default_factory=dict)
    performance: PerformanceInfo
    warnings: list[str] = Field(default_factory=list)
