"""
DataInsight API — Cleaning Router
=====================================
HTTP interface for the data cleaning engine.

Endpoints:
    POST  /api/v1/cleaning/inspect/{dataset_id}
          Read-only scan — detect issues, return DatasetIssueReport.

    POST  /api/v1/cleaning/clean/{dataset_id}
          Apply cleaning operations — return CleaningReport + new dataset_id.

    GET   /api/v1/cleaning/strategies
          List all registered cleaning strategies with descriptions.

Design:
    - Zero business logic in route functions (all delegated to DataCleaningEngine).
    - DataCleaningEngine is constructed per-request using the shared DatasetService
      from app.state (injected via FastAPI Depends).
    - Each route documents its own error responses for accurate OpenAPI output.
"""

from fastapi import APIRouter, Depends, status

from app.schemas.cleaning import (
    CleaningReport,
    CleaningRequest,
    DatasetIssueReport,
)
from app.schemas.response import SuccessResponse
from app.services.cleaning_engine import DataCleaningEngine
from app.services.dataset_service import DatasetService
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(
    prefix="/cleaning",
    tags=["Data Cleaning"],
)


# ---------------------------------------------------------------------------
# Dependency: DatasetService (same shared instance as datasets router)
# ---------------------------------------------------------------------------

def get_dataset_service() -> DatasetService:
    """Inject the shared DatasetService from app.state."""
    from app.main import app
    return app.state.dataset_service


def get_cleaning_engine(
    service: DatasetService = Depends(get_dataset_service),
) -> DataCleaningEngine:
    """
    Construct a fresh DataCleaningEngine per request.

    Keeping the engine stateless (per-request) avoids any cross-request
    contamination of pipeline state.
    """
    return DataCleaningEngine(dataset_service=service)


# ---------------------------------------------------------------------------
# Endpoint 1: Inspect (read-only)
# ---------------------------------------------------------------------------

@router.post(
    "/inspect/{dataset_id}",
    response_model=SuccessResponse[DatasetIssueReport],
    status_code=status.HTTP_200_OK,
    summary="Inspect dataset for data quality issues",
    description=(
        "Performs a **read-only** scan of the dataset and returns a detailed "
        "issue report covering:\n"
        "- Missing values (count + %)\n"
        "- Duplicate rows\n"
        "- Empty columns\n"
        "- Leading/trailing whitespace\n"
        "- Inconsistent date formats\n"
        "- Likely date columns\n\n"
        "No data is modified by this endpoint."
    ),
    responses={
        200: {"description": "Issue report generated"},
        404: {"description": "Dataset not found"},
    },
)
async def inspect_dataset(
    dataset_id: str,
    engine: DataCleaningEngine = Depends(get_cleaning_engine),
) -> SuccessResponse[DatasetIssueReport]:
    """
    Scan a dataset and return a comprehensive issue report.

    Args:
        dataset_id: UUID of the dataset to inspect.
        engine:     Injected DataCleaningEngine instance.

    Returns:
        SuccessResponse wrapping a DatasetIssueReport.
    """
    logger.info("Inspect request received", dataset_id=dataset_id)
    issue_report: DatasetIssueReport = engine.inspect(dataset_id)
    return SuccessResponse(data=issue_report)


# ---------------------------------------------------------------------------
# Endpoint 2: Clean
# ---------------------------------------------------------------------------

@router.post(
    "/clean/{dataset_id}",
    response_model=SuccessResponse[CleaningReport],
    status_code=status.HTTP_200_OK,
    summary="Apply data cleaning operations to a dataset",
    description=(
        "Applies one or more cleaning operations to the dataset in the "
        "following fixed order:\n\n"
        "1. **drop_high_missing_columns** — Remove columns exceeding the "
        "   missing-value threshold\n"
        "2. **remove_duplicates** — Drop exact duplicate rows\n"
        "3. **fill_missing_values** — Impute NaN using mean/median/mode/custom\n"
        "4. **normalize_strings** — Strip whitespace, optionally lowercase\n"
        "5. **convert_dates** — Parse date strings → datetime64\n\n"
        "Returns a detailed `CleaningReport` listing every action taken, "
        "rows/columns affected, and before/after values.  If `save_cleaned=true`, "
        "the result is persisted as a new dataset and its UUID is returned."
    ),
    responses={
        200: {"description": "Cleaning completed — report returned"},
        404: {"description": "Dataset not found"},
        422: {"description": "Invalid cleaning configuration"},
    },
)
async def clean_dataset(
    dataset_id: str,
    request: CleaningRequest,
    engine: DataCleaningEngine = Depends(get_cleaning_engine),
) -> SuccessResponse[CleaningReport]:
    """
    Apply cleaning operations to a dataset and return the action report.

    Args:
        dataset_id: UUID of the source dataset.
        request:    CleaningRequest body describing which operations to run.
        engine:     Injected DataCleaningEngine instance.

    Returns:
        SuccessResponse wrapping a CleaningReport with full action log.
    """
    logger.info(
        "Clean request received",
        dataset_id=dataset_id,
        remove_duplicates=request.remove_duplicates,
        save_cleaned=request.save_cleaned,
    )
    cleaning_report: CleaningReport = engine.clean(
        dataset_id=dataset_id,
        request=request,
    )
    return SuccessResponse(data=cleaning_report)


# ---------------------------------------------------------------------------
# Endpoint 3: List available strategies (documentation / introspection)
# ---------------------------------------------------------------------------

@router.get(
    "/strategies",
    status_code=status.HTTP_200_OK,
    summary="List available cleaning strategies",
    description=(
        "Returns metadata for all built-in cleaning strategies, including "
        "their names, descriptions, and configuration parameters.  "
        "Use this to discover which operations are available."
    ),
)
async def list_strategies() -> SuccessResponse[list[dict]]:
    """
    Return a catalogue of all registered cleaning strategies.

    This endpoint is purely informational — it does not load or modify
    any data.  Useful for building UI dropdowns or API client documentation.

    Returns:
        SuccessResponse wrapping a list of strategy descriptor dicts.
    """
    strategies = [
        {
            "name": "drop_high_missing_columns",
            "description": "Drop columns where the fraction of missing values exceeds a threshold.",
            "config_field": "drop_high_missing_columns",
            "config_type": "DropColumnConfig",
            "parameters": {
                "threshold": "float (0.0–1.0) — fraction of missing values above which column is dropped",
            },
            "order": 1,
        },
        {
            "name": "remove_duplicates",
            "description": "Remove exact duplicate rows, keeping the first occurrence.",
            "config_field": "remove_duplicates",
            "config_type": "bool",
            "parameters": {},
            "order": 2,
        },
        {
            "name": "fill_missing_values",
            "description": "Impute NaN values using mean, median, mode, zero, ffill, bfill, or custom values.",
            "config_field": "fill_missing",
            "config_type": "MissingValueConfig",
            "parameters": {
                "strategy": "mean | median | mode | zero | ffill | bfill | custom",
                "custom_values": "dict[column_name, fill_value] — per-column overrides",
                "string_fill": "str — fill value for object/string columns",
                "apply_to_columns": "list[str] — restrict to specific columns (empty = all)",
            },
            "order": 3,
        },
        {
            "name": "normalize_strings",
            "description": "Strip leading/trailing whitespace and optionally convert to lowercase.",
            "config_field": "normalize_strings",
            "config_type": "StringNormConfig",
            "parameters": {
                "strip_whitespace": "bool (default: true)",
                "lowercase": "bool (default: false)",
                "apply_to_columns": "list[str] — restrict to specific columns (empty = all string cols)",
            },
            "order": 4,
        },
        {
            "name": "convert_dates",
            "description": "Parse string columns that contain dates into pandas datetime64.",
            "config_field": "convert_dates",
            "config_type": "DateConversionConfig",
            "parameters": {
                "columns": "list[str] — columns to convert (empty = auto-detect)",
                "format_hint": "%Y-%m-%d | %m/%d/%Y | %d/%m/%Y | auto | ...",
                "errors": "coerce (→ NaT) | raise",
            },
            "order": 5,
        },
    ]
    return SuccessResponse(data=strategies)
