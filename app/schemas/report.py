"""
DataInsight API — Report Generation Schemas
===========================================
Pydantic models for the PDF Report Generator.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ReportGenerationRequest(BaseModel):
    """Configuration options for the PDF report."""
    author: str = Field(
        default="DataInsight Platform",
        description="Name of the report author or organization"
    )
    title: str | None = Field(
        default=None,
        description="Custom title for the report (defaults to dataset name)"
    )
    include_visualizations: bool = Field(
        default=True,
        description="Whether to generate and embed charts in the PDF"
    )
    include_recommendations: bool = Field(
        default=True,
        description="Whether to run the rule-based recommendation engine"
    )


class ReportGenerationResponse(BaseModel):
    """Result of a PDF report generation request."""
    dataset_id: str
    report_id: str = Field(description="Unique identifier for the generated report")
    filename: str = Field(description="Name of the generated PDF file")
    download_url: str = Field(description="API URL to download the PDF")
    file_size_kb: float = Field(description="Size of the PDF in kilobytes")
    pages: int = Field(description="Number of pages in the generated PDF")
    elapsed_ms: float = Field(description="Time taken to generate the report in milliseconds")
