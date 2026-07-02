"""
DataInsight API — Centralized Exception Handlers
==================================================
Registers FastAPI exception handlers that convert all domain exceptions and
unexpected Python errors into a consistent, structured JSON response.

Response envelope for ALL errors:
    {
        "success": false,
        "error": {
            "code":    <HTTP status code as int>,
            "type":    <exception class name>,
            "message": <human-readable message>,
            "detail":  <optional additional context or null>
        }
    }

SOLID Principle Applied:
    Open/Closed — new exception types can be added to `exceptions.py`; as
    long as they inherit from DataInsightBaseError, they are handled here
    without modifying this file.
"""

import logging
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.utils.exceptions import DataInsightBaseError
from app.utils.logger import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _build_error_response(
    status_code: int,
    error_type: str,
    message: str,
    detail: str | None = None,
) -> JSONResponse:
    """
    Construct a standardised JSON error response payload.

    Args:
        status_code: HTTP status code to return.
        error_type:  Name of the exception class (used by API consumers for
                     programmatic error handling).
        message:     Human-readable error description.
        detail:      Optional extra context (e.g., invalid field name, file path).

    Returns:
        JSONResponse with the structured error payload.
    """
    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "error": {
                "code": status_code,
                "type": error_type,
                "message": message,
                "detail": detail,
            },
        },
    )


# ---------------------------------------------------------------------------
# Domain Exception Handler
# ---------------------------------------------------------------------------

async def datainsight_exception_handler(
    request: Request,
    exc: DataInsightBaseError,
) -> JSONResponse:
    """
    Handle all custom DataInsight domain exceptions.

    This single handler covers every subclass of DataInsightBaseError
    (DatasetNotFoundError, UnsupportedFileTypeError, CorruptedFileError, etc.)
    because FastAPI traverses the MRO when looking up exception handlers.

    Args:
        request: The incoming HTTP request (used for logging context).
        exc:     The caught DataInsightBaseError instance.

    Returns:
        A structured JSON error response with the exception's status code.
    """
    logger.warning(
        "Domain exception raised",
        path=request.url.path,
        method=request.method,
        exception_type=type(exc).__name__,
        message=exc.message,
        detail=exc.detail,
    )
    return _build_error_response(
        status_code=exc.status_code,
        error_type=type(exc).__name__,
        message=exc.message,
        detail=exc.detail,
    )


# ---------------------------------------------------------------------------
# FastAPI / Starlette HTTP Exception Handler
# ---------------------------------------------------------------------------

async def http_exception_handler(
    request: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    """
    Handle standard Starlette/FastAPI HTTPExceptions (e.g., 404 from routing,
    405 Method Not Allowed, 401 Unauthorized, etc.).

    Args:
        request: The incoming HTTP request.
        exc:     The Starlette HTTPException with status_code and detail.

    Returns:
        A structured JSON error response.
    """
    logger.info(
        "HTTP exception",
        path=request.url.path,
        method=request.method,
        status_code=exc.status_code,
        detail=str(exc.detail),
    )
    return _build_error_response(
        status_code=exc.status_code,
        error_type="HTTPException",
        message=str(exc.detail),
    )


# ---------------------------------------------------------------------------
# Pydantic Validation Error Handler
# ---------------------------------------------------------------------------

async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """
    Handle Pydantic v2 validation errors raised by FastAPI when request
    body, query parameters, or path parameters fail schema validation.

    Flattens the list of Pydantic error objects into a single readable
    message so API consumers get clear field-level feedback.

    Args:
        request: The incoming HTTP request.
        exc:     RequestValidationError containing a list of validation errors.

    Returns:
        422 Unprocessable Entity with field-level error detail.
    """
    # Build a concise summary of all field validation failures
    errors = exc.errors()
    field_errors: list[str] = []

    for err in errors:
        # loc is a tuple like ('body', 'filename') → join to 'body.filename'
        location = " → ".join(str(loc) for loc in err.get("loc", []))
        msg = err.get("msg", "Validation error")
        field_errors.append(f"[{location}] {msg}")

    combined_message = "; ".join(field_errors) if field_errors else "Request validation failed."

    logger.warning(
        "Request validation failed",
        path=request.url.path,
        method=request.method,
        error_count=len(errors),
    )
    return _build_error_response(
        status_code=422,
        error_type="ValidationError",
        message=combined_message,
        detail=f"{len(errors)} validation error(s) found in the request.",
    )


# ---------------------------------------------------------------------------
# Catch-All Unhandled Exception Handler
# ---------------------------------------------------------------------------

async def unhandled_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """
    Safety net handler for any exception that was not explicitly caught by
    a more specific handler. Logs the full traceback for debugging while
    returning a generic 500 response to the client (no stack traces exposed).

    Args:
        request: The incoming HTTP request.
        exc:     The unexpected exception.

    Returns:
        500 Internal Server Error with a generic message.
    """
    logger.exception(
        "Unhandled exception",
        exc_info=exc,
    )
    return _build_error_response(
        status_code=500,
        error_type="InternalServerError",
        message="An unexpected internal error occurred. Please try again later.",
    )
