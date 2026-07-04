"""
DataInsight API — Outlier Detection Schemas
============================================
Pydantic models for the outlier detection engine.

Hierarchy:
    OutlierDetectionRequest    → caller configuration (method, thresholds, columns)
    ColumnOutlierResult        → per-column detection outcome
    OutlierDetectionReport     → top-level response (all columns + chart info)
    MethodCatalogEntry         → describes a registered detection strategy
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Detection method enum — single source of truth for valid method names
# ---------------------------------------------------------------------------

class OutlierMethod(str, Enum):
    """Supported outlier detection algorithms."""
    IQR               = "iqr"
    ZSCORE            = "zscore"
    ISOLATION_FOREST  = "isolation_forest"


# ---------------------------------------------------------------------------
# Request
# ---------------------------------------------------------------------------

class IQRConfig(BaseModel):
    """
    Parameters for the IQR (Tukey fence) detection method.

    Attributes:
        multiplier: Fence multiplier applied to the IQR.
                    Standard Tukey inner fence = 1.5.
                    Outer fence (extreme outliers) = 3.0.
    """
    multiplier: float = Field(
        default=1.5,
        gt=0,
        description="IQR multiplier for fence calculation (default 1.5 = Tukey inner fence)",
    )


class ZScoreConfig(BaseModel):
    """
    Parameters for the Z-score detection method.

    Attributes:
        threshold: Absolute Z-score value above which a point is an outlier.
                   Standard threshold = 3.0 (≈ 0.3% of a normal distribution).
        use_modified: If True, use the Modified Z-Score (median-based) which
                      is more robust to non-Gaussian distributions.
    """
    threshold: float = Field(
        default=3.0,
        gt=0,
        description="Z-score threshold above which a value is flagged as an outlier",
    )
    use_modified: bool = Field(
        default=False,
        description=(
            "If True, use the modified Z-score (MAD-based), which is robust "
            "to non-Gaussian distributions and existing outliers"
        ),
    )


class IsolationForestConfig(BaseModel):
    """
    Parameters for the Isolation Forest detection method.

    Attributes:
        contamination: Expected proportion of outliers in the dataset (0–0.5).
        n_estimators:  Number of isolation trees in the ensemble.
        max_samples:   Number of samples per tree ('auto' or integer).
        random_state:  Seed for reproducibility.
        multivariate:  If True, fit on all numeric columns together (joint
                       outliers).  If False, fit on each column independently.
    """
    contamination: float = Field(
        default=0.05,
        gt=0,
        lt=0.5,
        description="Expected fraction of outliers (0–0.5)",
    )
    n_estimators: int = Field(
        default=100,
        ge=10,
        le=1000,
        description="Number of isolation trees",
    )
    random_state: int = Field(
        default=42,
        description="Random seed for reproducibility",
    )
    multivariate: bool = Field(
        default=False,
        description=(
            "True → fit on all numeric columns jointly (detects joint outliers). "
            "False → fit each column independently."
        ),
    )


class OutlierDetectionRequest(BaseModel):
    """
    Caller configuration for an outlier detection run.

    Attributes:
        method:            Detection algorithm to use.
        columns:           Specific numeric columns to analyse (empty = all).
        iqr:               IQR method configuration.
        zscore:            Z-score method configuration.
        isolation_forest:  Isolation Forest configuration.
        generate_boxplots: Whether to build and export boxplot PNGs.
        max_outlier_values: Maximum number of raw outlier values to include
                            per column in the response (avoids huge payloads).
    """
    method: OutlierMethod = Field(
        default=OutlierMethod.IQR,
        description="Detection algorithm: 'iqr', 'zscore', or 'isolation_forest'",
    )
    columns: list[str] = Field(
        default_factory=list,
        description="Columns to analyse (empty = all numeric columns)",
    )
    iqr: IQRConfig = Field(default_factory=IQRConfig)
    zscore: ZScoreConfig = Field(default_factory=ZScoreConfig)
    isolation_forest: IsolationForestConfig = Field(
        default_factory=IsolationForestConfig
    )
    generate_boxplots: bool = Field(
        default=True,
        description="Generate and export boxplot PNG for each numeric column",
    )
    max_outlier_values: int = Field(
        default=20,
        ge=1,
        le=200,
        description="Max raw outlier values to include per column in JSON response",
    )


# ---------------------------------------------------------------------------
# Per-column result
# ---------------------------------------------------------------------------

class ColumnOutlierResult(BaseModel):
    """
    Outlier detection results for a single numeric column.

    Attributes:
        column:         Column name.
        dtype:          Pandas dtype string.
        total_count:    Total rows (including NaN).
        valid_count:    Non-NaN rows used for detection.
        outlier_count:  Number of detected outliers.
        outlier_pct:    Percentage of valid values flagged as outliers.
        outlier_indices: Row indices (0-based) of detected outliers.
        outlier_values:  Actual outlier values (capped at max_outlier_values).
        lower_bound:    Lower boundary below which values are outliers (IQR/Z).
        upper_bound:    Upper boundary above which values are outliers (IQR/Z).
        method_params:  Method-specific parameters used for this column.
        stats:          Basic descriptive stats for context (Q1, Q3, mean, std).
    """
    column: str
    dtype: str
    total_count: int
    valid_count: int
    outlier_count: int
    outlier_pct: float
    outlier_indices: list[int] = Field(default_factory=list)
    outlier_values: list[float] = Field(default_factory=list)
    lower_bound: float | None = None
    upper_bound: float | None = None
    method_params: dict[str, Any] = Field(default_factory=dict)
    stats: dict[str, float | None] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Chart info
# ---------------------------------------------------------------------------

class BoxplotChartInfo(BaseModel):
    """Metadata about the generated boxplot PNG."""
    chart_path: str
    chart_filename: str
    chart_url: str
    width_px: int
    height_px: int
    file_size_kb: float
    columns_plotted: int


# ---------------------------------------------------------------------------
# Top-level report
# ---------------------------------------------------------------------------

class OutlierDetectionReport(BaseModel):
    """
    Full outlier detection report for a dataset.

    Attributes:
        dataset_id:           Source dataset UUID.
        method:               Detection method used.
        total_rows:           Total dataset rows.
        columns_analysed:     Number of numeric columns examined.
        total_outlier_rows:   Unique rows flagged in at least one column.
        total_outlier_cells:  Sum of outliers across all columns.
        affected_columns:     Column names with at least one outlier.
        affected_row_indices: Unique row indices flagged across all columns.
        column_results:       Per-column ColumnOutlierResult map.
        chart:                Boxplot chart metadata (None if not generated).
        warnings:             Non-fatal issues encountered.
        elapsed_ms:           Wall-clock time for the analysis.
    """
    dataset_id: str
    method: str
    total_rows: int
    columns_analysed: int
    total_outlier_rows: int
    total_outlier_cells: int
    affected_columns: list[str]
    affected_row_indices: list[int]
    column_results: dict[str, ColumnOutlierResult]
    chart: BoxplotChartInfo | None = None
    warnings: list[str] = Field(default_factory=list)
    elapsed_ms: float


# ---------------------------------------------------------------------------
# Method catalogue entry
# ---------------------------------------------------------------------------

class MethodCatalogEntry(BaseModel):
    """Human-readable description of a registered detection strategy."""
    name: str
    description: str
    parameters: dict[str, str]
    when_to_use: str
    limitations: str
