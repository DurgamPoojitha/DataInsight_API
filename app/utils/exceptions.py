"""
DataInsight API — Custom Exception Classes
============================================
Defines all domain-specific exceptions used throughout the application.
Each exception carries an HTTP status code and a descriptive message,
enabling the centralized exception handler to produce consistent JSON error
responses without leaking implementation details.

SOLID Principle Applied:
    Single Responsibility — exceptions are pure error-signalling objects;
    they contain NO business logic or I/O.
"""

from http import HTTPStatus


# ---------------------------------------------------------------------------
# Base Application Exception
# ---------------------------------------------------------------------------

class DataInsightBaseError(Exception):
    """
    Base class for all DataInsight API domain exceptions.

    All custom exceptions should inherit from this class so that the global
    exception handler can catch them with a single `except` clause while
    still allowing fine-grained `except SpecificError` blocks in services.

    Attributes:
        message (str): Human-readable description of the error.
        status_code (int): HTTP status code that should be returned to the caller.
        detail (str | None): Optional additional context (e.g., problematic value).
    """

    def __init__(
        self,
        message: str,
        status_code: int = HTTPStatus.INTERNAL_SERVER_ERROR,
        detail: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message: str = message
        self.status_code: int = status_code
        self.detail: str | None = detail

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"status_code={self.status_code}, "
            f"message={self.message!r}, "
            f"detail={self.detail!r})"
        )


# ---------------------------------------------------------------------------
# Dataset Exceptions
# ---------------------------------------------------------------------------

class DatasetNotFoundError(DataInsightBaseError):
    """
    Raised when a requested dataset ID does not exist in the metadata store.

    Example:
        raise DatasetNotFoundError(dataset_id="abc-123")
    """

    def __init__(self, dataset_id: str) -> None:
        super().__init__(
            message=f"Dataset with ID '{dataset_id}' was not found.",
            status_code=HTTPStatus.NOT_FOUND,
            detail=f"dataset_id={dataset_id}",
        )


class UnsupportedFileTypeError(DataInsightBaseError):
    """
    Raised when an uploaded file has an extension or MIME type that is not
    supported by the platform (currently only CSV files are accepted).

    Example:
        raise UnsupportedFileTypeError(filename="data.xlsx")
    """

    def __init__(self, filename: str, allowed_types: list[str] | None = None) -> None:
        allowed: str = ", ".join(allowed_types) if allowed_types else "csv"
        super().__init__(
            message=(
                f"File '{filename}' has an unsupported type. "
                f"Allowed types: {allowed}."
            ),
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            detail=f"filename={filename}",
        )


class FileTooLargeError(DataInsightBaseError):
    """
    Raised when an uploaded file exceeds the configured maximum size limit.

    Example:
        raise FileTooLargeError(filename="big.csv", max_mb=50)
    """

    def __init__(self, filename: str, max_mb: int) -> None:
        super().__init__(
            message=(
                f"File '{filename}' exceeds the maximum allowed size of {max_mb} MB."
            ),
            status_code=HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
            detail=f"filename={filename}, max_mb={max_mb}",
        )


class CorruptedFileError(DataInsightBaseError):
    """
    Raised when a file cannot be parsed correctly (e.g., malformed CSV content,
    encoding errors, or an empty file with no readable rows/columns).

    Example:
        raise CorruptedFileError(filename="bad.csv", reason="Empty file")
    """

    def __init__(self, filename: str, reason: str) -> None:
        super().__init__(
            message=f"File '{filename}' could not be read: {reason}",
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            detail=f"filename={filename}, reason={reason}",
        )


class EmptyDatasetError(DataInsightBaseError):
    """
    Raised when a CSV file is valid but contains no data rows after the header.

    Example:
        raise EmptyDatasetError(filename="empty.csv")
    """

    def __init__(self, filename: str) -> None:
        super().__init__(
            message=f"File '{filename}' contains no data rows.",
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            detail=f"filename={filename}",
        )


# ---------------------------------------------------------------------------
# Analysis Exceptions
# ---------------------------------------------------------------------------

class AnalysisError(DataInsightBaseError):
    """
    Raised when a statistical analysis operation fails (e.g., non-numeric
    columns passed to a numeric-only function).

    Example:
        raise AnalysisError("Correlation requires at least two numeric columns.")
    """

    def __init__(self, message: str, detail: str | None = None) -> None:
        super().__init__(
            message=message,
            status_code=HTTPStatus.BAD_REQUEST,
            detail=detail,
        )


# ---------------------------------------------------------------------------
# Cache Exceptions
# ---------------------------------------------------------------------------

class CacheError(DataInsightBaseError):
    """
    Raised when a Redis cache operation fails (connection refused, timeout, etc.).
    The application should be able to degrade gracefully when this is raised.

    Example:
        raise CacheError("Failed to connect to Redis.")
    """

    def __init__(self, message: str, detail: str | None = None) -> None:
        super().__init__(
            message=message,
            status_code=HTTPStatus.SERVICE_UNAVAILABLE,
            detail=detail,
        )


# ---------------------------------------------------------------------------
# Report Exceptions
# ---------------------------------------------------------------------------

class ReportGenerationError(DataInsightBaseError):
    """
    Raised when PDF report generation fails (e.g., ReportLab rendering error
    or missing chart files).

    Example:
        raise ReportGenerationError("Failed to embed chart into PDF.")
    """

    def __init__(self, message: str, detail: str | None = None) -> None:
        super().__init__(
            message=message,
            status_code=HTTPStatus.INTERNAL_SERVER_ERROR,
            detail=detail,
        )
