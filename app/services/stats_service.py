"""
DataInsight API — Statistical Analysis Engine
===============================================
High-performance, NaN-aware statistical engine for numeric DataFrame columns.

Architecture (SOLID):
┌──────────────────────────────────────────────────────────────────────────┐
│                    StatisticalAnalysisEngine                             │
│   ┌────────────────────────┐   ┌───────────────────────────────────────┐ │
│   │  NaNAwareArrayBuilder  │   │       ColumnStatsCalculator           │ │
│   │  (data preparation)    │   │  ┌─────────────────────────────────┐  │ │
│   └────────────────────────┘   │  │ CentralTendencyCalculator       │  │ │
│                                │  │ SpreadCalculator                │  │ │
│                                │  │ PercentilesCalculator           │  │ │
│                                │  │ DistributionShapeCalculator     │  │ │
│                                │  │ OutlierCalculator               │  │ │
│                                │  └─────────────────────────────────┘  │ │
│                                └───────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────┘

Performance Strategy (>100k rows):
  - NumPy fast path: convert pandas Series → np.ndarray once,
    use nanmean/nanmedian/nanvar/nanstd/nanpercentile throughout.
  - All NaN removal done in a single pass (dropna → .to_numpy()).
  - scipy.stats used only for skewness and kurtosis (both are vectorised C).
  - Avoid any Python-level loops over rows.
  - Mode computed with numpy.unique() + argmax (O(n log n), avoids pandas overhead).

NaN Handling:
  - 'omit' policy (default): each statistic uses only valid (non-NaN) values.
  - 'zero'  policy: NaN replaced with 0 before all calculations.
  - np.nanXXX functions used throughout — no silent NaN propagation.

SOLID Principles:
  S — Each calculator class handles exactly one concern.
  O — New stat groups added by subclassing AbstractStatCalculator.
  L — All calculators interchangeable via the abstract interface.
  I — AbstractStatCalculator exposes only compute(arr).
  D — ColumnStatsCalculator depends on abstractions, not concrete calculators.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats

from app.schemas.analysis import (
    AnalysisRequest,
    ColumnStatistics,
    DatasetStatistics,
    DistributionShape,
    OutlierStats,
    PerformanceInfo,
    QuartileStats,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Default percentile points always computed (regardless of request config)
_DEFAULT_PERCENTILES: list[float] = [1, 5, 10, 25, 50, 75, 90, 95, 99]

# Minimum number of valid observations required to compute variance / std / shape
_MIN_FOR_VARIANCE: int = 2
_MIN_FOR_SHAPE: int = 3


# ---------------------------------------------------------------------------
# Utility: safe scalar coercion for JSON
# ---------------------------------------------------------------------------

def _f(value: Any) -> float | None:
    """
    Convert a numpy scalar to a Python float, returning None for NaN/Inf.

    Used throughout to ensure every field in the response is JSON-safe.

    Args:
        value: Any numeric value (numpy scalar, Python float, etc.)

    Returns:
        Python float, or None if the value is NaN, Inf, or not finite.
    """
    if value is None:
        return None
    try:
        v = float(value)
        return v if np.isfinite(v) else None
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Data preparation: NaN-aware array builder
# ---------------------------------------------------------------------------

class NaNAwareArrayBuilder:
    """
    Prepares a clean numpy array from a pandas Series, applying the
    caller's NaN policy.

    Responsibilities:
      - Apply 'omit' or 'zero' NaN policy.
      - Expose the full array (for total_count, nan_count) and the
        valid-only array (for actual statistics).
      - Perform the Series → ndarray conversion exactly once.

    This is the single point of data ingestion for the statistics pipeline.
    """

    def __init__(self, series: pd.Series, nan_policy: str = "omit") -> None:
        """
        Args:
            series:     A pandas Series (numeric dtype).
            nan_policy: 'omit' to drop NaN, 'zero' to replace with 0.
        """
        self._policy: str = nan_policy

        # Full array (preserves NaN, used for count/nan stats)
        self._full: np.ndarray = series.to_numpy(dtype=float, na_value=np.nan)

        # Valid array (NaN removed or replaced, used for all statistics)
        if nan_policy == "zero":
            self._valid: np.ndarray = np.where(
                np.isnan(self._full), 0.0, self._full
            )
        else:
            # 'omit' — drop NaN entirely (single allocation)
            self._valid = self._full[~np.isnan(self._full)]

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def full(self) -> np.ndarray:
        """Full array including NaN positions."""
        return self._full

    @property
    def valid(self) -> np.ndarray:
        """Clean array with NaN handled per policy (used for all stats)."""
        return self._valid

    @property
    def total_count(self) -> int:
        """Total row count (including NaN)."""
        return len(self._full)

    @property
    def valid_count(self) -> int:
        """Number of non-NaN values."""
        if self._policy == "zero":
            return int(np.isfinite(self._full).sum())
        return len(self._valid)

    @property
    def nan_count(self) -> int:
        """Number of NaN values in the original series."""
        return int(np.isnan(self._full).sum())

    @property
    def nan_pct(self) -> float:
        """Percentage of NaN values (0–100)."""
        if self.total_count == 0:
            return 0.0
        return round(self.nan_count / self.total_count * 100, 4)


# ---------------------------------------------------------------------------
# Abstract base for stat calculators
# ---------------------------------------------------------------------------

class AbstractStatCalculator(ABC):
    """
    Base class for all statistical calculators.

    Subclasses each handle one group of statistics (central tendency, spread,
    percentiles, distribution shape, outliers).  The compute() method receives
    the pre-built NaNAwareArrayBuilder and returns a plain dict of results.

    Extensibility:
        To add a new statistics group, subclass AbstractStatCalculator and
        implement compute().  Register an instance in ColumnStatsCalculator.
    """

    @abstractmethod
    def compute(self, builder: NaNAwareArrayBuilder) -> dict[str, Any]:
        """
        Compute statistics from the clean array.

        Args:
            builder: Pre-built NaNAwareArrayBuilder with full and valid arrays.

        Returns:
            Dict of stat_name → value (Python/numpy scalars).
        """
        ...


# ---------------------------------------------------------------------------
# Calculator 1 — Central Tendency
# ---------------------------------------------------------------------------

class CentralTendencyCalculator(AbstractStatCalculator):
    """
    Computes mean, median, and mode(s) of the valid-values array.

    Mode algorithm:
      Uses numpy.unique(return_counts=True) which is O(n log n) and
      significantly faster than scipy.stats.mode for large arrays.
      Returns ALL values tied for the highest frequency (multi-modal support).
    """

    def compute(self, builder: NaNAwareArrayBuilder) -> dict[str, Any]:
        arr = builder.valid

        if len(arr) == 0:
            return {
                "mean": None,
                "median": None,
                "mode": [],
                "mode_count": 0,
            }

        mean: float | None   = _f(np.mean(arr))
        median: float | None = _f(np.median(arr))
        mode_vals, mode_count = self._compute_mode(arr)

        return {
            "mean": mean,
            "median": median,
            "mode": mode_vals,
            "mode_count": mode_count,
        }

    def _compute_mode(self, arr: np.ndarray) -> tuple[list[float], int]:
        """
        Find all mode values efficiently using numpy.unique.

        Returns:
            (list of modal values as Python floats, count of modal values)
        """
        if len(arr) == 0:
            return [], 0

        unique_vals, counts = np.unique(arr, return_counts=True)
        max_count: int = int(counts.max())
        modal_vals: list[float] = [
            _f(v) for v in unique_vals[counts == max_count]
        ]
        # Trim to at most 10 modes to avoid enormous responses
        return [v for v in modal_vals[:10] if v is not None], len(modal_vals)


# ---------------------------------------------------------------------------
# Calculator 2 — Spread
# ---------------------------------------------------------------------------

class SpreadCalculator(AbstractStatCalculator):
    """
    Computes minimum, maximum, range, variance, standard deviation,
    and coefficient of variation.

    Uses ddof=1 (sample statistics) which is the statistically correct
    default for data samples (as opposed to the entire population).

    Optimised for large arrays using numpy vectorised operations throughout.
    """

    def compute(self, builder: NaNAwareArrayBuilder) -> dict[str, Any]:
        arr = builder.valid
        n = len(arr)

        if n == 0:
            return {
                "minimum": None, "maximum": None, "range": None,
                "variance": None, "std_dev": None, "coeff_of_variation": None,
            }

        minimum: float | None = _f(arr.min())
        maximum: float | None = _f(arr.max())
        rng: float | None     = _f(maximum - minimum) if (minimum is not None and maximum is not None) else None

        variance: float | None = None
        std_dev: float | None  = None
        cv: float | None       = None

        if n >= _MIN_FOR_VARIANCE:
            var_val = np.var(arr, ddof=1)
            variance = _f(var_val)
            std_val  = np.std(arr, ddof=1)
            std_dev  = _f(std_val)

            # CV = (std / |mean|) × 100  — only meaningful when mean ≠ 0
            mean_val = np.mean(arr)
            if mean_val != 0 and std_dev is not None:
                cv = _f((std_val / abs(mean_val)) * 100)

        return {
            "minimum": minimum,
            "maximum": maximum,
            "range": rng,
            "variance": variance,
            "std_dev": std_dev,
            "coeff_of_variation": cv,
        }


# ---------------------------------------------------------------------------
# Calculator 3 — Percentiles & Quartiles
# ---------------------------------------------------------------------------

class PercentilesCalculator(AbstractStatCalculator):
    """
    Computes quartiles (Q1, Q2, Q3, IQR) and arbitrary percentile points.

    Uses numpy.percentile with 'linear' interpolation (equivalent to pandas
    quantile default).  For large arrays this is the fastest approach as
    numpy's percentile is implemented in C (partitioning algorithm, O(n)).

    The extra percentile points from the request config are merged with
    the fixed default set (_DEFAULT_PERCENTILES) and deduplicated.
    """

    def __init__(self, extra_percentiles: list[float] | None = None) -> None:
        """
        Args:
            extra_percentiles: Additional percentile points (0–100) from request.
        """
        raw: list[float] = list(_DEFAULT_PERCENTILES)
        if extra_percentiles:
            raw.extend(np.clip(extra_percentiles, 0.0, 100.0).tolist())
        # Deduplicate and sort
        self._percentile_points: np.ndarray = np.unique(np.array(raw))

    def compute(self, builder: NaNAwareArrayBuilder) -> dict[str, Any]:
        arr = builder.valid

        if len(arr) == 0:
            return {
                "quartiles": QuartileStats(),
                "percentiles": {f"p{int(p)}": None for p in self._percentile_points},
            }

        # Compute all percentile points in one vectorised call
        pct_values: np.ndarray = np.percentile(arr, self._percentile_points)

        percentile_dict: dict[str, float | None] = {}
        for point, value in zip(self._percentile_points, pct_values):
            # Key format: p25, p75, p99 etc.
            key = f"p{int(point)}" if point == int(point) else f"p{point}"
            percentile_dict[key] = _f(value)

        # Quartiles (extracted from the already-computed array)
        q1_val  = _f(np.percentile(arr, 25))
        q2_val  = _f(np.percentile(arr, 50))
        q3_val  = _f(np.percentile(arr, 75))
        iqr_val = _f(q3_val - q1_val) if (q1_val is not None and q3_val is not None) else None

        quartiles = QuartileStats(q1=q1_val, q2=q2_val, q3=q3_val, iqr=iqr_val)

        return {
            "quartiles": quartiles,
            "percentiles": percentile_dict,
        }


# ---------------------------------------------------------------------------
# Calculator 4 — Distribution Shape (Skewness + Kurtosis)
# ---------------------------------------------------------------------------

class DistributionShapeCalculator(AbstractStatCalculator):
    """
    Computes Fisher–Pearson skewness and excess kurtosis using scipy.stats.

    scipy.stats.skew and scipy.stats.kurtosis are implemented in C and
    handle large arrays efficiently in a single pass.

    Interpretations:
      Skewness:  < -1 highly left-skewed | -1 to -0.5 moderately left-skewed
                 -0.5 to 0.5 approximately symmetric | 0.5 to 1 moderately right-skewed
                 > 1 highly right-skewed
      Kurtosis:  < -1 very platykurtic | -1 to -0.5 platykurtic
                 -0.5 to 0.5 mesokurtic (normal-like)
                 0.5 to 1 leptokurtic | > 1 very leptokurtic (heavy tails)
    """

    def compute(self, builder: NaNAwareArrayBuilder) -> dict[str, Any]:
        arr = builder.valid

        if len(arr) < _MIN_FOR_SHAPE:
            return {
                "distribution": DistributionShape(
                    skewness=None,
                    kurtosis=None,
                    skewness_interpretation="Insufficient data",
                    kurtosis_interpretation="Insufficient data",
                )
            }

        # scipy.stats functions are vectorised C — fast on large arrays
        skew_val: float | None = _f(scipy_stats.skew(arr, bias=False))
        kurt_val: float | None = _f(scipy_stats.kurtosis(arr, fisher=True, bias=False))

        shape = DistributionShape(
            skewness=skew_val,
            kurtosis=kurt_val,
            skewness_interpretation=self._interpret_skewness(skew_val),
            kurtosis_interpretation=self._interpret_kurtosis(kurt_val),
        )
        return {"distribution": shape}

    @staticmethod
    def _interpret_skewness(skew: float | None) -> str:
        if skew is None:
            return "Unknown"
        if skew > 1.0:
            return "Highly right-skewed (long right tail)"
        if skew > 0.5:
            return "Moderately right-skewed"
        if skew >= -0.5:
            return "Approximately symmetric"
        if skew >= -1.0:
            return "Moderately left-skewed"
        return "Highly left-skewed (long left tail)"

    @staticmethod
    def _interpret_kurtosis(kurt: float | None) -> str:
        if kurt is None:
            return "Unknown"
        if kurt > 1.0:
            return "Leptokurtic — heavy tails, sharp peak"
        if kurt > 0.5:
            return "Slightly leptokurtic"
        if kurt >= -0.5:
            return "Mesokurtic — approximately normal tails"
        if kurt >= -1.0:
            return "Slightly platykurtic"
        return "Platykurtic — thin tails, flat peak"


# ---------------------------------------------------------------------------
# Calculator 5 — Outlier Detection (IQR method)
# ---------------------------------------------------------------------------

class OutlierCalculator(AbstractStatCalculator):
    """
    Detects outliers using Tukey's IQR fence method.

    Fences:
        Lower fence = Q1 − 1.5 × IQR
        Upper fence = Q3 + 1.5 × IQR

    Values outside these fences are classified as outliers.
    This is O(n) (single boolean comparison on the numpy array) and
    efficient for any dataset size.
    """

    def compute(self, builder: NaNAwareArrayBuilder) -> dict[str, Any]:
        arr = builder.valid

        if len(arr) < 4:
            return {"outliers": OutlierStats()}

        q1: float = np.percentile(arr, 25)
        q3: float = np.percentile(arr, 75)
        iqr: float = q3 - q1

        lower_fence: float = q1 - 1.5 * iqr
        upper_fence: float = q3 + 1.5 * iqr

        # Boolean mask — fully vectorised, O(n)
        outlier_mask: np.ndarray = (arr < lower_fence) | (arr > upper_fence)
        outlier_count: int = int(outlier_mask.sum())
        outlier_pct: float = round(outlier_count / len(arr) * 100, 4)

        return {
            "outliers": OutlierStats(
                lower_fence=_f(lower_fence),
                upper_fence=_f(upper_fence),
                outlier_count=outlier_count,
                outlier_pct=outlier_pct,
            )
        }


# ---------------------------------------------------------------------------
# Calculator 6 — Frequency Table (optional)
# ---------------------------------------------------------------------------

class FrequencyTableCalculator(AbstractStatCalculator):
    """
    Computes a top-10 value-frequency table for a column.

    Uses numpy.unique(return_counts=True) — O(n log n) — and argpartition
    for efficient top-k selection.  Cheaper than pandas value_counts() for
    large arrays because it avoids index construction overhead.
    """

    def __init__(self, top_k: int = 10) -> None:
        self._top_k = top_k

    def compute(self, builder: NaNAwareArrayBuilder) -> dict[str, Any]:
        arr = builder.valid

        if len(arr) == 0:
            return {"frequency_table": []}

        unique_vals, counts = np.unique(arr, return_counts=True)
        n_unique = len(unique_vals)
        k = min(self._top_k, n_unique)

        # Efficient top-k using argpartition (O(n) instead of full sort)
        if n_unique > k:
            top_idx = np.argpartition(counts, -k)[-k:]
            top_idx = top_idx[np.argsort(counts[top_idx])[::-1]]
        else:
            top_idx = np.argsort(counts)[::-1]

        total = len(arr)
        freq_table = [
            {
                "value": _f(unique_vals[i]),
                "count": int(counts[i]),
                "pct": round(float(counts[i]) / total * 100, 4),
            }
            for i in top_idx
        ]
        return {"frequency_table": freq_table}


# ---------------------------------------------------------------------------
# Column Stats Calculator — orchestrates all sub-calculators
# ---------------------------------------------------------------------------

class ColumnStatsCalculator:
    """
    Orchestrates all statistical sub-calculators for a single column.

    Builds a ColumnStatistics object by:
      1. Building a NaNAwareArrayBuilder (single NaN-removal pass).
      2. Running each AbstractStatCalculator in order.
      3. Merging results into a flat ColumnStatistics response object.

    The list of calculators is injected at construction time, making it easy
    to add or remove stat groups without touching this class (OCP).
    """

    def __init__(
        self,
        calculators: list[AbstractStatCalculator],
        include_frequency_table: bool = False,
        freq_calculator: FrequencyTableCalculator | None = None,
    ) -> None:
        """
        Args:
            calculators:             Ordered list of stat calculators to run.
            include_frequency_table: Whether to run the frequency calculator.
            freq_calculator:         FrequencyTableCalculator instance (or None).
        """
        self._calculators = calculators
        self._include_freq = include_frequency_table
        self._freq_calc = freq_calculator

    def compute(
        self,
        series: pd.Series,
        column_name: str,
        nan_policy: str,
    ) -> ColumnStatistics:
        """
        Compute all statistics for one column.

        Args:
            series:       Numeric pandas Series.
            column_name:  Column name (for the response).
            nan_policy:   'omit' or 'zero'.

        Returns:
            Fully populated ColumnStatistics.
        """
        builder = NaNAwareArrayBuilder(series, nan_policy=nan_policy)
        dtype_str = str(series.dtype)

        # Merge all calculator outputs into a flat dict
        merged: dict[str, Any] = {}
        for calc in self._calculators:
            merged.update(calc.compute(builder))

        # Frequency table (optional)
        freq_table: list[dict] = []
        if self._include_freq and self._freq_calc is not None:
            freq_result = self._freq_calc.compute(builder)
            freq_table = freq_result.get("frequency_table", [])

        # Unique count — efficient with numpy
        unique_count: int = (
            int(np.unique(builder.valid).size) if len(builder.valid) > 0 else 0
        )

        return ColumnStatistics(
            column=column_name,
            dtype=dtype_str,
            total_count=builder.total_count,
            valid_count=builder.valid_count,
            nan_count=builder.nan_count,
            nan_pct=builder.nan_pct,
            # Central tendency
            mean=merged.get("mean"),
            median=merged.get("median"),
            mode=merged.get("mode", []),
            mode_count=merged.get("mode_count", 0),
            # Spread
            minimum=merged.get("minimum"),
            maximum=merged.get("maximum"),
            range=merged.get("range"),
            variance=merged.get("variance"),
            std_dev=merged.get("std_dev"),
            coeff_of_variation=merged.get("coeff_of_variation"),
            # Quartiles & percentiles
            quartiles=merged.get("quartiles", QuartileStats()),
            percentiles=merged.get("percentiles", {}),
            # Distribution shape
            distribution=merged.get("distribution", DistributionShape()),
            # Outliers
            outliers=merged.get("outliers", OutlierStats()),
            # Frequency table
            frequency_table=freq_table,
            # Unique count
            unique_count=unique_count,
        )


# ---------------------------------------------------------------------------
# Statistical Analysis Engine — top-level orchestrator
# ---------------------------------------------------------------------------

class StatisticalAnalysisEngine:
    """
    Top-level orchestrator for the statistical analysis pipeline.

    Responsibilities:
      - Load the DataFrame via DatasetService.
      - Select numeric columns (all or caller-specified subset).
      - Choose the optimal processing path based on dataset size:
          ≤ threshold rows: standard pandas Series → calculator pipeline.
          > threshold rows: pre-convert to numpy array for faster throughput.
      - Assemble the final DatasetStatistics response.

    Performance design:
      - For large datasets, the DataFrame is converted to a dict of numpy
        arrays upfront.  Each column then uses the pre-converted array,
        avoiding repeated Series.to_numpy() call overhead.
      - All stat computations are fully vectorised (no Python loops over rows).
      - Elapsed time is recorded and returned in the performance info.

    Usage:
        engine = StatisticalAnalysisEngine(dataset_service=service)
        result = engine.analyse(dataset_id="abc-123", request=AnalysisRequest())
    """

    def __init__(self, dataset_service: Any) -> None:
        """
        Args:
            dataset_service: Shared DatasetService instance (from app.state).
        """
        self._dataset_service = dataset_service

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyse(
        self,
        dataset_id: str,
        request: AnalysisRequest,
    ) -> DatasetStatistics:
        """
        Run the full statistical analysis pipeline.

        Args:
            dataset_id: UUID of the dataset to analyse.
            request:    AnalysisRequest with column list, NaN policy, options.

        Returns:
            DatasetStatistics with per-column ColumnStatistics and perf info.
        """
        t_start: float = time.perf_counter()

        df: pd.DataFrame = self._dataset_service.load_dataframe(dataset_id)
        warnings: list[str] = []

        # ── Select numeric columns ────────────────────────────────────────
        all_numeric_cols: list[str] = df.select_dtypes(
            include=[np.number]
        ).columns.tolist()

        target_cols, skipped = self._resolve_target_columns(
            requested=request.columns,
            all_numeric=all_numeric_cols,
            df=df,
            warnings=warnings,
        )

        # ── Choose processing path ────────────────────────────────────────
        n_rows: int = len(df)
        use_fast_path: bool = n_rows > request.large_dataset_threshold

        if use_fast_path:
            logger.info(
                "Using NumPy fast path for large dataset",
                dataset_id=dataset_id,
                rows=n_rows,
                threshold=request.large_dataset_threshold,
            )
            # Pre-convert all target columns to numpy arrays in one pass
            # Avoids repeated pandas overhead per column
            numpy_arrays: dict[str, np.ndarray] = {
                col: df[col].to_numpy(dtype=float, na_value=np.nan)
                for col in target_cols
            }

        # ── Build calculator stack ────────────────────────────────────────
        calculators = self._build_calculators(request)
        freq_calc = FrequencyTableCalculator(top_k=10)
        column_calc = ColumnStatsCalculator(
            calculators=calculators,
            include_frequency_table=request.include_frequency_table,
            freq_calculator=freq_calc,
        )

        # ── Run per-column analysis ───────────────────────────────────────
        column_stats: dict[str, ColumnStatistics] = {}

        for col in target_cols:
            logger.debug(
                "Analysing column",
                column=col,
                rows=n_rows,
                fast_path=use_fast_path,
            )
            try:
                if use_fast_path:
                    # Wrap pre-built array back into a Series (zero-copy for numpy)
                    series = pd.Series(numpy_arrays[col], name=col)
                else:
                    series = df[col]

                col_stats = column_calc.compute(
                    series=series,
                    column_name=col,
                    nan_policy=request.nan_policy,
                )
                column_stats[col] = col_stats

            except Exception as exc:
                msg = f"Failed to analyse column '{col}': {exc}"
                warnings.append(msg)
                logger.warning(msg, column=col)

        elapsed_ms: float = round((time.perf_counter() - t_start) * 1000, 2)

        logger.info(
            "Statistical analysis complete",
            dataset_id=dataset_id,
            columns_analysed=len(column_stats),
            elapsed_ms=elapsed_ms,
            fast_path=use_fast_path,
        )

        return DatasetStatistics(
            dataset_id=dataset_id,
            columns=column_stats,
            performance=PerformanceInfo(
                total_rows=n_rows,
                total_columns_analysed=len(column_stats),
                numeric_columns_found=len(all_numeric_cols),
                skipped_columns=skipped,
                fast_path_used=use_fast_path,
                elapsed_ms=elapsed_ms,
            ),
            warnings=warnings,
        )

    def analyse_column(
        self,
        dataset_id: str,
        column_name: str,
        request: AnalysisRequest,
    ) -> ColumnStatistics:
        """
        Run statistical analysis for a single named column.

        More efficient than analyse() when only one column is needed because
        it skips iterating over all numeric columns.

        Args:
            dataset_id:  UUID of the dataset.
            column_name: Column to analyse.
            request:     AnalysisRequest options (NaN policy, percentiles, etc.)

        Returns:
            ColumnStatistics for the requested column.

        Raises:
            ValueError: If the column does not exist or is not numeric.
        """
        df: pd.DataFrame = self._dataset_service.load_dataframe(dataset_id)

        if column_name not in df.columns:
            raise ValueError(f"Column '{column_name}' not found in dataset.")

        if not pd.api.types.is_numeric_dtype(df[column_name]):
            raise ValueError(
                f"Column '{column_name}' is not numeric "
                f"(dtype: {df[column_name].dtype})."
            )

        calculators = self._build_calculators(request)
        freq_calc = FrequencyTableCalculator(top_k=10)
        column_calc = ColumnStatsCalculator(
            calculators=calculators,
            include_frequency_table=request.include_frequency_table,
            freq_calculator=freq_calc,
        )
        return column_calc.compute(
            series=df[column_name],
            column_name=column_name,
            nan_policy=request.nan_policy,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_calculators(
        self, request: AnalysisRequest
    ) -> list[AbstractStatCalculator]:
        """
        Construct the ordered list of stat calculators from the request config.

        Args:
            request: AnalysisRequest with percentile options.

        Returns:
            Ordered list of AbstractStatCalculator instances.
        """
        return [
            CentralTendencyCalculator(),
            SpreadCalculator(),
            PercentilesCalculator(extra_percentiles=request.percentiles),
            DistributionShapeCalculator(),
            OutlierCalculator(),
        ]

    @staticmethod
    def _resolve_target_columns(
        requested: list[str],
        all_numeric: list[str],
        df: pd.DataFrame,
        warnings: list[str],
    ) -> tuple[list[str], list[str]]:
        """
        Resolve which columns to analyse, validating caller-supplied names.

        Args:
            requested:   Caller-supplied column list (may be empty → use all).
            all_numeric: All numeric columns in the DataFrame.
            df:          The full DataFrame (used to check column existence/type).
            warnings:    Mutable list to append non-fatal warning messages to.

        Returns:
            (target_columns, skipped_columns)
        """
        if not requested:
            return all_numeric, []

        target: list[str] = []
        skipped: list[str] = []

        for col in requested:
            if col not in df.columns:
                msg = f"Requested column '{col}' does not exist — skipped."
                warnings.append(msg)
                skipped.append(col)
            elif not pd.api.types.is_numeric_dtype(df[col]):
                msg = (
                    f"Requested column '{col}' is not numeric "
                    f"(dtype: {df[col].dtype}) — skipped."
                )
                warnings.append(msg)
                skipped.append(col)
            else:
                target.append(col)

        return target, skipped
