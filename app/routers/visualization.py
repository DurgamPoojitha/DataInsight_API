"""
DataInsight API — Visualization Router
======================================
HTTP interface for generating and downloading dynamic Plotly charts.
"""

from __future__ import annotations

import pathlib

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse

from app.schemas.response import SuccessResponse
from app.schemas.visualization import (
    VisualizationBatchReport,
    VisualizationBatchRequest,
)
from app.services.dataset_service import DatasetService
from app.services.visualization_service import VisualizationService
from app.routers.dependencies import get_dataset_service, get_cache
from app.utils.cache import RedisCache
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/visualizations",
    tags=["Visualizations"],
)



def _get_plots_dir() -> pathlib.Path:
    from app.main import PLOTS_DIR
    return PLOTS_DIR


def _get_viz_service(
    service: DatasetService = Depends(get_dataset_service),
    plots_dir: pathlib.Path = Depends(_get_plots_dir),
) -> VisualizationService:
    return VisualizationService(
        dataset_service=service,
        plots_dir=plots_dir,
    )


@router.post(
    "/generate/{dataset_id}",
    response_model=SuccessResponse[VisualizationBatchReport],
    status_code=status.HTTP_200_OK,
    summary="Batch generate visualizations",
    description=(
        "Accepts a list of chart requests (histogram, bar, pie, scatter, line, "
        "box, heatmap) and generates them sequentially. Supports exporting to PNG, HTML, or BOTH."
    ),
)
async def generate_visualizations(
    dataset_id: str,
    request: VisualizationBatchRequest,
    svc: VisualizationService = Depends(_get_viz_service),
    cache: RedisCache | None = Depends(get_cache),
) -> SuccessResponse[VisualizationBatchReport]:
    """Generate multiple charts in a single request."""
    import hashlib
    req_hash = hashlib.md5(request.model_dump_json().encode()).hexdigest()
    cache_key = f"viz:{dataset_id}:{req_hash}"

    if cache:
        cached_data = cache.get(cache_key, VisualizationBatchReport)
        if cached_data:
            return SuccessResponse(data=cached_data)

    logger.info("Visualization batch request", dataset_id=dataset_id, charts_count=len(request.charts))
    report = svc.generate_batch(
        dataset_id=dataset_id,
        request=request,
        api_base_url="/api/v1",
    )
    
    if cache:
        cache.set(cache_key, report)
        
    return SuccessResponse(data=report)


@router.get(
    "/chart/{filename}",
    summary="Download a generated chart file",
    description="Returns the PNG or HTML file by filename.",
    response_class=FileResponse,
)
async def download_chart(
    filename: str,
    plots_dir: pathlib.Path = Depends(_get_plots_dir),
) -> FileResponse:
    """Download a pre-generated chart file."""
    chart_path = plots_dir / filename

    if not chart_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chart file '{filename}' not found."
        )

    media_type = "image/png" if filename.endswith(".png") else "text/html"
    return FileResponse(
        path=str(chart_path),
        media_type=media_type,
        filename=filename,
    )
