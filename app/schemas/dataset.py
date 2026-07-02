"""
DataInsight API — Dataset API Schemas
=======================================
Pydantic models that define the exact JSON shape of dataset-related
request bodies and response payloads exposed at the router boundary.

These schemas are distinct from the domain models (app/models/dataset.py)
to respect the separation between API contract and internal representation.
This makes it safe to evolve the internal model without breaking the API, or
version the API without changing internal business logic.
"""

from datetime import datetime
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Upload Response
# ---------------------------------------------------------------------------

class DatasetUploadResponse(BaseModel):
    """
    Response payload returned after a successful CSV upload.

    Returned by:  POST /api/v1/datasets/upload

    Attributes:
        dataset_id (str):         UUID that uniquely identifies this dataset.
        filename (str):           Sanitized original filename.
        rows (int):               Number of data rows (header excluded).
        columns (int):            Number of columns.
        column_names (list[str]): Ordered list of column header names.
        file_size_kb (float):     File size in kilobytes.
        checksum (str):           SHA-256 hex digest of the raw file bytes.
        uploaded_at (datetime):   UTC timestamp of the upload event.
    """

    dataset_id: str = Field(
        ...,
        description="UUID v4 identifier for this dataset",
        examples=["3f2504e0-4f89-11d3-9a0c-0305e82c3301"],
    )
    filename: str = Field(
        ...,
        description="Sanitized original filename",
        examples=["sales_data_2024.csv"],
    )
    rows: int = Field(
        ...,
        ge=0,
        description="Number of data rows (header row excluded)",
        examples=[1024],
    )
    columns: int = Field(
        ...,
        ge=1,
        description="Number of columns",
        examples=[12],
    )
    column_names: list[str] = Field(
        default_factory=list,
        description="Ordered list of column header names",
        examples=[["date", "revenue", "region"]],
    )
    file_size_kb: float = Field(
        ...,
        ge=0,
        description="File size in kilobytes",
        examples=[45.23],
    )
    checksum: str = Field(
        ...,
        description="SHA-256 hex digest of the uploaded file",
        examples=["e3b0c44298fc1c149afb..."],
    )
    uploaded_at: datetime = Field(
        ...,
        description="UTC timestamp when the file was processed",
    )

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Dataset List / Summary
# ---------------------------------------------------------------------------

class DatasetSummary(BaseModel):
    """
    Lightweight summary of a dataset used in list responses.

    Returned by:  GET /api/v1/datasets/

    Attributes:
        dataset_id (str):   UUID identifier.
        filename (str):     Sanitized original filename.
        rows (int):         Number of data rows.
        columns (int):      Number of columns.
        uploaded_at (datetime): UTC upload timestamp.
    """

    dataset_id: str = Field(..., description="UUID v4 identifier for this dataset")
    filename: str = Field(..., description="Sanitized original filename")
    rows: int = Field(..., ge=0, description="Number of data rows")
    columns: int = Field(..., ge=1, description="Number of columns")
    uploaded_at: datetime = Field(..., description="UTC upload timestamp")

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Dataset Detail
# ---------------------------------------------------------------------------

class DatasetDetailResponse(BaseModel):
    """
    Full metadata detail of a single dataset.

    Returned by:  GET /api/v1/datasets/{dataset_id}

    Attributes:
        dataset_id (str):         UUID identifier.
        filename (str):           Sanitized original filename.
        rows (int):               Number of data rows.
        columns (int):            Number of columns.
        column_names (list[str]): All column header names.
        file_size_kb (float):     File size in kilobytes.
        file_size_mb (float):     File size in megabytes.
        checksum (str):           SHA-256 hex digest.
        uploaded_at (datetime):   UTC upload timestamp.
    """

    dataset_id: str = Field(..., description="UUID v4 identifier for this dataset")
    filename: str = Field(..., description="Sanitized original filename")
    rows: int = Field(..., ge=0, description="Number of data rows")
    columns: int = Field(..., ge=1, description="Number of columns")
    column_names: list[str] = Field(default_factory=list, description="Column header names")
    file_size_kb: float = Field(..., ge=0, description="File size in kilobytes")
    file_size_mb: float = Field(..., ge=0, description="File size in megabytes")
    checksum: str = Field(..., description="SHA-256 hex digest of the file")
    uploaded_at: datetime = Field(..., description="UTC upload timestamp")

    model_config = {"from_attributes": True}
