"""
DataInsight API — Outlier Detection Service
============================================
Three detection strategies + boxplot chart builder + top-level orchestrator.

Architecture (SOLID):
┌─────────────────────────────────────────────────────────────────────────┐
│                     OutlierDetectionService                              │
│   ┌──────────────────────────────────────────────────────────────────┐  │
│   │               OutlierDetectionEngine                             │  │
│   │  ┌─────────────────────────────────────────────────────────────┐ │  │
│   │  │   OutlierDetectionStrategy  (Abstract Base — OCP hook)      │ │  │
│   │  │   ┌───────────────────┐  ┌───────────────────┐             │ │  │
│   │  │   │  IQRStrategy      │  │  ZScoreStrategy   │             │ │  │
│   │  │   └───────────────────┘  └───────────────────┘             │ │  │
│   │  │   ┌──────────────────────────────────────────┐             │ │  │
│   │  │   │  IsolationForestStrategy                 │             │ │  │
│   │  │   └──────────────────────────────────────────┘             │ │  │
│   │  └─────────────────────────────────────────────────────────────┘ │  │
│   └──────────────────────────────────────────────────────────────────┘  │
│   ┌──────────────────────────────────────────────────────────────────┐  │
│   │               BoxplotChartBuilder                                │  │
│   └──────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘

Detection Strategy Details:
  IQR (Tukey fences):
    Lower = Q1 − k×IQR,  Upper = Q3 + k×IQR  (default k = 1.5)
    Pros: distribution-free, no normality assumption, highly interpretable.
    Cons: assumes unimodality; poor on skewed data with default k.

  Z-Score (standard and modified):
    Standard: z = (x − μ) / σ,  flag |z| > threshold (default 3.0)
    Modified: z = 0.6745 × (x − median) / MAD,  more robust to existing outliers.
    Pros: simple, well-understood.
    Cons: assumes normality; sensitive to existing outliers (standard version).

  Isolation Forest (sklearn):
    Unsupervised ensemble.  Each tree isolates observations by random splits.
    Outliers require fewer splits → shorter average path length.
    Pros: handles multivariate outliers; no normality assumption; scales well.
    Cons: contamination parameter must be estimated; non-deterministic without seed.

Extensibility:
    Add a new strategy by subclassing OutlierDetectionStrategy and
    implementing detect_column() and detect_multivariate().
    Register it in OutlierDetectionEngine._STRATEGY_REGISTRY.

Boxplot chart design:
    - Dynamic grid (≤4 columns wide) of Plotly Box traces
    - Outlier points highlighted with filled orange markers
    - Distribution bands (Q1–Q3) annotated per subplot
    - Dark-mode premium theme matching the project palette
    - Exported at 1600px × dynamic height via Kaleido
"""

from __future__ import annotations

import math
import pathlib
import time
from abc import ABC, abstractmethod
from typing import Any

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy import stats as scipy_stats

from app.schemas.outliers import (
    BoxplotChartInfo,
    ColumnOutlierResult,
    IQRConfig,
    IsolationForestConfig,
    MethodCatalogEntry,
    OutlierDetectionReport,
    OutlierDetectionRequest,
    OutlierMethod,
    ZScoreConfig,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Chart constants (shared with BoxplotChartBuilder)
# ---------------------------------------------------------------------------

_FONT_FAMILY   = "Inter, 'Helvetica Neue', Arial, sans-serif"
_BG_COLOR      = "#0f172a"   # slate-900
_PAPER_COLOR   = "#1e293b"   # slate-800
_GRID_COLOR    = "#334155"   # slate-600
_TEXT_COLOR    = "#e2e8f0"   # slate-200
_MUTED_COLOR   = "#94a3b8"   # slate-400
_BOX_COLOR     = "#6366f1"   # indigo-500  (box fill)
_OUTLIER_COLOR = "#f97316"   # orange-500 (outlier points)
_MEDIAN_COLOR  = "#10b981"   # emerald-500 (median line)

_CHART_WIDTH   = 1600
_SUBPLOT_COLS  = 4            # maximum subplots per row
_SUBPLOT_HEIGHT = 340         # px per subplot row
_TOP_MARGIN    = 100


# ===========================================================================
# Abstract base strategy
# ===========================================================================

class OutlierDetectionStrategy(ABC):
    """
    Abstract base class for all outlier detection algorithms.

    Subclasses must implement:
        detect_column()      — per-column (univariate) detection.
        detect_multivariate() — optional joint detection (e.g. Isolation Forest).
        name                 — string identifier.
        catalog_entry()      — human-readable description for the API catalogue.

    Extensibility (OCP):
        Register a new subclass in OutlierDetectionEngine._STRATEGY_REGISTRY
        without changing any existing code.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Short unique identifier (matches OutlierMethod enum value)."""
        ...

    @abstractmethod
    def detect_column(
        self,
        series: pd.Series,
        request: OutlierDetectionRequest,
    ) -> ColumnOutlierResult:
        """
        Detect outliers in a single numeric Series.

        Args:
            series:  Numeric pandas Series (original index preserved).
            request: Full request (method-specific config is read from it).

        Returns:
            ColumnOutlierResult with outlier indices, values, bounds, etc.
        """
        ...

    def detect_multivariate(
        self,
        df: pd.DataFrame,
        columns: list[str],
        request: OutlierDetectionRequest,
    ) -> dict[str, ColumnOutlierResult]:
        """
        Optional joint (multivariate) detection across multiple columns.

        Default implementation delegates to detect_column() for each column.
        Override in strategies that support joint detection (e.g. IsolationForest).

        Args:
            df:      DataFrame containing the target columns.
            columns: Column names to include.
            request: Full request object.

        Returns:
            Dict of column_name → ColumnOutlierResult.
        """
        return {col: self.detect_column(df[col], request) for col in columns}

    @staticmethod
    @abstractmethod
    def catalog_entry() -> MethodCatalogEntry:
        """Return a human-readable description for the method catalogue."""
        ...

    # ------------------------------------------------------------------
    # Shared helper: build a ColumnOutlierResult from a boolean mask
    # ------------------------------------------------------------------

    @staticmethod
    def _build_result(
        series: pd.Series,
        outlier_mask: np.ndarray,
        lower_bound: float | None,
        upper_bound: float | None,
        method_params: dict[str, Any],
        max_values: int,
    ) -> ColumnOutlierResult:
        """
        Build a ColumnOutlierResult from a boolean outlier mask.

        Args:
            series:       The original numeric Series.
            outlier_mask: Boolean np.ndarray of the same length as series.dropna().
            lower_bound:  Lower threshold (for IQR / Z-score methods).
            upper_bound:  Upper threshold (for IQR / Z-score methods).
            method_params: Method-specific parameters for documentation.
            max_values:   Maximum outlier values to include in response.

        Returns:
            Fully populated ColumnOutlierResult.
        """
        valid_series: pd.Series = series.dropna()
        total_count  = len(series)
        valid_count  = len(valid_series)

        # Map mask back to original Series indices
        outlier_positions = np.where(outlier_mask)[0]
        original_indices  = valid_series.iloc[outlier_positions].index.tolist()
        outlier_vals      = valid_series.iloc[outlier_positions].tolist()

        outlier_count = len(original_indices)
        outlier_pct   = round(
            (outlier_count / valid_count * 100) if valid_count > 0 else 0.0, 4
        )

        # Basic stats for context
        arr = valid_series.to_numpy(dtype=float)
        stats: dict[str, float | None] = {}
        if len(arr) > 0:
            q1, q3 = float(np.percentile(arr, 25)), float(np.percentile(arr, 75))
            stats = {
                "mean":   round(float(np.mean(arr)), 6),
                "median": round(float(np.median(arr)), 6),
                "std":    round(float(np.std(arr, ddof=1)), 6) if len(arr) > 1 else None,
                "q1":     round(q1, 6),
                "q3":     round(q3, 6),
                "iqr":    round(q3 - q1, 6),
                "min":    round(float(arr.min()), 6),
                "max":    round(float(arr.max()), 6),
            }

        # Cap outlier_values to avoid huge payloads
        capped_vals = [
            float(v) for v in outlier_vals[:max_values]
        ]

        return ColumnOutlierResult(
            column=series.name or "unknown",
            dtype=str(series.dtype),
            total_count=total_count,
            valid_count=valid_count,
            outlier_count=outlier_count,
            outlier_pct=outlier_pct,
            outlier_indices=[int(i) for i in original_indices],
            outlier_values=capped_vals,
            lower_bound=round(lower_bound, 6) if lower_bound is not None else None,
            upper_bound=round(upper_bound, 6) if upper_bound is not None else None,
            method_params=method_params,
            stats=stats,
        )


# ===========================================================================
# Strategy 1 — IQR (Tukey fences)
# ===========================================================================

class IQRStrategy(OutlierDetectionStrategy):
    """
    Interquartile Range (Tukey fence) outlier detection.

    Algorithm:
        Q1 = 25th percentile, Q3 = 75th percentile, IQR = Q3 − Q1
        Lower fence = Q1 − k × IQR
        Upper fence = Q3 + k × IQR   (default k = 1.5)
        Outlier ← value < lower_fence OR value > upper_fence
    """

    @property
    def name(self) -> str:
        return OutlierMethod.IQR.value

    def detect_column(
        self,
        series: pd.Series,
        request: OutlierDetectionRequest,
    ) -> ColumnOutlierResult:
        cfg: IQRConfig = request.iqr
        arr = series.dropna().to_numpy(dtype=float)

        if len(arr) == 0:
            return ColumnOutlierResult(
                column=str(series.name), dtype=str(series.dtype),
                total_count=len(series), valid_count=0,
                outlier_count=0, outlier_pct=0.0,
            )

        q1, q3  = np.percentile(arr, 25), np.percentile(arr, 75)
        iqr_val = q3 - q1
        lower   = float(q1 - cfg.multiplier * iqr_val)
        upper   = float(q3 + cfg.multiplier * iqr_val)

        mask = (arr < lower) | (arr > upper)
        return self._build_result(
            series=series,
            outlier_mask=mask,
            lower_bound=lower,
            upper_bound=upper,
            method_params={
                "q1": round(float(q1), 4),
                "q3": round(float(q3), 4),
                "iqr": round(float(iqr_val), 4),
                "multiplier": cfg.multiplier,
                "lower_fence": round(lower, 4),
                "upper_fence": round(upper, 4),
            },
            max_values=request.max_outlier_values,
        )

    @staticmethod
    def catalog_entry() -> MethodCatalogEntry:
        return MethodCatalogEntry(
            name="iqr",
            description=(
                "Tukey's IQR fence method: values below Q1 − k×IQR or above "
                "Q3 + k×IQR are flagged as outliers."
            ),
            parameters={
                "multiplier": "Fence multiplier k (default 1.5 = inner fence, 3.0 = outer fence)",
            },
            when_to_use=(
                "Best general-purpose method.  Distribution-free, robust to "
                "non-Gaussian data, and highly interpretable.  Use k=3.0 for "
                "a stricter 'extreme outlier' definition."
            ),
            limitations=(
                "Assumes unimodal distribution.  May flag too many outliers on "
                "heavy-tailed or strongly skewed data with the default k=1.5."
            ),
        )


# ===========================================================================
# Strategy 2 — Z-Score (standard + modified)
# ===========================================================================

class ZScoreStrategy(OutlierDetectionStrategy):
    """
    Z-Score outlier detection with optional Modified (MAD-based) variant.

    Standard Z-Score:
        z = (x − μ) / σ;  flag |z| > threshold
    Modified Z-Score (Iglewicz & Hoaglin):
        z_mod = 0.6745 × (x − median) / MAD;  flag |z_mod| > threshold
        More robust because it uses median/MAD instead of mean/std.
    """

    @property
    def name(self) -> str:
        return OutlierMethod.ZSCORE.value

    def detect_column(
        self,
        series: pd.Series,
        request: OutlierDetectionRequest,
    ) -> ColumnOutlierResult:
        cfg: ZScoreConfig = request.zscore
        arr = series.dropna().to_numpy(dtype=float)

        if len(arr) < 2:
            return ColumnOutlierResult(
                column=str(series.name), dtype=str(series.dtype),
                total_count=len(series), valid_count=len(arr),
                outlier_count=0, outlier_pct=0.0,
                method_params={"reason": "insufficient data (need >= 2 values)"},
            )

        if cfg.use_modified:
            # Modified Z-Score (Iglewicz & Hoaglin, 1993)
            median_val = np.median(arr)
            mad = np.median(np.abs(arr - median_val))
            if mad == 0:
                # MAD=0: all values identical — no outliers possible
                mask = np.zeros(len(arr), dtype=bool)
                lower, upper = None, None
            else:
                z_scores = 0.6745 * (arr - median_val) / mad
                mask     = np.abs(z_scores) > cfg.threshold
                # Derive equivalent bounds in original units
                lower = float(median_val - cfg.threshold * mad / 0.6745)
                upper = float(median_val + cfg.threshold * mad / 0.6745)
            params = {
                "variant": "modified",
                "median": round(float(median_val), 4),
                "mad": round(float(mad), 4),
                "threshold": cfg.threshold,
            }
        else:
            # Standard Z-Score
            mu, sigma = np.mean(arr), np.std(arr, ddof=1)
            if sigma == 0:
                mask = np.zeros(len(arr), dtype=bool)
                lower, upper = None, None
            else:
                z_scores = (arr - mu) / sigma
                mask     = np.abs(z_scores) > cfg.threshold
                lower    = float(mu - cfg.threshold * sigma)
                upper    = float(mu + cfg.threshold * sigma)
            params = {
                "variant": "standard",
                "mean": round(float(mu), 4),
                "std": round(float(sigma), 4),
                "threshold": cfg.threshold,
            }

        return self._build_result(
            series=series,
            outlier_mask=mask,
            lower_bound=lower,
            upper_bound=upper,
            method_params=params,
            max_values=request.max_outlier_values,
        )

    @staticmethod
    def catalog_entry() -> MethodCatalogEntry:
        return MethodCatalogEntry(
            name="zscore",
            description=(
                "Z-Score method: values with |z| > threshold are flagged. "
                "Supports both standard (mean/std) and modified (median/MAD) variants."
            ),
            parameters={
                "threshold":     "Absolute Z-score above which a value is an outlier (default 3.0)",
                "use_modified":  "Use Modified Z-Score (MAD-based) for non-Gaussian data (default false)",
            },
            when_to_use=(
                "Good for approximately Gaussian data.  Use use_modified=true "
                "when the data is skewed or already contains outliers that would "
                "inflate the mean and standard deviation."
            ),
            limitations=(
                "Standard variant is sensitive to existing outliers (masking / "
                "swamping effects).  Assumes at least approximate normality for "
                "meaningful threshold selection."
            ),
        )


# ===========================================================================
# Strategy 3 — Isolation Forest (scikit-learn)
# ===========================================================================

class IsolationForestStrategy(OutlierDetectionStrategy):
    """
    Isolation Forest outlier detection using scikit-learn.

    Algorithm:
        Builds an ensemble of random binary trees.  Points that require
        fewer splits to isolate have shorter path lengths → marked as outliers.
        contamination parameter controls the decision threshold.

    Modes:
        multivariate=False (default): each column fitted independently (1D).
        multivariate=True:            all columns fitted jointly (nD).
    """

    @property
    def name(self) -> str:
        return OutlierMethod.ISOLATION_FOREST.value

    def detect_column(
        self,
        series: pd.Series,
        request: OutlierDetectionRequest,
    ) -> ColumnOutlierResult:
        """Fit Isolation Forest on a single column (1-D mode)."""
        try:
            from sklearn.ensemble import IsolationForest as _IF
        except ImportError:
            return ColumnOutlierResult(
                column=str(series.name), dtype=str(series.dtype),
                total_count=len(series), valid_count=0,
                outlier_count=0, outlier_pct=0.0,
                method_params={"error": "scikit-learn not installed"},
            )

        cfg: IsolationForestConfig = request.isolation_forest
        valid = series.dropna()
        arr   = valid.to_numpy(dtype=float).reshape(-1, 1)

        if len(arr) < 10:
            return ColumnOutlierResult(
                column=str(series.name), dtype=str(series.dtype),
                total_count=len(series), valid_count=len(arr),
                outlier_count=0, outlier_pct=0.0,
                method_params={"reason": "insufficient data (need >= 10 values)"},
            )

        clf = _IF(
            n_estimators=cfg.n_estimators,
            contamination=cfg.contamination,
            random_state=cfg.random_state,
            n_jobs=-1,          # Use all available cores
        )
        clf.fit(arr)

        # predict returns +1 (inlier) or -1 (outlier)
        predictions = clf.predict(arr)
        mask        = predictions == -1
        scores      = clf.score_samples(arr)   # anomaly scores (lower = more anomalous)

        params = {
            "n_estimators": cfg.n_estimators,
            "contamination": cfg.contamination,
            "random_state": cfg.random_state,
            "mode": "univariate",
            "mean_anomaly_score": round(float(scores.mean()), 6),
        }
        return self._build_result(
            series=series,
            outlier_mask=mask,
            lower_bound=None,
            upper_bound=None,
            method_params=params,
            max_values=request.max_outlier_values,
        )

    def detect_multivariate(
        self,
        df: pd.DataFrame,
        columns: list[str],
        request: OutlierDetectionRequest,
    ) -> dict[str, ColumnOutlierResult]:
        """
        Fit Isolation Forest jointly on all columns (multivariate mode).

        A single model is fitted on the n-dimensional feature matrix.
        Each column receives the same outlier mask (rows flagged by the joint fit).
        """
        if not request.isolation_forest.multivariate:
            # Fall back to per-column independent fitting
            return {col: self.detect_column(df[col], request) for col in columns}

        try:
            from sklearn.ensemble import IsolationForest as _IF
        except ImportError:
            return {col: self.detect_column(df[col], request) for col in columns}

        cfg = request.isolation_forest

        # Build feature matrix, dropping rows with any NaN
        sub_df = df[columns].dropna()
        if len(sub_df) < 10:
            return {col: self.detect_column(df[col], request) for col in columns}

        X = sub_df.to_numpy(dtype=float)
        clf = _IF(
            n_estimators=cfg.n_estimators,
            contamination=cfg.contamination,
            random_state=cfg.random_state,
            n_jobs=-1,
        )
        clf.fit(X)
        predictions = clf.predict(X)
        shared_mask = predictions == -1

        results: dict[str, ColumnOutlierResult] = {}
        for col in columns:
            # Apply the shared mask to the per-column clean Series
            col_series = df[col].dropna()
            # Align: restrict to the same rows used in joint fit
            aligned    = col_series.loc[sub_df.index]
            mask_for_col = np.zeros(len(aligned), dtype=bool)
            mask_for_col[:len(shared_mask)] = shared_mask

            results[col] = self._build_result(
                series=df[col],
                outlier_mask=mask_for_col,
                lower_bound=None,
                upper_bound=None,
                method_params={
                    "n_estimators": cfg.n_estimators,
                    "contamination": cfg.contamination,
                    "random_state": cfg.random_state,
                    "mode": "multivariate",
                    "columns_in_joint_fit": columns,
                },
                max_values=request.max_outlier_values,
            )
        return results

    @staticmethod
    def catalog_entry() -> MethodCatalogEntry:
        return MethodCatalogEntry(
            name="isolation_forest",
            description=(
                "Isolation Forest (Liu et al., 2008): tree-based ensemble that "
                "isolates observations by random feature splits.  Points requiring "
                "fewer splits (shorter path length) are flagged as outliers."
            ),
            parameters={
                "contamination":  "Expected fraction of outliers (0–0.5, default 0.05)",
                "n_estimators":   "Number of isolation trees (default 100)",
                "random_state":   "Seed for reproducibility (default 42)",
                "multivariate":   "True = joint nD fit; False = per-column 1D (default false)",
            },
            when_to_use=(
                "Best for complex, multivariate outliers that IQR / Z-Score miss.  "
                "No normality assumption.  Use multivariate=true when outliers "
                "only emerge in combinations of features (not visible per-column)."
            ),
            limitations=(
                "Requires contamination estimate.  Non-deterministic without "
                "random_state.  Computationally heavier than IQR/Z-Score.  "
                "No natural lower/upper bounds (decision is tree-path based)."
            ),
        )


# ===========================================================================
# Boxplot Chart Builder
# ===========================================================================

class BoxplotChartBuilder:
    """
    Builds a grid of Plotly Box traces, one per numeric column.

    Layout:
        - max 4 subplots per row (configurable via _SUBPLOT_COLS constant)
        - Outlier points rendered with a distinct filled orange marker
        - Median line in emerald green
        - Box fill in indigo-500
        - Dark-mode palette matching the project's chart style
        - Exported at 1600px wide, dynamic height via Kaleido
    """

    def build(
        self,
        df: pd.DataFrame,
        columns: list[str],
        column_results: dict[str, ColumnOutlierResult],
        dataset_id: str,
        method_name: str,
    ) -> go.Figure:
        """
        Build the boxplot grid figure.

        Args:
            df:             Source DataFrame.
            columns:        Numeric columns to plot.
            column_results: Detection results (for annotation overlay).
            dataset_id:     Used in the chart title.
            method_name:    Detection method used (shown in subtitle).

        Returns:
            Fully configured Plotly Figure.
        """
        n = len(columns)
        if n == 0:
            # Blank placeholder figure
            return go.Figure(layout=go.Layout(
                title="No numeric columns to plot",
                paper_bgcolor=_PAPER_COLOR,
                plot_bgcolor=_BG_COLOR,
            ))

        # Grid geometry
        n_cols = min(_SUBPLOT_COLS, n)
        n_rows = math.ceil(n / n_cols)

        # Build subtitle annotations for each subplot
        subplot_titles = []
        for col in columns:
            res = column_results.get(col)
            if res:
                subtitle = f"<b>{col}</b>  ({res.outlier_count} outliers, {res.outlier_pct:.1f}%)"
            else:
                subtitle = f"<b>{col}</b>"
            subplot_titles.append(subtitle)

        # Pad to fill last row
        subplot_titles += [""] * (n_cols * n_rows - n)

        fig = make_subplots(
            rows=n_rows,
            cols=n_cols,
            subplot_titles=subplot_titles,
            vertical_spacing=0.12,
            horizontal_spacing=0.06,
        )

        for idx, col in enumerate(columns):
            row = idx // n_cols + 1
            col_pos = idx % n_cols + 1

            series = df[col].dropna()
            arr    = series.to_numpy(dtype=float)
            res    = column_results.get(col)

            # Separate inlier and outlier values for distinct rendering
            if res and res.outlier_indices:
                outlier_set = set(res.outlier_indices)
                inlier_vals  = series.loc[
                    [i for i in series.index if i not in outlier_set]
                ].tolist()
                outlier_vals = series.loc[
                    [i for i in series.index if i in outlier_set]
                ].tolist()
            else:
                inlier_vals  = series.tolist()
                outlier_vals = []

            # ── Main box (inliers + all data for box stats) ───────────────
            fig.add_trace(
                go.Box(
                    y=arr.tolist(),
                    name=col,
                    boxpoints=False,         # hide individual points; we draw them separately
                    marker=dict(
                        color=_BOX_COLOR,
                        opacity=0.85,
                    ),
                    line=dict(color=_BOX_COLOR, width=1.5),
                    fillcolor=f"rgba(99,102,241,0.25)",   # indigo-500, 25% opacity
                    whiskerwidth=0.5,
                    showlegend=False,
                    hovertemplate=(
                        f"<b>{col}</b><br>"
                        "Q1: %{q1:.3f}<br>"
                        "Median: %{median:.3f}<br>"
                        "Q3: %{q3:.3f}<br>"
                        "<extra></extra>"
                    ),
                ),
                row=row, col=col_pos,
            )

            # ── Inlier scatter points (small, muted) ──────────────────────
            if inlier_vals:
                jitter = np.random.uniform(-0.15, 0.15, size=len(inlier_vals))
                fig.add_trace(
                    go.Scatter(
                        x=jitter.tolist(),
                        y=inlier_vals,
                        mode="markers",
                        marker=dict(
                            color=_MUTED_COLOR,
                            size=3,
                            opacity=0.35,
                        ),
                        showlegend=False,
                        hoverinfo="skip",
                    ),
                    row=row, col=col_pos,
                )

            # ── Outlier scatter points (large, orange, labelled) ──────────
            if outlier_vals:
                jitter_o = np.random.uniform(-0.12, 0.12, size=len(outlier_vals))
                fig.add_trace(
                    go.Scatter(
                        x=jitter_o.tolist(),
                        y=outlier_vals,
                        mode="markers",
                        marker=dict(
                            color=_OUTLIER_COLOR,
                            size=7,
                            opacity=0.85,
                            line=dict(color="#fff8f1", width=0.8),
                            symbol="circle",
                        ),
                        name="Outlier" if idx == 0 else None,
                        showlegend=(idx == 0),
                        hovertemplate=f"<b>{col}</b><br>Value: %{{y:.4f}}<br><b>OUTLIER</b><extra></extra>",
                    ),
                    row=row, col=col_pos,
                )

            # ── IQR fence lines (where applicable) ───────────────────────
            if res and res.lower_bound is not None:
                for fence_val, label in [
                    (res.lower_bound, "Lower fence"),
                    (res.upper_bound, "Upper fence"),
                ]:
                    if fence_val is not None:
                        fig.add_hline(
                            y=fence_val,
                            line_dash="dot",
                            line_color="rgba(249,115,22,0.50)",
                            line_width=1,
                            row=row, col=col_pos,
                            annotation_text=f"{label}: {fence_val:.2f}",
                            annotation_font=dict(
                                size=8,
                                color="rgba(249,115,22,0.80)",
                                family=_FONT_FAMILY,
                            ),
                            annotation_position="right",
                        )

        # ── Global layout ─────────────────────────────────────────────────
        chart_height = _TOP_MARGIN + n_rows * _SUBPLOT_HEIGHT

        fig.update_layout(
            title=dict(
                text=(
                    f"Outlier Detection — Boxplots"
                    f"<br><span style='font-size:13px;color:{_MUTED_COLOR}'>"
                    f"Method: <b>{method_name.upper()}</b>  ·  "
                    f"{n} numeric columns  ·  "
                    f"<span style='color:{_OUTLIER_COLOR}'>● Outlier points</span>"
                    f"</span>"
                ),
                font=dict(family=_FONT_FAMILY, size=21, color=_TEXT_COLOR),
                x=0.5, xanchor="center",
                y=0.99, yanchor="top",
            ),
            paper_bgcolor=_PAPER_COLOR,
            plot_bgcolor=_BG_COLOR,
            font=dict(family=_FONT_FAMILY, color=_TEXT_COLOR),
            width=_CHART_WIDTH,
            height=chart_height,
            margin=dict(l=60, r=40, t=_TOP_MARGIN, b=60),
            showlegend=True,
            legend=dict(
                orientation="h",
                x=0.99, xanchor="right",
                y=1.0, yanchor="top",
                bgcolor="rgba(0,0,0,0)",
                font=dict(family=_FONT_FAMILY, size=11, color=_MUTED_COLOR),
            ),
            hoverlabel=dict(
                bgcolor="#1e293b",
                bordercolor="#475569",
                font=dict(family=_FONT_FAMILY, size=12, color="#e2e8f0"),
            ),
        )

        # Apply dark axis styles to every subplot
        for i in range(1, n_rows * n_cols + 1):
            xref = f"xaxis{i}" if i > 1 else "xaxis"
            yref = f"yaxis{i}" if i > 1 else "yaxis"
            for axis_ref in [xref, yref]:
                axis_updates = dict(
                    gridcolor=_GRID_COLOR,
                    zerolinecolor=_GRID_COLOR,
                    showgrid=True,
                    zeroline=True,
                    tickfont=dict(family=_FONT_FAMILY, size=10, color=_MUTED_COLOR),
                    title_font=dict(family=_FONT_FAMILY, size=10, color=_MUTED_COLOR),
                )
                fig.update_layout(**{axis_ref: axis_updates})

        # Style subplot titles
        for annotation in fig.layout.annotations:
            annotation.update(
                font=dict(family=_FONT_FAMILY, size=12, color=_TEXT_COLOR),
            )

        return fig

    def export_png(
        self,
        fig: go.Figure,
        plots_dir: pathlib.Path,
        dataset_id: str,
        method_name: str,
    ) -> tuple[pathlib.Path, int]:
        """
        Export the Plotly figure to a PNG file.

        Filename is deterministic per (dataset_id, method) pair so repeated
        calls overwrite the previous chart rather than filling disk.

        Args:
            fig:         Plotly Figure to export.
            plots_dir:   Target directory.
            dataset_id:  Used in the filename.
            method_name: Used in the filename.

        Returns:
            (absolute path to PNG, file size in bytes)
        """
        plots_dir.mkdir(parents=True, exist_ok=True)
        filename    = f"outliers_{method_name}_{dataset_id}.png"
        output_path = plots_dir / filename

        fig.write_image(
            str(output_path),
            format="png",
            width=_CHART_WIDTH,
            height=fig.layout.height,
            scale=1,
            engine="kaleido",
        )
        size = output_path.stat().st_size
        logger.info(
            "Boxplot chart exported",
            path=str(output_path),
            size_kb=round(size / 1024, 2),
        )
        return output_path, size


# ===========================================================================
# Detection Engine — orchestrates strategies across all columns
# ===========================================================================

class OutlierDetectionEngine:
    """
    Selects and runs the appropriate detection strategy across target columns.

    Strategy registry:
        _STRATEGY_REGISTRY maps method names to strategy instances.
        Adding a new strategy = add one entry to the dict; no other change needed.
    """

    # -------------- Strategy registry (open for extension) ----------------
    _STRATEGY_REGISTRY: dict[str, OutlierDetectionStrategy] = {
        OutlierMethod.IQR.value:              IQRStrategy(),
        OutlierMethod.ZSCORE.value:           ZScoreStrategy(),
        OutlierMethod.ISOLATION_FOREST.value: IsolationForestStrategy(),
    }
    # ----------------------------------------------------------------------

    @classmethod
    def available_methods(cls) -> list[MethodCatalogEntry]:
        """Return catalogue entries for all registered strategies."""
        return [s.catalog_entry() for s in cls._STRATEGY_REGISTRY.values()]

    def run(
        self,
        df: pd.DataFrame,
        target_cols: list[str],
        request: OutlierDetectionRequest,
        warnings: list[str],
    ) -> dict[str, ColumnOutlierResult]:
        """
        Run the selected detection strategy across all target columns.

        For Isolation Forest with multivariate=True, delegates to
        detect_multivariate() for a joint fit.  All other methods run
        per-column.

        Args:
            df:          Source DataFrame.
            target_cols: Numeric columns to process.
            request:     Full request with method selection and config.
            warnings:    Mutable list for non-fatal messages.

        Returns:
            Dict of column_name → ColumnOutlierResult.
        """
        method_key = request.method.value
        strategy   = self._STRATEGY_REGISTRY.get(method_key)

        if strategy is None:
            raise ValueError(f"Unknown detection method: '{method_key}'")

        logger.info(
            "Running outlier detection",
            method=method_key,
            columns=len(target_cols),
        )

        # Isolation Forest multivariate path
        if (
            method_key == OutlierMethod.ISOLATION_FOREST.value
            and request.isolation_forest.multivariate
        ):
            try:
                return strategy.detect_multivariate(df, target_cols, request)
            except Exception as exc:
                msg = f"Multivariate Isolation Forest failed: {exc} — falling back to per-column"
                warnings.append(msg)
                logger.warning(msg)

        # Per-column univariate path (default)
        results: dict[str, ColumnOutlierResult] = {}
        for col in target_cols:
            try:
                results[col] = strategy.detect_column(df[col], request)
            except Exception as exc:
                msg = f"Failed to process column '{col}': {exc}"
                warnings.append(msg)
                logger.warning(msg, column=col)
        return results


# ===========================================================================
# Top-level Outlier Detection Service
# ===========================================================================

class OutlierDetectionService:
    """
    Orchestrates the full outlier detection and visualisation pipeline:

    1. Load DataFrame via DatasetService.
    2. Resolve target numeric columns.
    3. Run detection via OutlierDetectionEngine.
    4. Build boxplot grid via BoxplotChartBuilder.
    5. Export PNG and assemble OutlierDetectionReport.
    """

    def __init__(
        self,
        dataset_service: Any,
        plots_dir: pathlib.Path,
    ) -> None:
        self._dataset_service = dataset_service
        self._plots_dir       = plots_dir
        self._engine          = OutlierDetectionEngine()
        self._chart_builder   = BoxplotChartBuilder()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def detect(
        self,
        dataset_id: str,
        request: OutlierDetectionRequest,
        api_base_url: str = "/api/v1",
    ) -> OutlierDetectionReport:
        """
        Run the full outlier detection + boxplot pipeline.

        Args:
            dataset_id:   UUID of the dataset.
            request:      Request config (method, columns, chart flag, etc.)
            api_base_url: Used to construct chart download URL.

        Returns:
            OutlierDetectionReport.
        """
        t_start   = time.perf_counter()
        warnings: list[str] = []

        # ── Load data ─────────────────────────────────────────────────────
        df: pd.DataFrame = self._dataset_service.load_dataframe(dataset_id)
        total_rows = len(df)

        logger.info(
            "Outlier detection started",
            dataset_id=dataset_id,
            method=request.method.value,
            rows=total_rows,
        )

        # ── Resolve target columns ─────────────────────────────────────────
        all_numeric   = df.select_dtypes(include=[np.number]).columns.tolist()
        target_cols, skipped = self._resolve_columns(
            requested=request.columns,
            all_numeric=all_numeric,
            df=df,
            warnings=warnings,
        )

        if skipped:
            warnings.append(f"Skipped non-numeric / missing columns: {skipped}")

        # ── Run detection ──────────────────────────────────────────────────
        col_results: dict[str, ColumnOutlierResult] = self._engine.run(
            df=df,
            target_cols=target_cols,
            request=request,
            warnings=warnings,
        )

        # ── Aggregate cross-column stats ───────────────────────────────────
        all_outlier_indices: set[int] = set()
        affected_cols: list[str] = []
        total_cells = 0

        for col, res in col_results.items():
            total_cells += res.outlier_count
            if res.outlier_count > 0:
                affected_cols.append(col)
                all_outlier_indices.update(res.outlier_indices)

        # ── Build boxplots (optional) ──────────────────────────────────────
        chart_info: BoxplotChartInfo | None = None

        if request.generate_boxplots and target_cols:
            try:
                fig = self._chart_builder.build(
                    df=df,
                    columns=target_cols,
                    column_results=col_results,
                    dataset_id=dataset_id,
                    method_name=request.method.value,
                )
                chart_path, file_size = self._chart_builder.export_png(
                    fig=fig,
                    plots_dir=self._plots_dir,
                    dataset_id=dataset_id,
                    method_name=request.method.value,
                )
                chart_info = BoxplotChartInfo(
                    chart_path=str(chart_path),
                    chart_filename=chart_path.name,
                    chart_url=f"{api_base_url}/outliers/boxplots/{dataset_id}?method={request.method.value}",
                    width_px=_CHART_WIDTH,
                    height_px=fig.layout.height,
                    file_size_kb=round(file_size / 1024, 2),
                    columns_plotted=len(target_cols),
                )
            except Exception as exc:
                msg = f"Boxplot generation failed: {exc}"
                warnings.append(msg)
                logger.warning(msg)

        elapsed_ms = round((time.perf_counter() - t_start) * 1000, 2)
        logger.info(
            "Outlier detection complete",
            dataset_id=dataset_id,
            method=request.method.value,
            affected_cols=len(affected_cols),
            total_outlier_rows=len(all_outlier_indices),
            elapsed_ms=elapsed_ms,
        )

        return OutlierDetectionReport(
            dataset_id=dataset_id,
            method=request.method.value,
            total_rows=total_rows,
            columns_analysed=len(target_cols),
            total_outlier_rows=len(all_outlier_indices),
            total_outlier_cells=total_cells,
            affected_columns=affected_cols,
            affected_row_indices=sorted(all_outlier_indices),
            column_results=col_results,
            chart=chart_info,
            warnings=warnings,
            elapsed_ms=elapsed_ms,
        )

    def available_methods(self) -> list[MethodCatalogEntry]:
        """Delegate to engine strategy registry."""
        return self._engine.available_methods()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _resolve_columns(
        requested: list[str],
        all_numeric: list[str],
        df: pd.DataFrame,
        warnings: list[str],
    ) -> tuple[list[str], list[str]]:
        if not requested:
            return all_numeric, []

        target, skipped = [], []
        for col in requested:
            if col not in df.columns:
                warnings.append(f"Column '{col}' not found — skipped.")
                skipped.append(col)
            elif not pd.api.types.is_numeric_dtype(df[col]):
                warnings.append(f"Column '{col}' is not numeric — skipped.")
                skipped.append(col)
            else:
                target.append(col)
        return target, skipped
