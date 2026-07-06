"""
DataInsight API — Correlation Router
====================================
HTTP interface for correlation matrix analysis.
"""

from __future__ import annotations

import pathlib

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse

from app.schemas.correlation import (
    CorrelationMethod,
    CorrelationReport,
    CorrelationRequest,
)
from app.schemas.response import SuccessResponse
from app.services.dataset_service import DatasetService
from app.services.correlation_service import CorrelationService
from app.routers.dependencies import get_dataset_service, get_cache
from app.utils.cache import RedisCache
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/correlation",
    tags=["Correlation Analysis"],
)


def _get_dataset_service() -> DatasetService:
    from app.main import app
    return app.state.dataset_service


def _get_plots_dir() -> pathlib.Path:
    from app.main import PLOTS_DIR
    return PLOTS_DIR


def _get_correlation_service(
    service: DatasetService = Depends(get_dataset_service),
    plots_dir: pathlib.Path = Depends(_get_plots_dir),
) -> CorrelationService:
    return CorrelationService(
        dataset_service=service,
        plots_dir=plots_dir,
    )


@router.post(
    "/analyse/{dataset_id}",
    response_model=SuccessResponse[CorrelationReport],
    status_code=status.HTTP_200_OK,
    summary="Compute correlation matrix and generate heatmaps",
    description=(
        "Computes the correlation matrix for numeric columns using Pearson, "
        "Spearman, or Kendall correlation. Extracts the strongest positive "
        "and negative pairs, and lists highly correlated pairs.\n\n"
        "Generates an interactive Plotly heatmap exported as HTML and a "
        "static PNG version."
    ),
)
async def analyse_correlation(
    dataset_id: str,
    request: CorrelationRequest,
    svc: CorrelationService = Depends(_get_correlation_service),
    cache: RedisCache | None = Depends(get_cache),
) -> SuccessResponse[CorrelationReport]:
    """Run correlation analysis."""
    import hashlib
    req_hash = hashlib.md5(request.model_dump_json().encode()).hexdigest()
    cache_key = f"corr:{dataset_id}:{req_hash}"

    if cache:
        cached_data = cache.get(cache_key, CorrelationReport)
        if cached_data:
            return SuccessResponse(data=cached_data)

    logger.info("Correlation analysis request", dataset_id=dataset_id)
    report = svc.analyse(
        dataset_id=dataset_id,
        request=request,
        api_base_url="/api/v1",
    )

    if cache:
        cache.set(cache_key, report)

    return SuccessResponse(data=report)


@router.get(
    "/chart/{dataset_id}",
    summary="Download correlation heatmap chart",
    description="Download the generated PNG or interactive HTML heatmap.",
    response_class=FileResponse,
)
async def download_chart(
    dataset_id: str,
    method: CorrelationMethod = Query(default=CorrelationMethod.PEARSON),
    fmt: str = Query(default="png", description="Format: 'png' or 'html'"),
    plots_dir: pathlib.Path = Depends(_get_plots_dir),
) -> FileResponse:
    """Download pre-generated chart."""
    if fmt not in ["png", "html"]:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Format must be 'png' or 'html'."
        )

    filename = f"correlation_{method.value}_{dataset_id}.{fmt}"
    chart_path = plots_dir / filename

    if not chart_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chart '{filename}' not found. Run analysis first."
        )

    media_type = "image/png" if fmt == "png" else "text/html"
    return FileResponse(
        path=str(chart_path),
        media_type=media_type,
        filename=filename,
    )
