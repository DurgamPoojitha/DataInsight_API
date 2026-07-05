"""
DataInsight API — Visualization Service
=======================================
Generates robust Plotly charts (Histogram, Bar, Pie, Scatter, Line, Box, Heatmap)
and exports them to HTML and PNG formats.
"""

from __future__ import annotations

import pathlib
import time
import uuid
from typing import Any

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from app.schemas.visualization import (
    BarChartRequest,
    BoxPlotRequest,
    ChartRequest,
    ChartType,
    CorrelationHeatmapRequest,
    ExportFormat,
    GeneratedChartInfo,
    HistogramRequest,
    LineChartRequest,
    PieChartRequest,
    ScatterPlotRequest,
    VisualizationBatchReport,
    VisualizationBatchRequest,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Theme Constants
# ---------------------------------------------------------------------------
_FONT_FAMILY   = "Inter, 'Helvetica Neue', Arial, sans-serif"
_BG_COLOR      = "#0f172a"   # slate-900
_PAPER_COLOR   = "#1e293b"   # slate-800
_GRID_COLOR    = "#334155"   # slate-600
_TEXT_COLOR    = "#e2e8f0"   # slate-200
_MUTED_COLOR   = "#94a3b8"   # slate-400
_PRIMARY_COLOR = "#6366f1"   # indigo-500
_PIE_COLORS    = px.colors.qualitative.Pastel


# ===========================================================================
# Base Chart Builder
# ===========================================================================

class BaseChartBuilder:
    """Helper to apply common dark-mode styling and export functions."""

    @staticmethod
    def apply_theme(fig: go.Figure, title: str | None = None) -> None:
        """Apply uniform dark theme to a Plotly figure."""
        fig.update_layout(
            title=dict(
                text=title if title else "",
                font=dict(family=_FONT_FAMILY, size=20, color=_TEXT_COLOR),
                x=0.5, xanchor="center", y=0.98, yanchor="top",
            ),
            paper_bgcolor=_PAPER_COLOR,
            plot_bgcolor=_BG_COLOR,
            font=dict(family=_FONT_FAMILY, color=_TEXT_COLOR),
            margin=dict(l=60, r=40, t=80, b=60),
            hoverlabel=dict(
                bgcolor="#1e293b", bordercolor="#475569",
                font=dict(family=_FONT_FAMILY, size=12, color="#e2e8f0"),
            ),
        )

        fig.update_xaxes(
            gridcolor=_GRID_COLOR, zerolinecolor=_GRID_COLOR,
            tickfont=dict(family=_FONT_FAMILY, color=_MUTED_COLOR),
            title_font=dict(family=_FONT_FAMILY, color=_MUTED_COLOR),
        )
        fig.update_yaxes(
            gridcolor=_GRID_COLOR, zerolinecolor=_GRID_COLOR,
            tickfont=dict(family=_FONT_FAMILY, color=_MUTED_COLOR),
            title_font=dict(family=_FONT_FAMILY, color=_MUTED_COLOR),
        )

    @staticmethod
    def export(
        fig: go.Figure,
        chart_id: str,
        plots_dir: pathlib.Path,
        export_format: ExportFormat,
    ) -> tuple[str | None, str | None]:
        """
        Export figure to disk based on requested formats.
        Returns (png_filename, html_filename).
        """
        plots_dir.mkdir(parents=True, exist_ok=True)
        
        png_name, html_name = None, None

        if export_format in (ExportFormat.PNG, ExportFormat.BOTH):
            png_name = f"viz_{chart_id}.png"
            path = plots_dir / png_name
            # Fallback size if layout doesn't specify
            w = fig.layout.width or 1000
            h = fig.layout.height or 600
            fig.write_image(str(path), format="png", width=w, height=h, scale=1, engine="kaleido")

        if export_format in (ExportFormat.HTML, ExportFormat.BOTH):
            html_name = f"viz_{chart_id}.html"
            path = plots_dir / html_name
            fig.write_html(str(path), include_plotlyjs="cdn", full_html=True, default_width="100%", default_height="100%")

        return png_name, html_name


# ===========================================================================
# Specific Chart Generators
# ===========================================================================

class VisualizationGenerator(BaseChartBuilder):
    """Contains logic for generating each specific chart type."""

    def build_histogram(self, df: pd.DataFrame, req: HistogramRequest) -> go.Figure:
        if req.column not in df.columns:
            raise ValueError(f"Column '{req.column}' not found.")
        
        fig = px.histogram(
            df, x=req.column, nbins=req.bins,
            color_discrete_sequence=[_PRIMARY_COLOR]
        )
        title = req.title or f"Distribution of {req.column}"
        self.apply_theme(fig, title)
        fig.update_traces(marker_line_width=1, marker_line_color="rgba(255,255,255,0.2)")
        return fig

    def build_bar(self, df: pd.DataFrame, req: BarChartRequest) -> go.Figure:
        if req.column not in df.columns:
            raise ValueError(f"Column '{req.column}' not found.")
        
        counts = df[req.column].value_counts().nlargest(req.top_k).reset_index()
        counts.columns = [req.column, "count"]
        
        fig = px.bar(
            counts, x=req.column, y="count",
            color_discrete_sequence=[_PRIMARY_COLOR]
        )
        title = req.title or f"Top {req.top_k} Frequencies in {req.column}"
        self.apply_theme(fig, title)
        return fig

    def build_pie(self, df: pd.DataFrame, req: PieChartRequest) -> go.Figure:
        if req.column not in df.columns:
            raise ValueError(f"Column '{req.column}' not found.")

        counts = df[req.column].value_counts()
        if len(counts) > req.top_k:
            top = counts.nlargest(req.top_k)
            other_sum = counts.iloc[req.top_k:].sum()
            top["Other"] = other_sum
            counts = top
        
        fig = px.pie(
            names=counts.index, values=counts.values,
            color_discrete_sequence=_PIE_COLORS
        )
        title = req.title or f"Proportions of {req.column}"
        self.apply_theme(fig, title)
        # Fix pie trace styling
        fig.update_traces(textposition='inside', textinfo='percent+label', marker=dict(line=dict(color=_PAPER_COLOR, width=2)))
        return fig

    def build_scatter(self, df: pd.DataFrame, req: ScatterPlotRequest) -> go.Figure:
        for col in [req.x, req.y]:
            if col not in df.columns:
                raise ValueError(f"Column '{col}' not found.")
        if req.color_by and req.color_by not in df.columns:
            raise ValueError(f"Color column '{req.color_by}' not found.")

        fig = px.scatter(
            df, x=req.x, y=req.y, color=req.color_by,
            color_discrete_sequence=px.colors.qualitative.Vivid
        )
        title = req.title or f"Scatter: {req.y} vs {req.x}"
        self.apply_theme(fig, title)
        fig.update_traces(marker=dict(size=8, opacity=0.7, line=dict(width=1, color="rgba(255,255,255,0.2)")))
        return fig

    def build_line(self, df: pd.DataFrame, req: LineChartRequest) -> go.Figure:
        for col in [req.x, req.y]:
            if col not in df.columns:
                raise ValueError(f"Column '{col}' not found.")

        plot_df = df.sort_values(req.x) if req.sort_x else df
        
        fig = px.line(
            plot_df, x=req.x, y=req.y,
            color_discrete_sequence=[_PRIMARY_COLOR]
        )
        title = req.title or f"Trend of {req.y} over {req.x}"
        self.apply_theme(fig, title)
        fig.update_traces(line=dict(width=2.5))
        return fig

    def build_box(self, df: pd.DataFrame, req: BoxPlotRequest) -> go.Figure:
        if req.y not in df.columns:
            raise ValueError(f"Column '{req.y}' not found.")
        if req.x and req.x not in df.columns:
            raise ValueError(f"Column '{req.x}' not found.")

        fig = px.box(
            df, y=req.y, x=req.x,
            color=req.x if req.x else None,
            color_discrete_sequence=px.colors.qualitative.Pastel
        )
        title = req.title or (f"Boxplot of {req.y} by {req.x}" if req.x else f"Boxplot of {req.y}")
        self.apply_theme(fig, title)
        return fig

    def build_heatmap(self, df: pd.DataFrame, req: CorrelationHeatmapRequest) -> go.Figure:
        all_numeric = df.select_dtypes(include=[np.number]).columns.tolist()
        cols = [c for c in req.columns if c in all_numeric] if req.columns else all_numeric
        
        if len(cols) < 2:
            raise ValueError("Need at least 2 numeric columns for a correlation heatmap.")
            
        corr_matrix = df[cols].corr().to_numpy()
        
        fig = go.Figure(data=go.Heatmap(
            z=corr_matrix[::-1], x=cols, y=cols[::-1],
            colorscale="RdBu", zmin=-1.0, zmax=1.0, zmid=0.0,
            text=np.round(corr_matrix[::-1], 2), texttemplate="%{text}",
            hoverongaps=False
        ))
        title = req.title or "Correlation Heatmap"
        self.apply_theme(fig, title)
        size = max(600, min(1400, 200 + len(cols) * 60))
        fig.update_layout(width=size, height=size)
        return fig


# ===========================================================================
# Service Orchestrator
# ===========================================================================

class VisualizationService:
    def __init__(self, dataset_service: Any, plots_dir: pathlib.Path) -> None:
        self._dataset_service = dataset_service
        self._plots_dir = plots_dir
        self._generator = VisualizationGenerator()

    def generate_batch(
        self,
        dataset_id: str,
        request: VisualizationBatchRequest,
        api_base_url: str = "/api/v1",
    ) -> VisualizationBatchReport:
        t_start = time.perf_counter()
        
        df = self._dataset_service.load_dataframe(dataset_id)
        
        results = []
        success_count = 0
        fail_count = 0

        for chart_req in request.charts:
            chart_id = str(uuid.uuid4())
            png_url, html_url, error = None, None, None

            try:
                # 1. Dispatch to builder
                if isinstance(chart_req, HistogramRequest):
                    fig = self._generator.build_histogram(df, chart_req)
                elif isinstance(chart_req, BarChartRequest):
                    fig = self._generator.build_bar(df, chart_req)
                elif isinstance(chart_req, PieChartRequest):
                    fig = self._generator.build_pie(df, chart_req)
                elif isinstance(chart_req, ScatterPlotRequest):
                    fig = self._generator.build_scatter(df, chart_req)
                elif isinstance(chart_req, LineChartRequest):
                    fig = self._generator.build_line(df, chart_req)
                elif isinstance(chart_req, BoxPlotRequest):
                    fig = self._generator.build_box(df, chart_req)
                elif isinstance(chart_req, CorrelationHeatmapRequest):
                    fig = self._generator.build_heatmap(df, chart_req)
                else:
                    raise ValueError(f"Unsupported chart request type: {type(chart_req)}")

                # 2. Export
                png_name, html_name = self._generator.export(
                    fig=fig,
                    chart_id=chart_id,
                    plots_dir=self._plots_dir,
                    export_format=request.export_format,
                )

                if png_name:
                    png_url = f"{api_base_url}/visualizations/chart/{png_name}"
                if html_name:
                    html_url = f"{api_base_url}/visualizations/chart/{html_name}"
                
                success_count += 1

            except Exception as exc:
                error = str(exc)
                fail_count += 1
                logger.warning(f"Failed to build chart {chart_req.type}: {error}")

            results.append(GeneratedChartInfo(
                chart_id=chart_id,
                type=chart_req.type.value,
                png_url=png_url,
                html_url=html_url,
                error=error,
            ))

        elapsed = round((time.perf_counter() - t_start) * 1000, 2)
        logger.info(
            "Visualization batch complete",
            dataset_id=dataset_id,
            success=success_count,
            failed=fail_count,
            elapsed_ms=elapsed,
        )

        return VisualizationBatchReport(
            dataset_id=dataset_id,
            successful_charts=success_count,
            failed_charts=fail_count,
            charts=results,
            elapsed_ms=elapsed,
        )
