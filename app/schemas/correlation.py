"""
DataInsight API — Correlation Analysis Schemas
==============================================
Pydantic models for the correlation analysis engine.

Hierarchy:
    CorrelationPair           → describes the correlation between two specific columns
    CorrelationMatrix         → full N×N matrix of correlation coefficients
    CorrelationChartInfo      → metadata for generated PNG and HTML heatmaps
    CorrelationReport         → top-level API response
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class CorrelationMethod(str, Enum):
    """Supported correlation algorithms."""
    PEARSON  = "pearson"   # linear relationship
    SPEARMAN = "spearman"  # monotonic relationship (rank-based)
    KENDALL  = "kendall"   # monotonic relationship (ordinal rank-based)


# ---------------------------------------------------------------------------
# Pairs and Matrix
# ---------------------------------------------------------------------------

class CorrelationPair(BaseModel):
    """Correlation details between two distinct features."""
    feature_x: str = Field(description="First feature name")
    feature_y: str = Field(description="Second feature name")
    correlation: float = Field(description="Correlation coefficient (-1.0 to 1.0)")
    strength: str = Field(
        description="Textual interpretation (e.g., 'Strong Positive', 'Weak Negative')"
    )


class CorrelationMatrix(BaseModel):
    """Full N×N correlation matrix representation."""
    features: list[str] = Field(description="List of feature names in matrix order")
    matrix: list[list[float | None]] = Field(
        description="2D array of correlation coefficients. None if undefined."
    )


# ---------------------------------------------------------------------------
# Chart Info
# ---------------------------------------------------------------------------

class CorrelationChartInfo(BaseModel):
    """Metadata about the generated heatmap charts."""
    png_path: str = Field(description="Absolute path to PNG file")
    png_url: str = Field(description="API URL to download PNG chart")
    html_path: str = Field(description="Absolute path to interactive HTML file")
    html_url: str = Field(description="API URL to download HTML chart")
    width_px: int
    height_px: int
    png_size_kb: float
    html_size_kb: float


# ---------------------------------------------------------------------------
# Top-level Request & Response
# ---------------------------------------------------------------------------

class CorrelationRequest(BaseModel):
    """Caller configuration for correlation analysis."""
    method: CorrelationMethod = Field(
        default=CorrelationMethod.PEARSON,
        description="Correlation algorithm to use",
    )
    columns: list[str] = Field(
        default_factory=list,
        description="Specific columns to correlate. Empty = all numeric columns.",
    )
    high_correlation_threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Absolute threshold to flag pairs as highly correlated",
    )
    generate_charts: bool = Field(
        default=True,
        description="If True, generate and export PNG and HTML heatmaps",
    )


class CorrelationReport(BaseModel):
    """
    Full correlation analysis report for a dataset.
    """
    dataset_id: str
    method: str
    columns_analysed: int
    matrix: CorrelationMatrix
    strongest_positive: CorrelationPair | None = Field(
        description="Pair with the highest positive correlation (< 1.0)"
    )
    strongest_negative: CorrelationPair | None = Field(
        description="Pair with the lowest negative correlation"
    )
    highly_correlated_pairs: list[CorrelationPair] = Field(
        description="Pairs exceeding the configured absolute threshold"
    )
    chart: CorrelationChartInfo | None = None
    warnings: list[str] = Field(default_factory=list)
    elapsed_ms: float
