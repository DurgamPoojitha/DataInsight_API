"""
DataInsight API — Datasets Router
====================================
Defines the HTTP interface for all dataset-related operations.

The router's ONLY job is to:
  1. Accept and parse HTTP requests
  2. Delegate work to DatasetService (dependency-injected)
  3. Map DatasetMetadata domain objects → Pydantic response schemas
  4. Return structured JSON responses

NO business logic lives inside these route functions.

Endpoints:
    POST   /api/v1/datasets/upload          Upload a CSV file
    GET    /api/v1/datasets/                List all uploaded datasets
    GET    /api/v1/datasets/{dataset_id}    Get dataset detail
    DELETE /api/v1/datasets/{dataset_id}    Delete a dataset

SOLID Principles Applied:
  - Dependency Inversion: routes depend on DatasetService via FastAPI's
    Depends() system, not on concrete I/O or storage implementations.
  - Single Responsibility: route functions handle HTTP concerns only.
"""

from fastapi import APIRouter, Depends, UploadFile, File, status
from fastapi.responses import JSONResponse

from app.schemas.dataset import (
    DatasetDetailResponse,
    DatasetSummary,
    DatasetUploadResponse,
)
from app.schemas.response import SuccessResponse
from app.services.dataset_service import DatasetService
from app.utils.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Router Configuration
# ---------------------------------------------------------------------------

router = APIRouter(
    prefix="/datasets",
    tags=["Datasets"],
)


# ---------------------------------------------------------------------------
# Dependency: DatasetService
# ---------------------------------------------------------------------------

def get_dataset_service() -> DatasetService:
    """
    FastAPI dependency that provides a shared DatasetService instance.

    In a production system this would inject a service configured from
    application state (e.g., app.state.dataset_service set during startup).
    For clarity we import the singleton from main here.

    This function is the Dependency Inversion Point — swap the returned
    object to use a different implementation (e.g., a database-backed service)
    without changing any route code.
    """
    # Import here to avoid circular imports at module load time
    from app.main import app
    return app.state.dataset_service


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/upload",
    response_model=SuccessResponse[DatasetUploadResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Upload a CSV dataset",
    description=(
        "Accepts a CSV file via multipart/form-data, validates it, parses it "
        "with Pandas, stores it on disk, and returns a dataset ID together "
        "with row/column metadata."
    ),
    responses={
        201: {"description": "Dataset uploaded successfully"},
        415: {"description": "Unsupported file type (only CSV accepted)"},
        413: {"description": "File exceeds maximum size limit"},
        422: {"description": "File is corrupted, empty, or unreadable"},
    },
)
async def upload_dataset(
    file: UploadFile = File(
        ...,
        description="CSV file to upload (max 50 MB by default)",
    ),
    service: DatasetService = Depends(get_dataset_service),
) -> SuccessResponse[DatasetUploadResponse]:
    """
    Upload a CSV file and register it as a new dataset.

    The file is read entirely into memory before processing so we can:
      a) compute the SHA-256 checksum in one pass, and
      b) pass raw bytes to DatasetService without coupling the service
         to FastAPI's UploadFile type.

    Args:
        file:    The uploaded file object provided by FastAPI.
        service: Injected DatasetService instance.

    Returns:
        SuccessResponse wrapping a DatasetUploadResponse with the assigned
        dataset_id, filename, row/column counts, and checksum.
    """
    logger.info(
        "Dataset upload request received",
        file_name=file.filename,
        content_type=file.content_type,
    )

    # Read file bytes entirely (service handles size validation)
    file_content: bytes = await file.read()

    # Delegate ALL business logic to the service layer
    metadata = service.upload_csv(
        file_content=file_content,
        original_filename=file.filename or "unnamed.csv",
    )

    # Map domain model → API response schema
    response_data = DatasetUploadResponse(
        dataset_id=metadata.dataset_id,
        filename=metadata.original_filename,
        rows=metadata.row_count,
        columns=metadata.column_count,
        column_names=metadata.column_names,
        file_size_kb=metadata.file_size_kb,
        checksum=metadata.checksum,
        uploaded_at=metadata.uploaded_at,
    )

    return SuccessResponse(data=response_data)


@router.get(
    "/",
    response_model=SuccessResponse[list[DatasetSummary]],
    status_code=status.HTTP_200_OK,
    summary="List all uploaded datasets",
    description="Returns summary metadata for all datasets sorted by upload time (newest first).",
)
async def list_datasets(
    service: DatasetService = Depends(get_dataset_service),
) -> SuccessResponse[list[DatasetSummary]]:
    """
    List all registered datasets (newest first).

    Args:
        service: Injected DatasetService instance.

    Returns:
        SuccessResponse wrapping a list of DatasetSummary objects.
    """
    datasets = service.list_datasets()

    summaries = [
        DatasetSummary(
            dataset_id=m.dataset_id,
            filename=m.original_filename,
            rows=m.row_count,
            columns=m.column_count,
            uploaded_at=m.uploaded_at,
        )
        for m in datasets
    ]

    return SuccessResponse(data=summaries)


@router.get(
    "/{dataset_id}",
    response_model=SuccessResponse[DatasetDetailResponse],
    status_code=status.HTTP_200_OK,
    summary="Get dataset details",
    description="Returns full metadata for a single dataset by its UUID.",
    responses={
        404: {"description": "Dataset not found"},
    },
)
async def get_dataset(
    dataset_id: str,
    service: DatasetService = Depends(get_dataset_service),
) -> SuccessResponse[DatasetDetailResponse]:
    """
    Retrieve detailed metadata for a specific dataset.

    Args:
        dataset_id: UUID of the dataset (from the URL path).
        service:    Injected DatasetService instance.

    Returns:
        SuccessResponse wrapping a DatasetDetailResponse.

    Raises:
        DatasetNotFoundError: Propagated from the service, caught globally.
    """
    metadata = service.get_dataset(dataset_id)

    detail = DatasetDetailResponse(
        dataset_id=metadata.dataset_id,
        filename=metadata.original_filename,
        rows=metadata.row_count,
        columns=metadata.column_count,
        column_names=metadata.column_names,
        file_size_kb=metadata.file_size_kb,
        file_size_mb=metadata.file_size_mb,
        checksum=metadata.checksum,
        uploaded_at=metadata.uploaded_at,
    )

    return SuccessResponse(data=detail)


@router.delete(
    "/{dataset_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete a dataset",
    description="Removes a dataset's metadata and deletes its raw file from disk.",
    responses={
        200: {"description": "Dataset deleted successfully"},
        404: {"description": "Dataset not found"},
    },
)
async def delete_dataset(
    dataset_id: str,
    service: DatasetService = Depends(get_dataset_service),
) -> SuccessResponse[dict]:
    """
    Delete a dataset by ID.

    Args:
        dataset_id: UUID of the dataset to delete.
        service:    Injected DatasetService instance.

    Returns:
        SuccessResponse with a confirmation message.
    """
    service.delete_dataset(dataset_id)

    return SuccessResponse(
        data={"message": f"Dataset '{dataset_id}' deleted successfully."}
    )
