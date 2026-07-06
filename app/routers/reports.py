"""
DataInsight API — Reports Router
================================
HTTP interface for generating professional PDF reports.
"""

from __future__ import annotations

import pathlib

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse

from app.schemas.report import ReportGenerationRequest, ReportGenerationResponse
from app.schemas.response import SuccessResponse
from app.services.stats_service import StatisticalAnalysisEngine
from app.services.correlation_service import CorrelationService
from app.services.dataset_service import DatasetService
from app.services.missing_values_service import MissingValuesService
from app.services.outlier_service import OutlierDetectionService
from app.services.correlation_service import CorrelationService
from app.services.visualization_service import VisualizationService
from app.services.report_service import ReportService
from app.routers.dependencies import get_cache
from app.utils.cache import RedisCache
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/reports",
    tags=["Reports"],
)


def _get_report_service() -> ReportService:
    from app.main import app, PLOTS_DIR, REPORTS_DIR
    
    # We construct the dependencies dynamically
    dataset_svc = app.state.dataset_service
    analysis_svc = StatisticalAnalysisEngine(dataset_service=dataset_svc)
    missing_svc = MissingValuesService(dataset_service=dataset_svc, plots_dir=PLOTS_DIR)
    outlier_svc = OutlierDetectionService(dataset_service=dataset_svc, plots_dir=PLOTS_DIR)
    corr_svc = CorrelationService(dataset_service=dataset_svc, plots_dir=PLOTS_DIR)
    viz_svc = VisualizationService(dataset_service=dataset_svc, plots_dir=PLOTS_DIR)
    
    return ReportService(
        dataset_service=dataset_svc,
        analysis_service=analysis_svc,
        missing_values_service=missing_svc,
        outlier_service=outlier_svc,
        correlation_service=corr_svc,
        visualization_service=viz_svc,
        reports_dir=REPORTS_DIR
    )


@router.post(
    "/generate/{dataset_id}",
    response_model=SuccessResponse[ReportGenerationResponse],
    status_code=status.HTTP_200_OK,
    summary="Generate a comprehensive PDF report",
    description=(
        "Orchestrates all analysis modules (Statistics, Missing Values, Outliers, "
        "Correlation, Visualization) and compiles the results into a professional, "
        "downloadable PDF document."
    ),
)
async def generate_report(
    dataset_id: str,
    request: ReportGenerationRequest,
    svc: ReportService = Depends(_get_report_service),
    cache: RedisCache | None = Depends(get_cache),
) -> SuccessResponse[ReportGenerationResponse]:
    """Trigger the PDF generation process."""
    import hashlib
    req_hash = hashlib.md5(request.model_dump_json().encode()).hexdigest()
    cache_key = f"report:{dataset_id}:{req_hash}"

    if cache:
        cached_data = cache.get(cache_key, ReportGenerationResponse)
        if cached_data:
            return SuccessResponse(data=cached_data)

    logger.info("Report generation request", dataset_id=dataset_id)
    report = svc.generate_report(
        dataset_id=dataset_id,
        request=request,
        api_base_url="/api/v1",
    )
    
    if cache:
        cache.set(cache_key, report)
        
    return SuccessResponse(data=report)


@router.get(
    "/download/{filename}",
    summary="Download a generated PDF report",
    response_class=FileResponse,
)
async def download_report(
    filename: str,
) -> FileResponse:
    """Download a pre-generated PDF report."""
    from app.main import REPORTS_DIR
    
    report_path = REPORTS_DIR / filename

    if not report_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report file '{filename}' not found."
        )

    return FileResponse(
        path=str(report_path),
        media_type="application/pdf",
        filename=filename,
    )
