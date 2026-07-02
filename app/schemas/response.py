"""
DataInsight API — Generic API Response Schemas
================================================
Provides reusable Pydantic models for wrapping all API responses in a
consistent envelope.  Every endpoint returns one of these two shapes:

    Success:
    {
        "success": true,
        "data": { ... }
    }

    Error (produced by exception handlers):
    {
        "success": false,
        "error": {
            "code":    <int>,
            "type":    <str>,
            "message": <str>,
            "detail":  <str | null>
        }
    }

Using a consistent envelope makes it trivial for API consumers (frontend,
mobile, other services) to parse responses without inspecting HTTP status
codes first.
"""

from typing import Any, Generic, TypeVar
from pydantic import BaseModel, Field

# TypeVar allows SuccessResponse to be generic over the data payload type.
DataT = TypeVar("DataT")


class ErrorDetail(BaseModel):
    """
    Structured error detail block embedded inside error responses.

    Attributes:
        code (int):         HTTP status code for programmatic handling.
        type (str):         Exception class name (e.g., "DatasetNotFoundError").
        message (str):      Human-readable error description.
        detail (str | None):Optional extra context (field name, file path, etc.).
    """

    code: int = Field(..., description="HTTP status code", examples=[404])
    type: str = Field(..., description="Exception class name", examples=["DatasetNotFoundError"])
    message: str = Field(..., description="Human-readable error description")
    detail: str | None = Field(
        default=None,
        description="Optional additional context about the error",
    )


class ErrorResponse(BaseModel):
    """
    Top-level error response envelope returned by all exception handlers.

    Attributes:
        success (bool):       Always False for error responses.
        error (ErrorDetail):  Structured error information.
    """

    success: bool = Field(default=False, description="Always False for errors")
    error: ErrorDetail = Field(..., description="Error detail block")


class SuccessResponse(BaseModel, Generic[DataT]):
    """
    Generic top-level success response envelope.

    Type parameter DataT allows callers to annotate the exact shape of the
    'data' payload, enabling IDE auto-completion and OpenAPI schema generation.

    Usage:
        class MyData(BaseModel):
            name: str

        @router.get("/example", response_model=SuccessResponse[MyData])
        def example() -> SuccessResponse[MyData]:
            return SuccessResponse(data=MyData(name="hello"))

    Attributes:
        success (bool): Always True for successful responses.
        data (DataT):   The actual response payload.
    """

    success: bool = Field(default=True, description="Always True for successful responses")
    data: DataT = Field(..., description="Response payload")
