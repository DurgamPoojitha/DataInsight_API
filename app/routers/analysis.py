"""
DataInsight API — Statistical Analysis Router
===============================================
HTTP interface for the statistical analysis engine.

Endpoints:
    POST  /api/v1/analysis/describe/{dataset_id}
          Full statistical profile for all (or specified) numeric columns.

    POST  /api/v1/analysis/column/{dataset_id}/{column_name}
          Statistical profile for a single named column.

    GET   /api/v1/analysis/numeric-columns/{dataset_id}
          List all numeric columns in the dataset (no heavy computation).

Design:
    - Zero business logic in route handlers.
    - StatisticalAnalysisEngine constructed per-request via Depends().
    - ValueError from the engine (bad column name/type) is surfaced as HTTP 422.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.schemas.analysis import (
    AnalysisRequest,
    ColumnStatistics,
    DatasetStatistics,
)
from app.schemas.response import SuccessResponse
from app.services.dataset_service import DatasetService
from app.services.stats_service import StatisticalAnalysisEngine
from app.routers.dependencies import get_dataset_service, get_cache
from app.utils.cache import RedisCache
from app.utils.logger import get_logger

import numpy as np

logger = get_logger(__name__)

router = APIRouter(
    prefix="/analysis",
    tags=["Statistical Analysis"],
)


# ---------------------------------------------------------------------------
# Dependency helpers
# ---------------------------------------------------------------------------

def _get_analysis_engine(
    service: DatasetService = Depends(get_dataset_service),
) -> StatisticalAnalysisEngine:
    """
    Construct a fresh StatisticalAnalysisEngine per request.

    Stateless per-request construction avoids any shared mutable state
    between concurrent requests.
    """
    return StatisticalAnalysisEngine(dataset_service=service)


# ---------------------------------------------------------------------------
# Endpoint 1: Full dataset statistical profile
# ---------------------------------------------------------------------------

@router.post(
    "/describe/{dataset_id}",
    response_model=SuccessResponse[DatasetStatistics],
    status_code=status.HTTP_200_OK,
    summary="Compute full statistical profile for all numeric columns",
    description=(
        "Runs descriptive statistics on every numeric column in the dataset "
        "(or a caller-specified subset).  Computes:\n\n"
        "**Central tendency**: mean, median, mode(s)\n\n"
        "**Spread**: min, max, range, variance (ddof=1), std deviation, "
        "coefficient of variation\n\n"
        "**Quartiles**: Q1, Q2 (median), Q3, IQR\n\n"
        "**Percentiles**: p1, p5, p10, p25, p50, p75, p90, p95, p99 "
        "(plus any custom points requested)\n\n"
        "**Distribution shape**: skewness (Fisher–Pearson), excess kurtosis "
        "(Fisher definition), with human-readable interpretations\n\n"
        "**Outliers**: Tukey IQR fences, outlier count and percentage\n\n"
        "**Performance**: automatically uses a NumPy fast-path for datasets "
        f"exceeding the large_dataset_threshold (default 100,000 rows)"
    ),
    responses={
        200: {"description": "Statistical profile computed"},
        404: {"description": "Dataset not found"},
        422: {"description": "Invalid column name or type"},
    },
)
async def describe_dataset(
    dataset_id: str,
    request: AnalysisRequest,
    engine: StatisticalAnalysisEngine = Depends(_get_analysis_engine),
    cache: RedisCache | None = Depends(get_cache),
) -> SuccessResponse[DatasetStatistics]:
    """
    Compute full descriptive statistics for all (or specified) numeric columns.

    Args:
        dataset_id: UUID of the dataset to analyse.
        request:    AnalysisRequest body controlling which columns, NaN
                    policy, additional percentiles, and performance threshold.
        cache:      Injected RedisCache instance.

    Returns:
        SuccessResponse wrapping DatasetStatistics.
    """
    import hashlib
    # Generate a cache key based on the dataset ID and request body
    req_hash = hashlib.md5(request.model_dump_json().encode()).hexdigest()
    cache_key = f"stats:{dataset_id}:{req_hash}"
    
    if cache:
        cached_data = cache.get(cache_key, DatasetStatistics)
        if cached_data:
            return SuccessResponse(data=cached_data)

    logger.info(
        "Analysis describe request",
        dataset_id=dataset_id,
        columns=request.columns or "all numeric",
        nan_policy=request.nan_policy,
    )

    result: DatasetStatistics = engine.analyse(
        dataset_id=dataset_id,
        request=request,
    )
    
    if cache:
        cache.set(cache_key, result)
        
    return SuccessResponse(data=result)


# ---------------------------------------------------------------------------
# Endpoint 2: Single-column statistics
# ---------------------------------------------------------------------------

@router.post(
    "/column/{dataset_id}/{column_name}",
    response_model=SuccessResponse[ColumnStatistics],
    status_code=status.HTTP_200_OK,
    summary="Compute statistics for a single column",
    description=(
        "Returns a full `ColumnStatistics` object for exactly one named column.  "
        "More efficient than `/describe` when only one column's stats are needed.  "
        "Raises HTTP 422 if the column is missing or non-numeric."
    ),
    responses={
        200: {"description": "Column statistics computed"},
        404: {"description": "Dataset not found"},
        422: {"description": "Column not found or not numeric"},
    },
)
async def describe_column(
    dataset_id: str,
    column_name: str,
    request: AnalysisRequest,
    engine: StatisticalAnalysisEngine = Depends(_get_analysis_engine),
    cache: RedisCache | None = Depends(get_cache),
) -> SuccessResponse[ColumnStatistics]:
    """
    Compute descriptive statistics for a single named column.

    Args:
        dataset_id:  UUID of the dataset.
        column_name: Name of the column to analyse.
        request:     AnalysisRequest options (NaN policy, percentiles, etc.)
        engine:      Injected StatisticalAnalysisEngine.
        cache:       Injected RedisCache instance.

    Returns:
        SuccessResponse wrapping ColumnStatistics.
    """
    import hashlib
    req_hash = hashlib.md5(request.model_dump_json().encode()).hexdigest()
    cache_key = f"stats:col:{dataset_id}:{column_name}:{req_hash}"
    
    if cache:
        cached_data = cache.get(cache_key, ColumnStatistics)
        if cached_data:
            return SuccessResponse(data=cached_data)

    logger.info(
        "Single-column analysis request",
        dataset_id=dataset_id,
        column=column_name,
        nan_policy=request.nan_policy,
    )

    try:
        result: ColumnStatistics = engine.analyse_column(
            dataset_id=dataset_id,
            column_name=column_name,
            request=request,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    if cache:
        cache.set(cache_key, result)

    return SuccessResponse(data=result)


# ---------------------------------------------------------------------------
# Endpoint 3: List numeric columns (lightweight, no heavy computation)
# ---------------------------------------------------------------------------

@router.get(
    "/numeric-columns/{dataset_id}",
    status_code=status.HTTP_200_OK,
    summary="List all numeric columns in a dataset",
    description=(
        "Returns the names and dtypes of all numeric columns in the dataset "
        "without running any statistical computations.  Useful for building "
        "UI dropdowns or deciding which columns to pass to `/describe`."
    ),
    responses={
        200: {"description": "Numeric column list returned"},
        404: {"description": "Dataset not found"},
    },
)
async def list_numeric_columns(
    dataset_id: str,
    service: DatasetService = Depends(get_dataset_service),
) -> SuccessResponse[dict]:
    """
    Return all numeric column names and their dtypes without computing stats.

    Args:
        dataset_id: UUID of the dataset.
        service:    Injected DatasetService.

    Returns:
        SuccessResponse with columns list and dataset shape.
    """
    logger.info("Numeric columns request", dataset_id=dataset_id)

    df = service.load_dataframe(dataset_id)
    numeric_df = df.select_dtypes(include=[np.number])

    columns_info = [
        {
            "name": col,
            "dtype": str(numeric_df[col].dtype),
            "non_null_count": int(numeric_df[col].notna().sum()),
            "null_count": int(numeric_df[col].isna().sum()),
        }
        for col in numeric_df.columns
    ]

    return SuccessResponse(data={
        "dataset_id": dataset_id,
        "total_rows": len(df),
        "total_columns": len(df.columns),
        "numeric_column_count": len(numeric_df.columns),
        "columns": columns_info,
    })
