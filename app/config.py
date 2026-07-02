"""
DataInsight API — Application Configuration
=============================================
Reads all configuration from environment variables using Pydantic Settings.
Provides typed, validated config values throughout the application.

Usage:
    from app.config import settings
    print(settings.upload_dir)
"""

import os
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    All values have sensible defaults for local development.
    Override them by setting environment variables or creating a .env file.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Application ---
    app_name: str = Field(default="DataInsight API", description="Application name")
    app_version: str = Field(default="1.0.0", description="Application version")
    debug: bool = Field(default=False, description="Enable debug mode")
    log_level: str = Field(default="INFO", description="Logging level")

    # --- Server ---
    host: str = Field(default="0.0.0.0", description="Uvicorn host")
    port: int = Field(default=8000, description="Uvicorn port")
    workers: int = Field(default=1, description="Number of Uvicorn worker processes")

    # --- CORS ---
    cors_origins: str = Field(default="*", description="Comma-separated allowed origins")

    # --- File Storage ---
    upload_dir: str = Field(default="uploads", description="Upload directory path")
    plots_dir: str = Field(default="plots", description="Plots output directory")
    reports_dir: str = Field(default="reports", description="Reports output directory")
    max_upload_size_mb: int = Field(default=50, description="Max upload size in MB")

    # --- Redis ---
    redis_url: str = Field(default="redis://localhost:6379/0", description="Redis connection URL")
    cache_ttl_seconds: int = Field(default=3600, description="Default cache TTL in seconds")


# Module-level singleton — import this throughout the app
settings = Settings()
