"""
DataInsight API — Visualization Schemas
=======================================
Pydantic models for the general-purpose visualization engine.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class ChartType(str, Enum):
    HISTOGRAM = "histogram"
    BAR       = "bar"
    PIE       = "pie"
    SCATTER   = "scatter"
    LINE      = "line"
    BOX       = "box"
    HEATMAP   = "heatmap"


class ExportFormat(str, Enum):
    PNG  = "png"
    HTML = "html"
    BOTH = "both"


# ---------------------------------------------------------------------------
# Individual Chart Requests
# ---------------------------------------------------------------------------

class ChartRequest(BaseModel):
    """Base class for chart requests."""
    type: ChartType
    title: str | None = None


class HistogramRequest(ChartRequest):
    type: Literal[ChartType.HISTOGRAM] = ChartType.HISTOGRAM
    column: str = Field(description="Numeric column for distribution")
    bins: int | None = Field(default=None, description="Number of bins (optional)")


class BarChartRequest(ChartRequest):
    type: Literal[ChartType.BAR] = ChartType.BAR
    column: str = Field(description="Categorical column to count frequencies")
    top_k: int = Field(default=10, description="Show top K categories")


class PieChartRequest(ChartRequest):
    type: Literal[ChartType.PIE] = ChartType.PIE
    column: str = Field(description="Categorical column for proportions")
    top_k: int = Field(default=5, description="Show top K categories, group rest as 'Other'")


class ScatterPlotRequest(ChartRequest):
    type: Literal[ChartType.SCATTER] = ChartType.SCATTER
    x: str = Field(description="Numeric column for X axis")
    y: str = Field(description="Numeric column for Y axis")
    color_by: str | None = Field(default=None, description="Optional categorical column for color grouping")


class LineChartRequest(ChartRequest):
    type: Literal[ChartType.LINE] = ChartType.LINE
    x: str = Field(description="Column for X axis (often time/date or sorted index)")
    y: str = Field(description="Column for Y axis")
    sort_x: bool = Field(default=True, description="Sort data by X axis before plotting")


class BoxPlotRequest(ChartRequest):
    type: Literal[ChartType.BOX] = ChartType.BOX
    y: str = Field(description="Numeric column for distribution")
    x: str | None = Field(default=None, description="Optional categorical column to split boxes")


class CorrelationHeatmapRequest(ChartRequest):
    type: Literal[ChartType.HEATMAP] = ChartType.HEATMAP
    columns: list[str] = Field(
        default_factory=list,
        description="Numeric columns to include. Empty = all numeric."
    )


# ---------------------------------------------------------------------------
# Batch Request & Response
# ---------------------------------------------------------------------------

class VisualizationBatchRequest(BaseModel):
    """Request multiple visualizations to be generated at once."""
    charts: list[
        HistogramRequest
        | BarChartRequest
        | PieChartRequest
        | ScatterPlotRequest
        | LineChartRequest
        | BoxPlotRequest
        | CorrelationHeatmapRequest
    ] = Field(description="List of charts to generate")
    export_format: ExportFormat = Field(default=ExportFormat.BOTH)


class GeneratedChartInfo(BaseModel):
    """Metadata about a generated chart."""
    chart_id: str = Field(description="Unique identifier for this specific chart run")
    type: str
    png_url: str | None = None
    html_url: str | None = None
    error: str | None = None


class VisualizationBatchReport(BaseModel):
    """Result of a batch visualization generation."""
    dataset_id: str
    successful_charts: int
    failed_charts: int
    charts: list[GeneratedChartInfo]
    elapsed_ms: float
