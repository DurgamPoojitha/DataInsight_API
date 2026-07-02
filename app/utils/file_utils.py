"""
DataInsight API — File Utilities
==================================
Pure utility functions for file validation, safe filename generation,
and path management.  No business logic lives here — these are stateless
helper functions reused across multiple services.

SOLID Principle Applied:
    Single Responsibility — this module only deals with file-system concerns.
    Services import these helpers rather than duplicating the logic.
"""

import os
import uuid
import hashlib
from pathlib import Path

from app.utils.exceptions import UnsupportedFileTypeError, FileTooLargeError
from app.utils.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# File types accepted by the platform for dataset uploads
ALLOWED_EXTENSIONS: frozenset[str] = frozenset({".csv"})

# Maximum upload size in megabytes (configurable via env var)
MAX_UPLOAD_SIZE_MB: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", "50"))
MAX_UPLOAD_SIZE_BYTES: int = MAX_UPLOAD_SIZE_MB * 1024 * 1024


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def validate_file_extension(filename: str) -> str:
    """
    Ensure the uploaded filename has an allowed extension.

    Args:
        filename: Original filename from the UploadFile object.

    Returns:
        The lowercase extension string (e.g., ".csv") if valid.

    Raises:
        UnsupportedFileTypeError: When the file extension is not in
            ALLOWED_EXTENSIONS.
    """
    if not filename:
        raise UnsupportedFileTypeError(
            filename="<empty>",
            allowed_types=list(ALLOWED_EXTENSIONS),
        )

    extension: str = Path(filename).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        logger.warning(
            "Rejected unsupported file type",
            file_name=filename,
            extension=extension,
        )
        raise UnsupportedFileTypeError(
            filename=filename,
            allowed_types=list(ALLOWED_EXTENSIONS),
        )

    return extension


def validate_file_size(content: bytes, filename: str) -> None:
    """
    Ensure the file content does not exceed the configured size limit.

    Args:
        content:  Raw bytes of the uploaded file.
        filename: Original filename (used in error messages).

    Raises:
        FileTooLargeError: When the content size exceeds MAX_UPLOAD_SIZE_BYTES.
    """
    size_bytes: int = len(content)

    if size_bytes > MAX_UPLOAD_SIZE_BYTES:
        logger.warning(
            "Rejected oversized file",
            file_name=filename,
            size_mb=round(size_bytes / 1024 / 1024, 2),
            max_mb=MAX_UPLOAD_SIZE_MB,
        )
        raise FileTooLargeError(filename=filename, max_mb=MAX_UPLOAD_SIZE_MB)


# ---------------------------------------------------------------------------
# Filename & path helpers
# ---------------------------------------------------------------------------

def generate_dataset_id() -> str:
    """
    Generate a UUID v4 string to be used as the unique dataset identifier.

    Returns:
        A UUID4 string (e.g., "3f2504e0-4f89-11d3-9a0c-0305e82c3301").
    """
    return str(uuid.uuid4())


def sanitize_filename(filename: str) -> str:
    """
    Strip path components and whitespace from a filename to prevent
    directory traversal attacks.

    Args:
        filename: Raw filename as provided by the client.

    Returns:
        A sanitized basename with spaces replaced by underscores.

    Example:
        sanitize_filename("../../etc/passwd.csv") → "passwd.csv"
        sanitize_filename("my data file.csv")     → "my_data_file.csv"
    """
    # os.path.basename handles path-traversal characters on all OS
    safe_name: str = os.path.basename(filename)
    # Replace whitespace with underscores
    safe_name = safe_name.replace(" ", "_")
    return safe_name


def build_upload_path(upload_dir: Path, dataset_id: str, original_filename: str) -> Path:
    """
    Construct the full filesystem path where an uploaded file should be stored.

    The file is stored as:  <upload_dir>/<dataset_id>_<sanitized_original_name>

    This naming scheme makes it easy to locate files belonging to a specific
    dataset without a database lookup.

    Args:
        upload_dir:        Path to the uploads directory (must exist).
        dataset_id:        UUID of the dataset.
        original_filename: Raw filename from the upload request.

    Returns:
        An absolute Path object for the upload destination.
    """
    safe_name: str = sanitize_filename(original_filename)
    return upload_dir / f"{dataset_id}_{safe_name}"


def compute_file_checksum(content: bytes) -> str:
    """
    Compute a SHA-256 hex digest of the file content.

    This can be used to:
    - Detect duplicate uploads (compare checksums before writing to disk).
    - Verify file integrity after storage.

    Args:
        content: Raw bytes of the file.

    Returns:
        A 64-character lowercase hex string.
    """
    return hashlib.sha256(content).hexdigest()


def ensure_directory(path: Path) -> None:
    """
    Create a directory and all its parents if they do not already exist.
    This is a no-op if the directory already exists.

    Args:
        path: Absolute or relative path to the directory.
    """
    path.mkdir(parents=True, exist_ok=True)
    logger.debug("Directory ensured", path=str(path))
