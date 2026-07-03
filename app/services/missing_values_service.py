"""
DataInsight API — Missing Values Service
==========================================
Detects, quantifies, and visualises missing values across a dataset.

Responsibilities (Single Responsibility Principle):
  MissingValuesDetector   — pure computation, no I/O, no charts
  MissingValuesChartBuilder — Plotly chart construction and PNG export
  MissingValuesService    — top-level orchestrator wiring both together

Chart design:
  - Horizontal bar chart, one bar per column (sorted by missing %)
  - Bars colour-coded by severity:
      none / low    → emerald green   (#10b981)
      moderate      → amber           (#f59e0b)
      high          → orange          (#f97316)
      critical      → crimson red     (#ef4444)
  - Each bar annotated with "N missing (X.X%)"
  - Reference lines at 5%, 20%, 50% thresholds
  - Dark-mode premium theme with subtle grid and gradient background
  - Exported at 1600 × (dynamic height) px for high-DPI displays
"""

from __future__ import annotations

import pathlib
import time
import uuid
from typing import Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from app.schemas.missing_values import (
    ChartInfo,
    ColumnMissingInfo,
    MissingValuesSummary,
    MissingValuesReport,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Severity thresholds
# ---------------------------------------------------------------------------

def _severity(pct: float) -> str:
    """
    Map a missing-value percentage to a severity label.

    Args:
        pct: Missing percentage (0–100).

    Returns:
        One of: 'none', 'low', 'moderate', 'high', 'critical'.
    """
    if pct == 0.0:
        return "none"
    if pct < 5.0:
        return "low"
    if pct < 20.0:
        return "moderate"
    if pct < 50.0:
        return "high"
    return "critical"


# Severity → bar colour mapping (dark-mode palette)
_SEVERITY_COLOR: dict[str, str] = {
    "none":     "#10b981",   # emerald green
    "low":      "#34d399",   # lighter green
    "moderate": "#f59e0b",   # amber
    "high":     "#f97316",   # orange
    "critical": "#ef4444",   # crimson red
}

# Severity → badge background colour (for text annotations)
_SEVERITY_BG: dict[str, str] = {
    "none":     "rgba(16,185,129,0.15)",
    "low":      "rgba(52,211,153,0.15)",
    "moderate": "rgba(245,158,11,0.15)",
    "high":     "rgba(249,115,22,0.20)",
    "critical": "rgba(239,68,68,0.20)",
}


# ===========================================================================
# 1. Missing Values Detector — pure computation
# ===========================================================================

class MissingValuesDetector:
    """
    Performs a fast, vectorised scan of a DataFrame for missing values.

    This class only reads data — no I/O, no chart generation.
    All operations use numpy/pandas vectorised functions.
    """

    def detect(self, df: pd.DataFrame) -> list[ColumnMissingInfo]:
        """
        Compute per-column missing-value statistics.

        Uses a single DataFrame.isna() call to build the null matrix,
        then reads per-column sums — O(rows × cols) with C-level speed.

        Args:
            df: Input DataFrame (any dtypes).

        Returns:
            List of ColumnMissingInfo sorted by missing_pct descending.
        """
        total_rows: int = len(df)

        # Single vectorised null-count pass for all columns
        null_counts: pd.Series = df.isna().sum()

        results: list[ColumnMissingInfo] = []
        for col in df.columns:
            missing: int = int(null_counts[col])
            present: int = total_rows - missing
            missing_pct = round((missing / total_rows * 100) if total_rows > 0 else 0.0, 4)
            present_pct = round(100.0 - missing_pct, 4)

            results.append(ColumnMissingInfo(
                column=col,
                dtype=str(df[col].dtype),
                total_count=total_rows,
                missing_count=missing,
                missing_pct=missing_pct,
                present_count=present,
                present_pct=present_pct,
                severity=_severity(missing_pct),
            ))

        # Sort: most missing first
        results.sort(key=lambda r: r.missing_pct, reverse=True)
        return results

    def build_summary(
        self,
        df: pd.DataFrame,
        column_stats: list[ColumnMissingInfo],
    ) -> MissingValuesSummary:
        """
        Build the dataset-level aggregated summary.

        Args:
            df:           Source DataFrame.
            column_stats: Per-column stats (from detect()).

        Returns:
            MissingValuesSummary with counts and severity-bucket lists.
        """
        total_rows = len(df)
        total_cols = len(df.columns)
        total_cells = total_rows * total_cols
        total_missing = int(df.isna().sum().sum())
        overall_pct = round((total_missing / total_cells * 100) if total_cells > 0 else 0.0, 4)

        cols_with_missing = [c for c in column_stats if c.missing_count > 0]
        fully_missing     = [c.column for c in column_stats if c.missing_pct == 100.0]
        above_50          = [c.column for c in column_stats if 50.0 < c.missing_pct < 100.0]
        above_20          = [c.column for c in column_stats if 20.0 <= c.missing_pct <= 50.0]
        above_5           = [c.column for c in column_stats if 5.0 <= c.missing_pct < 20.0]
        below_5           = [c.column for c in column_stats if 0.0 < c.missing_pct < 5.0]
        complete          = [c.column for c in column_stats if c.missing_pct == 0.0]

        return MissingValuesSummary(
            total_rows=total_rows,
            total_columns=total_cols,
            total_cells=total_cells,
            total_missing_cells=total_missing,
            overall_missing_pct=overall_pct,
            columns_with_missing=len(cols_with_missing),
            columns_fully_missing=fully_missing,
            columns_above_50pct=above_50,
            columns_above_20pct=above_20,
            columns_above_5pct=above_5,
            columns_below_5pct=below_5,
            complete_columns=complete,
        )


# ===========================================================================
# 2. Missing Values Chart Builder — Plotly PNG generation
# ===========================================================================

class MissingValuesChartBuilder:
    """
    Builds a premium dark-mode Plotly bar chart visualising missing values
    and exports it as a high-resolution PNG via Kaleido.

    Chart layout:
      - Horizontal bar chart (columns on Y-axis, missing % on X-axis)
      - Bars colour-coded by severity (green → amber → orange → red)
      - Bar text: "N missing (X.X%)" aligned inside the bar
      - Vertical reference lines at 5%, 20%, 50%
      - Dark gradient background, subtle grid, custom font
      - Dynamic height: 80px per column (min 500px, max 2400px)
      - Width: 1400px (high-DPI friendly)
    """

    CHART_WIDTH: int  = 1400
    ROW_HEIGHT:  int  = 70    # px per column bar
    MIN_HEIGHT:  int  = 500
    MAX_HEIGHT:  int  = 2400

    FONT_FAMILY: str = "Inter, 'Helvetica Neue', Arial, sans-serif"

    # Dark-mode background palette
    BG_COLOR:    str = "#0f172a"   # slate-900
    PAPER_COLOR: str = "#1e293b"   # slate-800
    GRID_COLOR:  str = "#334155"   # slate-600
    TEXT_COLOR:  str = "#e2e8f0"   # slate-200
    MUTED_COLOR: str = "#94a3b8"   # slate-400

    def build(
        self,
        column_stats: list[ColumnMissingInfo],
        dataset_id: str,
        total_rows: int,
    ) -> go.Figure:
        """
        Construct the Plotly Figure.

        Args:
            column_stats: Per-column stats sorted by missing_pct descending.
            dataset_id:   Used in the chart title.
            total_rows:   Total row count (for subtitle).

        Returns:
            A Plotly Figure ready for PNG export.
        """
        # Reverse so highest missing is at top of horizontal chart
        stats = list(reversed(column_stats))

        cols      = [s.column for s in stats]
        pcts      = [s.missing_pct for s in stats]
        counts    = [s.missing_count for s in stats]
        severities = [s.severity for s in stats]
        bar_colors = [_SEVERITY_COLOR[sev] for sev in severities]

        # Build hover text (detailed tooltip)
        hover_texts = [
            (
                f"<b>{s.column}</b><br>"
                f"Missing: {s.missing_count:,} / {s.total_count:,} rows<br>"
                f"Missing: {s.missing_pct:.2f}%<br>"
                f"Present: {s.present_count:,} ({s.present_pct:.2f}%)<br>"
                f"Dtype: {s.dtype}<br>"
                f"Severity: <b>{s.severity.upper()}</b>"
            )
            for s in stats
        ]

        # Annotation text inside bars
        bar_texts = [
            f"  {c:,} missing  ({p:.1f}%)" if p > 0 else "  ✓ Complete"
            for c, p in zip(counts, pcts)
        ]

        fig = go.Figure()

        # ── Main bars ────────────────────────────────────────────────────
        fig.add_trace(go.Bar(
            x=pcts,
            y=cols,
            orientation="h",
            marker=dict(
                color=bar_colors,
                line=dict(color="rgba(255,255,255,0.08)", width=1),
                opacity=0.9,
            ),
            text=bar_texts,
            textposition="inside",
            textfont=dict(
                family=self.FONT_FAMILY,
                size=12,
                color="#ffffff",
            ),
            insidetextanchor="start",
            hovertemplate="%{customdata}<extra></extra>",
            customdata=hover_texts,
            showlegend=False,
        ))

        # ── Threshold reference lines ─────────────────────────────────────
        thresholds = [
            (5,  "#34d399", "5% — Low"),
            (20, "#f59e0b", "20% — Moderate"),
            (50, "#ef4444", "50% — High"),
        ]
        for x_val, color, label in thresholds:
            if x_val <= (max(pcts) + 5 if pcts else 100):
                fig.add_vline(
                    x=x_val,
                    line_dash="dot",
                    line_color=color,
                    line_width=1.5,
                    opacity=0.6,
                    annotation_text=label,
                    annotation_position="top",
                    annotation_font=dict(
                        color=color,
                        size=10,
                        family=self.FONT_FAMILY,
                    ),
                    annotation_bgcolor="rgba(0,0,0,0.4)",
                    annotation_borderpad=4,
                )

        # ── Legend: severity colour chips ─────────────────────────────────
        legend_items = [
            ("none/low",  _SEVERITY_COLOR["low"],      "0–5%"),
            ("moderate",  _SEVERITY_COLOR["moderate"],  "5–20%"),
            ("high",      _SEVERITY_COLOR["high"],      "20–50%"),
            ("critical",  _SEVERITY_COLOR["critical"],  ">50%"),
        ]
        for label, color, rng in legend_items:
            fig.add_trace(go.Bar(
                x=[None], y=[None],
                name=f"■  {label.capitalize()}  ({rng})",
                marker_color=color,
                showlegend=True,
            ))

        # ── Layout ────────────────────────────────────────────────────────
        n_cols = len(column_stats)
        chart_height = max(
            self.MIN_HEIGHT,
            min(self.MAX_HEIGHT, n_cols * self.ROW_HEIGHT + 200),
        )

        x_max = min(100, max(pcts) * 1.15 + 2) if pcts else 100

        affected = sum(1 for s in column_stats if s.missing_count > 0)
        subtitle = (
            f"{total_rows:,} rows · {n_cols} columns · "
            f"{affected} columns with missing values"
        )

        fig.update_layout(
            title=dict(
                text=(
                    f"Missing Values Analysis"
                    f"<br><span style='font-size:13px;color:{self.MUTED_COLOR}'>"
                    f"{subtitle}</span>"
                ),
                font=dict(
                    family=self.FONT_FAMILY,
                    size=22,
                    color=self.TEXT_COLOR,
                ),
                x=0.5,
                xanchor="center",
                y=0.98,
                yanchor="top",
                pad=dict(b=20),
            ),
            xaxis=dict(
                title=dict(
                    text="Missing Values (%)",
                    font=dict(family=self.FONT_FAMILY, size=13, color=self.MUTED_COLOR),
                ),
                range=[0, x_max],
                ticksuffix="%",
                tickfont=dict(family=self.FONT_FAMILY, size=11, color=self.MUTED_COLOR),
                gridcolor=self.GRID_COLOR,
                gridwidth=1,
                zeroline=True,
                zerolinecolor=self.GRID_COLOR,
                zerolinewidth=1.5,
                showgrid=True,
            ),
            yaxis=dict(
                tickfont=dict(
                    family=self.FONT_FAMILY,
                    size=12,
                    color=self.TEXT_COLOR,
                ),
                automargin=True,
                gridcolor="rgba(0,0,0,0)",
            ),
            legend=dict(
                orientation="h",
                x=0.5,
                xanchor="center",
                y=-0.06,
                bgcolor="rgba(0,0,0,0)",
                font=dict(family=self.FONT_FAMILY, size=11, color=self.MUTED_COLOR),
                traceorder="normal",
            ),
            plot_bgcolor=self.BG_COLOR,
            paper_bgcolor=self.PAPER_COLOR,
            margin=dict(l=30, r=40, t=90, b=80),
            width=self.CHART_WIDTH,
            height=chart_height,
            bargap=0.35,
            font=dict(family=self.FONT_FAMILY),
            hoverlabel=dict(
                bgcolor="#1e293b",
                bordercolor="#475569",
                font=dict(family=self.FONT_FAMILY, size=12, color="#e2e8f0"),
            ),
        )

        return fig

    def export_png(
        self,
        fig: go.Figure,
        plots_dir: pathlib.Path,
        dataset_id: str,
    ) -> tuple[pathlib.Path, int]:
        """
        Export the Plotly figure to a PNG file in the plots directory.

        The filename is deterministic per dataset_id so repeated calls
        overwrite the same file rather than filling the disk.

        Args:
            fig:        The Plotly Figure to export.
            plots_dir:  Target directory for the PNG file.
            dataset_id: Used to construct the output filename.

        Returns:
            (absolute_path_to_png, file_size_in_bytes)
        """
        plots_dir.mkdir(parents=True, exist_ok=True)
        filename = f"missing_values_{dataset_id}.png"
        output_path = plots_dir / filename

        fig.write_image(
            str(output_path),
            format="png",
            width=self.CHART_WIDTH,
            height=fig.layout.height,
            scale=1,             # 1× scale — already high resolution at 1400px
            engine="kaleido",
        )

        file_size = output_path.stat().st_size
        logger.info(
            "Missing values chart exported",
            path=str(output_path),
            size_kb=round(file_size / 1024, 2),
        )
        return output_path, file_size


# ===========================================================================
# 3. MissingValuesService — top-level orchestrator
# ===========================================================================

class MissingValuesService:
    """
    Orchestrates the full missing-values analysis and chart-generation pipeline.

    1. Load the DataFrame via DatasetService.
    2. Run MissingValuesDetector to compute per-column and summary stats.
    3. Build the Plotly chart with MissingValuesChartBuilder.
    4. Export the chart as a PNG to the plots directory.
    5. Return a fully-populated MissingValuesReport.

    Usage:
        service = MissingValuesService(dataset_service, plots_dir)
        report  = service.analyse(dataset_id="abc-123", api_base_url="/api/v1")
    """

    def __init__(
        self,
        dataset_service: Any,
        plots_dir: pathlib.Path,
    ) -> None:
        """
        Args:
            dataset_service: Shared DatasetService instance (from app.state).
            plots_dir:       Directory where PNG charts are saved.
        """
        self._dataset_service = dataset_service
        self._plots_dir = plots_dir
        self._detector = MissingValuesDetector()
        self._chart_builder = MissingValuesChartBuilder()

    def analyse(
        self,
        dataset_id: str,
        api_base_url: str = "/api/v1",
    ) -> MissingValuesReport:
        """
        Run the full pipeline: detect → summarise → chart → export.

        Args:
            dataset_id:   UUID of the dataset to analyse.
            api_base_url: Base URL prefix for the chart download URL.

        Returns:
            MissingValuesReport with full stats and chart metadata.
        """
        t_start = time.perf_counter()

        # ── Step 1: Load data ─────────────────────────────────────────────
        df: pd.DataFrame = self._dataset_service.load_dataframe(dataset_id)
        logger.info(
            "Missing values analysis started",
            dataset_id=dataset_id,
            rows=len(df),
            columns=len(df.columns),
        )

        # ── Step 2: Detect missing values ─────────────────────────────────
        column_stats: list[ColumnMissingInfo] = self._detector.detect(df)
        summary: MissingValuesSummary = self._detector.build_summary(df, column_stats)
        affected: list[ColumnMissingInfo] = [
            c for c in column_stats if c.missing_count > 0
        ]

        # ── Step 3: Build Plotly chart ────────────────────────────────────
        fig: go.Figure = self._chart_builder.build(
            column_stats=column_stats,
            dataset_id=dataset_id,
            total_rows=len(df),
        )

        # ── Step 4: Export PNG ────────────────────────────────────────────
        chart_path, file_size = self._chart_builder.export_png(
            fig=fig,
            plots_dir=self._plots_dir,
            dataset_id=dataset_id,
        )

        chart_filename = chart_path.name
        chart_url = f"{api_base_url}/missing-values/chart/{dataset_id}"

        chart_info = ChartInfo(
            chart_path=str(chart_path),
            chart_filename=chart_filename,
            chart_url=chart_url,
            width_px=MissingValuesChartBuilder.CHART_WIDTH,
            height_px=fig.layout.height,
            file_size_kb=round(file_size / 1024, 2),
        )

        elapsed_ms = round((time.perf_counter() - t_start) * 1000, 2)
        logger.info(
            "Missing values analysis complete",
            dataset_id=dataset_id,
            columns_with_missing=summary.columns_with_missing,
            total_missing=summary.total_missing_cells,
            elapsed_ms=elapsed_ms,
        )

        return MissingValuesReport(
            dataset_id=dataset_id,
            summary=summary,
            columns=column_stats,
            affected_columns=affected,
            chart=chart_info,
        )
