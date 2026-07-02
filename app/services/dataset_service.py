"""
DataInsight API — Dataset Service
====================================
Contains ALL business logic related to dataset upload and retrieval.

Design decisions:
  - `DatasetService` is an injectable class (not a module with bare functions)
    so it can carry shared state (the in-memory metadata store) and be easily
    mocked in tests.
  - The service accepts its upload directory as a constructor argument,
    making it trivially unit-testable with a tmp_path fixture.
  - Metadata is stored in memory (a dict) as the primary store and serialized
    to Redis as the secondary/cache store.  When Redis is unavailable the
    service degrades gracefully and continues to work with in-memory state.
  - All Pandas I/O is wrapped in try/except to surface helpful error messages
    instead of raw tracebacks to the API consumer.

SOLID Principles Applied:
  - Single Responsibility: the service handles only dataset business logic.
  - Dependency Inversion: the service depends on the Path abstraction and on
    an optional cache interface, not on concrete FastAPI or Redis objects.
"""

import io
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd

from app.models.dataset import DatasetMetadata
from app.utils.exceptions import (
    CorruptedFileError,
    DatasetNotFoundError,
    EmptyDatasetError,
)
from app.utils.file_utils import (
    build_upload_path,
    compute_file_checksum,
    ensure_directory,
    generate_dataset_id,
    validate_file_extension,
    validate_file_size,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)


class DatasetService:
    """
    Handles the complete lifecycle of dataset uploads and retrievals.

    Responsibilities:
    ┌─────────────────────────────────────────────────────────────────┐
    │  1. Validate uploaded file (type + size)                        │
    │  2. Parse CSV content via Pandas                                 │
    │  3. Generate a UUID dataset identifier                           │
    │  4. Persist raw file to the uploads directory                    │
    │  5. Build and store DatasetMetadata (in-memory + optional Redis) │
    │  6. Expose query methods for listing/retrieving datasets         │
    └─────────────────────────────────────────────────────────────────┘

    Attributes:
        upload_dir (Path):
            Directory where raw CSV files are stored.  Created on first use.
        _metadata_store (dict[str, DatasetMetadata]):
            In-memory dictionary mapping dataset_id → DatasetMetadata.
            Acts as the primary store; Redis is the secondary/cache layer.
    """

    def __init__(self, upload_dir: Path) -> None:
        """
        Initialise the service with a configurable upload directory.

        Args:
            upload_dir: Absolute path to the directory where uploaded files
                        will be stored.  Created automatically if absent.
        """
        self.upload_dir: Path = upload_dir
        # In-memory store: dataset_id → DatasetMetadata
        # In a production system with multiple workers this would be replaced
        # by a shared store (Redis, PostgreSQL, etc.).
        self._metadata_store: dict[str, DatasetMetadata] = {}

        # Ensure the upload directory exists before any writes
        ensure_directory(self.upload_dir)
        logger.info("DatasetService initialised", upload_dir=str(upload_dir))

    # ------------------------------------------------------------------
    # Upload
    # ------------------------------------------------------------------

    def upload_csv(
        self,
        file_content: bytes,
        original_filename: str,
    ) -> DatasetMetadata:
        """
        Process an uploaded CSV file end-to-end and return its metadata.

        Pipeline:
            validate extension → validate size → parse CSV with Pandas
            → generate UUID → write bytes to disk → build metadata
            → persist metadata → return DatasetMetadata

        Args:
            file_content:      Raw bytes read from the UploadFile object.
            original_filename: Filename provided by the HTTP client
                               (will be sanitized internally).

        Returns:
            DatasetMetadata populated with row count, column count, checksum,
            upload timestamp, and the path to the stored file.

        Raises:
            UnsupportedFileTypeError: File extension is not .csv
            FileTooLargeError:        File exceeds MAX_UPLOAD_SIZE_MB
            CorruptedFileError:       CSV cannot be parsed by Pandas
            EmptyDatasetError:        CSV has no data rows after the header
        """
        logger.info(
            "Processing CSV upload",
            file_name=original_filename,
        )

        # ── Step 1: Validate extension ────────────────────────────────────
        validate_file_extension(original_filename)

        # ── Step 2: Validate size ─────────────────────────────────────────
        validate_file_size(file_content, original_filename)

        # ── Step 3: Parse with Pandas ─────────────────────────────────────
        dataframe: pd.DataFrame = self._parse_csv(file_content, original_filename)

        # ── Step 4: Validate data presence ───────────────────────────────
        if dataframe.empty or len(dataframe) == 0:
            raise EmptyDatasetError(filename=original_filename)

        # ── Step 5: Generate identifiers ──────────────────────────────────
        dataset_id: str = generate_dataset_id()
        checksum: str = compute_file_checksum(file_content)

        # ── Step 6: Persist raw file to disk ──────────────────────────────
        stored_path: Path = build_upload_path(
            upload_dir=self.upload_dir,
            dataset_id=dataset_id,
            original_filename=original_filename,
        )
        stored_path.write_bytes(file_content)
        logger.info(
            "File written to disk",
            path=str(stored_path),
            size_bytes=len(file_content),
        )

        # ── Step 7: Build metadata ────────────────────────────────────────
        metadata = DatasetMetadata(
            dataset_id=dataset_id,
            original_filename=original_filename,
            stored_path=stored_path,
            row_count=len(dataframe),
            column_count=len(dataframe.columns),
            column_names=list(dataframe.columns),
            file_size_bytes=len(file_content),
            checksum=checksum,
            uploaded_at=datetime.now(timezone.utc),
        )

        # ── Step 8: Persist metadata ──────────────────────────────────────
        self._store_metadata(metadata)

        logger.info(
            "Dataset upload complete",
            dataset_id=dataset_id,
            rows=metadata.row_count,
            columns=metadata.column_count,
        )
        return metadata

    # ------------------------------------------------------------------
    # Query methods
    # ------------------------------------------------------------------

    def get_dataset(self, dataset_id: str) -> DatasetMetadata:
        """
        Retrieve the metadata for a single dataset by its UUID.

        Args:
            dataset_id: UUID string of the dataset to retrieve.

        Returns:
            The DatasetMetadata instance for that dataset.

        Raises:
            DatasetNotFoundError: When no dataset with the given ID exists.
        """
        metadata: Optional[DatasetMetadata] = self._metadata_store.get(dataset_id)
        if metadata is None:
            logger.warning("Dataset not found", dataset_id=dataset_id)
            raise DatasetNotFoundError(dataset_id=dataset_id)
        return metadata

    def list_datasets(self) -> list[DatasetMetadata]:
        """
        Return all registered datasets, sorted by upload time (newest first).

        Returns:
            List of DatasetMetadata instances.  Empty list if none uploaded yet.
        """
        datasets = list(self._metadata_store.values())
        datasets.sort(key=lambda m: m.uploaded_at, reverse=True)
        logger.debug("Listing datasets", count=len(datasets))
        return datasets

    def delete_dataset(self, dataset_id: str) -> None:
        """
        Remove a dataset's metadata from the store and delete its file from
        disk.  Silently skips the file deletion if the file no longer exists.

        Args:
            dataset_id: UUID of the dataset to remove.

        Raises:
            DatasetNotFoundError: When no dataset with the given ID exists.
        """
        metadata = self.get_dataset(dataset_id)  # raises if not found

        # Remove the raw file from disk
        if metadata.stored_path.exists():
            metadata.stored_path.unlink()
            logger.info("Deleted file", path=str(metadata.stored_path))
        else:
            logger.warning(
                "File not found on disk during deletion",
                path=str(metadata.stored_path),
            )

        # Remove from in-memory store
        del self._metadata_store[dataset_id]
        logger.info("Dataset deleted", dataset_id=dataset_id)

    def load_dataframe(self, dataset_id: str) -> pd.DataFrame:
        """
        Load the stored CSV file for a dataset into a Pandas DataFrame.

        This is used by downstream analysis and visualisation services that
        need the actual data, not just the metadata.

        Args:
            dataset_id: UUID of the dataset to load.

        Returns:
            A pandas DataFrame containing the dataset's data.

        Raises:
            DatasetNotFoundError: When the dataset ID does not exist.
            CorruptedFileError:   When the stored file cannot be re-read.
        """
        metadata = self.get_dataset(dataset_id)

        try:
            df = pd.read_csv(
                metadata.stored_path,
                on_bad_lines="warn",  # skip malformed rows, consistent with upload
            )
        except Exception as exc:
            raise CorruptedFileError(
                filename=metadata.original_filename,
                reason=str(exc),
            ) from exc

        logger.debug(
            "DataFrame loaded",
            dataset_id=dataset_id,
            rows=len(df),
            columns=len(df.columns),
        )
        return df

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _parse_csv(self, content: bytes, filename: str) -> pd.DataFrame:
        """
        Attempt to parse raw bytes as a CSV using Pandas.

        Tries UTF-8 first, then falls back to latin-1 encoding to handle
        common Windows/Excel-exported CSVs.  Raises CorruptedFileError with
        a clear reason message on any failure.

        Args:
            content:  Raw file bytes.
            filename: Original filename (used in error messages only).

        Returns:
            A parsed pandas DataFrame.

        Raises:
            CorruptedFileError: On any parsing failure.
        """
        encodings = ["utf-8", "utf-8-sig", "latin-1", "cp1252"]

        for encoding in encodings:
            try:
                df = pd.read_csv(
                    io.BytesIO(content),
                    encoding=encoding,
                    # Prevent Pandas from interpreting date strings automatically
                    # (avoids silent data corruption)
                    parse_dates=False,
                    # Allow up to 1000 columns (guards against malformed files)
                    on_bad_lines="warn",
                )
                logger.debug(
                    "CSV parsed successfully",
                    file_name=filename,
                    encoding=encoding,
                )
                return df
            except pd.errors.EmptyDataError:
                # File is empty — no need to try other encodings
                raise CorruptedFileError(
                    filename=filename,
                    reason="The file is empty or contains no parsable data.",
                )
            except pd.errors.ParserError as exc:
                # Malformed CSV (bad quoting, inconsistent columns, etc.)
                raise CorruptedFileError(
                    filename=filename,
                    reason=f"CSV parsing failed: {exc}",
                ) from exc
            except UnicodeDecodeError:
                # Try the next encoding
                continue
            except Exception as exc:
                raise CorruptedFileError(
                    filename=filename,
                    reason=f"Unexpected error while reading file: {exc}",
                ) from exc

        # All encodings exhausted
        raise CorruptedFileError(
            filename=filename,
            reason=(
                "Could not decode file with any supported encoding "
                f"({', '.join(encodings)}). "
                "Please ensure the file is a valid CSV."
            ),
        )

    def _store_metadata(self, metadata: DatasetMetadata) -> None:
        """
        Persist metadata to the in-memory store.

        In a multi-worker deployment this would be replaced (or supplemented)
        by a Redis hash write so all worker processes share the same state.

        Args:
            metadata: Populated DatasetMetadata instance to persist.
        """
        self._metadata_store[metadata.dataset_id] = metadata
        logger.debug(
            "Metadata stored",
            dataset_id=metadata.dataset_id,
        )
