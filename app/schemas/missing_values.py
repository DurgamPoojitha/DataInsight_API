"""
DataInsight API — Missing Values Analysis Schemas
===================================================
Pydantic models for the missing-values detection and visualisation endpoint.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Per-column result
# ---------------------------------------------------------------------------

class ColumnMissingInfo(BaseModel):
    """Missing-value statistics for a single column."""

    column: str = Field(description="Column name")
    dtype: str = Field(description="Pandas dtype string")
    total_count: int = Field(description="Total number of rows")
    missing_count: int = Field(description="Number of missing (NaN/None) values")
    missing_pct: float = Field(description="Percentage of missing values (0–100)")
    present_count: int = Field(description="Number of non-missing values")
    present_pct: float = Field(description="Percentage of present values (0–100)")
    severity: str = Field(
        description=(
            "Severity label based on missing percentage: "
            "'none' (0%), 'low' (<5%), 'moderate' (5–20%), "
            "'high' (20–50%), 'critical' (>50%)"
        )
    )


# ---------------------------------------------------------------------------
# Dataset-level summary
# ---------------------------------------------------------------------------

class MissingValuesSummary(BaseModel):
    """Aggregated missing-values summary across the entire dataset."""

    total_rows: int = Field(description="Total rows in the dataset")
    total_columns: int = Field(description="Total columns in the dataset")
    total_cells: int = Field(description="Total cells (rows × columns)")
    total_missing_cells: int = Field(description="Total missing cells across all columns")
    overall_missing_pct: float = Field(description="Overall missing percentage (0–100)")

    columns_with_missing: int = Field(description="Number of columns that have at least one missing value")
    columns_fully_missing: list[str] = Field(
        default_factory=list,
        description="Column names that are 100% missing (entirely empty)",
    )
    columns_above_50pct: list[str] = Field(
        default_factory=list,
        description="Column names with > 50% missing values (critical)",
    )
    columns_above_20pct: list[str] = Field(
        default_factory=list,
        description="Column names with 20–50% missing values (high)",
    )
    columns_above_5pct: list[str] = Field(
        default_factory=list,
        description="Column names with 5–20% missing values (moderate)",
    )
    columns_below_5pct: list[str] = Field(
        default_factory=list,
        description="Column names with 0–5% missing values (low)",
    )
    complete_columns: list[str] = Field(
        default_factory=list,
        description="Column names with zero missing values",
    )


# ---------------------------------------------------------------------------
# Chart metadata
# ---------------------------------------------------------------------------

class ChartInfo(BaseModel):
    """Metadata about the generated missing-values bar chart."""

    chart_path: str = Field(description="Absolute path to the saved PNG file")
    chart_filename: str = Field(description="PNG filename only (for download)")
    chart_url: str = Field(description="API URL to download the chart")
    width_px: int = Field(description="Chart width in pixels")
    height_px: int = Field(description="Chart height in pixels")
    file_size_kb: float = Field(description="File size in kilobytes")


# ---------------------------------------------------------------------------
# Top-level response
# ---------------------------------------------------------------------------

class MissingValuesReport(BaseModel):
    """
    Full missing-values analysis report for a dataset.

    Returned by POST /api/v1/missing-values/analyse/{dataset_id}.

    Attributes:
        dataset_id:    Source dataset UUID.
        summary:       Dataset-level aggregated statistics.
        columns:       Per-column missing-value breakdown (all columns).
        affected_columns: Only columns that have at least one missing value.
        chart:         Metadata about the generated bar chart PNG.
    """

    dataset_id: str
    summary: MissingValuesSummary
    columns: list[ColumnMissingInfo] = Field(
        description="All columns (sorted by missing_pct descending)"
    )
    affected_columns: list[ColumnMissingInfo] = Field(
        description="Only columns that have ≥ 1 missing value"
    )
    chart: ChartInfo
