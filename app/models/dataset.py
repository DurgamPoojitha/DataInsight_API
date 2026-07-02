"""
DataInsight API — Dataset Domain Model
=========================================
Defines the internal data structure used to represent a dataset throughout
the application's service and cache layers.

This is NOT a Pydantic API schema — it is a plain Python dataclass that acts
as the domain model (the 'M' in a layered architecture).  It gets converted
to/from Pydantic schemas at the router boundary.

Using a dataclass rather than Pydantic here keeps the domain layer dependency-
free and fast (no validation overhead for internal objects).
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class DatasetMetadata:
    """
    Represents the metadata of a successfully uploaded and parsed dataset.

    Attributes:
        dataset_id (str):         Unique UUID v4 identifier assigned at upload.
        original_filename (str):  The sanitized filename as provided by the client.
        stored_path (Path):       Absolute filesystem path where the CSV is stored.
        row_count (int):          Number of data rows (excludes the header row).
        column_count (int):       Number of columns in the dataset.
        column_names (list[str]): Ordered list of column header names.
        file_size_bytes (int):    Raw size of the uploaded file in bytes.
        checksum (str):           SHA-256 hex digest of the file content.
        uploaded_at (datetime):   UTC timestamp of when the upload was processed.
    """

    dataset_id: str
    original_filename: str
    stored_path: Path
    row_count: int
    column_count: int
    column_names: list[str] = field(default_factory=list)
    file_size_bytes: int = 0
    checksum: str = ""
    uploaded_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------

    @property
    def file_size_kb(self) -> float:
        """Return file size in kilobytes, rounded to 2 decimal places."""
        return round(self.file_size_bytes / 1024, 2)

    @property
    def file_size_mb(self) -> float:
        """Return file size in megabytes, rounded to 4 decimal places."""
        return round(self.file_size_bytes / (1024 * 1024), 4)

    def to_dict(self) -> dict:
        """
        Serialize the metadata to a plain dictionary for cache storage.

        Returns:
            A JSON-serializable dict (datetime → ISO string, Path → str).
        """
        return {
            "dataset_id": self.dataset_id,
            "original_filename": self.original_filename,
            "stored_path": str(self.stored_path),
            "row_count": self.row_count,
            "column_count": self.column_count,
            "column_names": self.column_names,
            "file_size_bytes": self.file_size_bytes,
            "checksum": self.checksum,
            "uploaded_at": self.uploaded_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DatasetMetadata":
        """
        Reconstruct a DatasetMetadata instance from a serialized dictionary.
        Used when deserialising from Redis or the in-memory store.

        Args:
            data: A dict previously produced by `to_dict()`.

        Returns:
            A DatasetMetadata instance.
        """
        return cls(
            dataset_id=data["dataset_id"],
            original_filename=data["original_filename"],
            stored_path=Path(data["stored_path"]),
            row_count=data["row_count"],
            column_count=data["column_count"],
            column_names=data.get("column_names", []),
            file_size_bytes=data.get("file_size_bytes", 0),
            checksum=data.get("checksum", ""),
            uploaded_at=datetime.fromisoformat(data["uploaded_at"]),
        )
