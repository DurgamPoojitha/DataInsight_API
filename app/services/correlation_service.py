"""
DataInsight API — Correlation Service
=====================================
Computes correlation matrices (Pearson, Spearman, Kendall) and generates
interactive Plotly heatmaps exported to PNG and HTML.
"""

from __future__ import annotations

import pathlib
import time
from typing import Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from app.schemas.correlation import (
    CorrelationChartInfo,
    CorrelationMatrix,
    CorrelationPair,
    CorrelationReport,
    CorrelationRequest,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_FONT_FAMILY = "Inter, 'Helvetica Neue', Arial, sans-serif"
_BG_COLOR    = "#0f172a"   # slate-900
_PAPER_COLOR = "#1e293b"   # slate-800
_TEXT_COLOR  = "#e2e8f0"   # slate-200
_MUTED_COLOR = "#94a3b8"   # slate-400


# ===========================================================================
# Chart Builder
# ===========================================================================

class CorrelationChartBuilder:
    """Builds and exports Plotly correlation heatmaps."""

    def build(
        self,
        corr_df: pd.DataFrame,
        dataset_id: str,
        method: str,
    ) -> go.Figure:
        """
        Build the Plotly Figure for a correlation heatmap.

        Uses RdBu color scale (Red for negative, Blue for positive, White for 0).
        """
        labels = corr_df.columns.tolist()
        matrix = corr_df.to_numpy()

        # Reverse the y-axis so the diagonal goes from top-left to bottom-right
        fig = go.Figure(data=go.Heatmap(
            z=matrix[::-1],
            x=labels,
            y=labels[::-1],
            colorscale="RdBu",
            zmin=-1.0,
            zmax=1.0,
            zmid=0.0,
            text=np.round(matrix[::-1], 2),
            texttemplate="%{text}",
            textfont={"size": 10},
            hoverongaps=False,
            hovertemplate="X: %{x}<br>Y: %{y}<br>Correlation: %{z:.3f}<extra></extra>",
        ))

        # Dynamic size based on feature count
        n_features = len(labels)
        size = max(600, min(1400, 200 + n_features * 60))

        fig.update_layout(
            title=dict(
                text=(
                    f"Correlation Heatmap"
                    f"<br><span style='font-size:13px;color:{_MUTED_COLOR}'>"
                    f"Method: <b>{method.upper()}</b>  ·  {n_features} features"
                    f"</span>"
                ),
                font=dict(family=_FONT_FAMILY, size=21, color=_TEXT_COLOR),
                x=0.5, xanchor="center",
                y=0.98, yanchor="top",
            ),
            xaxis=dict(
                tickangle=-45,
                tickfont=dict(family=_FONT_FAMILY, color=_TEXT_COLOR, size=11)
            ),
            yaxis=dict(
                tickfont=dict(family=_FONT_FAMILY, color=_TEXT_COLOR, size=11)
            ),
            paper_bgcolor=_PAPER_COLOR,
            plot_bgcolor=_BG_COLOR,
            font=dict(family=_FONT_FAMILY, color=_TEXT_COLOR),
            width=size,
            height=size,
            margin=dict(l=80, r=80, t=100, b=100),
        )
        return fig

    def export(
        self,
        fig: go.Figure,
        plots_dir: pathlib.Path,
        dataset_id: str,
        method: str,
    ) -> tuple[pathlib.Path, pathlib.Path, float, float]:
        """
        Export figure to both PNG and interactive HTML.

        Returns:
            (png_path, html_path, png_size_kb, html_size_kb)
        """
        plots_dir.mkdir(parents=True, exist_ok=True)
        base_name = f"correlation_{method}_{dataset_id}"
        
        png_path  = plots_dir / f"{base_name}.png"
        html_path = plots_dir / f"{base_name}.html"

        # Export PNG
        fig.write_image(
            str(png_path),
            format="png",
            width=fig.layout.width,
            height=fig.layout.height,
            scale=1,
            engine="kaleido",
        )

        # Export HTML
        fig.write_html(
            str(html_path),
            include_plotlyjs="cdn",
            full_html=True,
            default_width="100%",
            default_height="100%",
        )

        png_size = png_path.stat().st_size / 1024.0
        html_size = html_path.stat().st_size / 1024.0

        logger.info(
            "Correlation charts exported",
            png=str(png_path), png_kb=round(png_size, 2),
            html=str(html_path), html_kb=round(html_size, 2)
        )
        return png_path, html_path, png_size, html_size


# ===========================================================================
# Service
# ===========================================================================

class CorrelationService:
    """Orchestrates correlation calculation and chart generation."""

    def __init__(
        self,
        dataset_service: Any,
        plots_dir: pathlib.Path,
    ) -> None:
        self._dataset_service = dataset_service
        self._plots_dir       = plots_dir
        self._chart_builder   = CorrelationChartBuilder()

    def analyse(
        self,
        dataset_id: str,
        request: CorrelationRequest,
        api_base_url: str = "/api/v1",
    ) -> CorrelationReport:
        t_start = time.perf_counter()
        warnings: list[str] = []

        # ── 1. Load Data ─────────────────────────────────────────────────────
        df: pd.DataFrame = self._dataset_service.load_dataframe(dataset_id)
        
        # Determine numeric columns
        all_numeric = df.select_dtypes(include=[np.number]).columns.tolist()
        if not all_numeric:
            raise ValueError("Dataset has no numeric columns to correlate.")

        if request.columns:
            target_cols = [c for c in request.columns if c in all_numeric]
            skipped = [c for c in request.columns if c not in all_numeric]
            if skipped:
                warnings.append(f"Skipped non-numeric or missing columns: {skipped}")
        else:
            target_cols = all_numeric

        if len(target_cols) < 2:
            raise ValueError(f"Need at least 2 numeric columns for correlation, found {len(target_cols)}.")

        sub_df = df[target_cols]

        # ── 2. Calculate Correlation ─────────────────────────────────────────
        method = request.method.value
        # Pandas corr() handles NaNs by pairwise deletion automatically
        corr_df = sub_df.corr(method=method)

        # Build schema matrix (replace NaNs with None for JSON)
        matrix_data = corr_df.replace({np.nan: None}).values.tolist()
        matrix = CorrelationMatrix(features=target_cols, matrix=matrix_data)

        # ── 3. Find Pairwise Highlights ──────────────────────────────────────
        pairs = []
        n = len(target_cols)
        # Extract lower triangle without diagonal to avoid self-correlation and duplicates
        for i in range(n):
            for j in range(i + 1, n):
                val = corr_df.iloc[i, j]
                if not pd.isna(val):
                    pairs.append((target_cols[i], target_cols[j], float(val)))

        # Sort pairs by correlation
        pairs.sort(key=lambda x: x[2], reverse=True)

        def make_pair(x: str, y: str, val: float) -> CorrelationPair:
            abs_v = abs(val)
            if abs_v >= 0.8: strength = "Very Strong"
            elif abs_v >= 0.6: strength = "Strong"
            elif abs_v >= 0.4: strength = "Moderate"
            elif abs_v >= 0.2: strength = "Weak"
            else: strength = "Very Weak"
            direction = "Positive" if val >= 0 else "Negative"
            return CorrelationPair(
                feature_x=x, feature_y=y, correlation=round(val, 4),
                strength=f"{strength} {direction}"
            )

        schema_pairs = [make_pair(x, y, v) for x, y, v in pairs]

        strong_pos = schema_pairs[0] if schema_pairs and schema_pairs[0].correlation > 0 else None
        strong_neg = schema_pairs[-1] if schema_pairs and schema_pairs[-1].correlation < 0 else None
        
        highly_correlated = [
            p for p in schema_pairs 
            if abs(p.correlation) >= request.high_correlation_threshold
        ]

        # ── 4. Charts ────────────────────────────────────────────────────────
        chart_info: CorrelationChartInfo | None = None
        if request.generate_charts:
            try:
                fig = self._chart_builder.build(
                    corr_df=corr_df,
                    dataset_id=dataset_id,
                    method=method,
                )
                png_p, html_p, png_sz, html_sz = self._chart_builder.export(
                    fig=fig,
                    plots_dir=self._plots_dir,
                    dataset_id=dataset_id,
                    method=method,
                )
                chart_info = CorrelationChartInfo(
                    png_path=str(png_p),
                    png_url=f"{api_base_url}/correlation/chart/{dataset_id}?method={method}&fmt=png",
                    html_path=str(html_p),
                    html_url=f"{api_base_url}/correlation/chart/{dataset_id}?method={method}&fmt=html",
                    width_px=fig.layout.width,
                    height_px=fig.layout.height,
                    png_size_kb=round(png_sz, 2),
                    html_size_kb=round(html_sz, 2),
                )
            except Exception as exc:
                msg = f"Chart generation failed: {exc}"
                warnings.append(msg)
                logger.warning(msg)

        elapsed_ms = round((time.perf_counter() - t_start) * 1000, 2)
        logger.info(
            "Correlation analysis complete",
            dataset_id=dataset_id,
            method=method,
            columns=len(target_cols),
            elapsed_ms=elapsed_ms,
        )

        return CorrelationReport(
            dataset_id=dataset_id,
            method=method,
            columns_analysed=len(target_cols),
            matrix=matrix,
            strongest_positive=strong_pos,
            strongest_negative=strong_neg,
            highly_correlated_pairs=highly_correlated,
            chart=chart_info,
            warnings=warnings,
            elapsed_ms=elapsed_ms,
        )
