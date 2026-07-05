"""
DataInsight API — Application Entry Point
============================================
Creates and configures the FastAPI application instance.

Responsibilities:
  ┌─────────────────────────────────────────────────────────────────────┐
  │  1. Bootstrap the FastAPI app with metadata (title, version, docs)  │
  │  2. Register CORS middleware                                         │
  │  3. Attach centralised exception handlers                            │
  │  4. Mount all routers with versioned prefixes                        │
  │  5. Manage application lifespan (startup / shutdown hooks)           │
  │     - Create required directories                                    │
  │     - Initialise DatasetService and store on app.state               │
  └─────────────────────────────────────────────────────────────────────┘

Why app.state?
    Storing shared objects (services, connections) on `app.state` allows
    FastAPI's dependency injection system to access a single, shared instance
    per worker process without relying on module-level singletons.
    This pattern avoids import-time side effects and makes testing easy:
    a test client can override `app.state` before making requests.
"""

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.routers import datasets as datasets_router
from app.routers import health as health_router
from app.routers import cleaning as cleaning_router
from app.routers import analysis as analysis_router
from app.routers import missing_values as missing_values_router
from app.routers import outliers as outliers_router
from app.routers import correlation as correlation_router
from app.routers import visualization as visualization_router
from app.routers import reports as reports_router
from app.services.dataset_service import DatasetService
from app.utils.exception_handlers import (
    datainsight_exception_handler,
    http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from app.utils.exceptions import DataInsightBaseError
from app.utils.file_utils import ensure_directory
from app.utils.logger import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Directory configuration (read from env vars with safe defaults)
# ---------------------------------------------------------------------------

BASE_DIR: Path = Path(__file__).resolve().parent.parent

UPLOAD_DIR: Path = BASE_DIR / os.getenv("UPLOAD_DIR", "uploads")
PLOTS_DIR: Path = BASE_DIR / os.getenv("PLOTS_DIR", "plots")
REPORTS_DIR: Path = BASE_DIR / os.getenv("REPORTS_DIR", "reports")


# ---------------------------------------------------------------------------
# Lifespan: startup & shutdown logic
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan context manager.

    Code BEFORE `yield` runs at startup.
    Code AFTER  `yield` runs at shutdown.

    Using the lifespan pattern (instead of deprecated @app.on_event) ensures
    clean resource management and compatibility with async test clients.
    """
    # ── Startup ───────────────────────────────────────────────────────────
    logger.info("DataInsight API starting up...")

    # Create all required directories
    for directory in (UPLOAD_DIR, PLOTS_DIR, REPORTS_DIR):
        ensure_directory(directory)

    # Initialise the DatasetService and attach it to app.state
    # so it is accessible to dependency injection functions in routers.
    app.state.dataset_service = DatasetService(upload_dir=UPLOAD_DIR)

    logger.info("DataInsight API startup complete.", upload_dir=str(UPLOAD_DIR))

    yield  # ← Application runs here

    # ── Shutdown ──────────────────────────────────────────────────────────
    logger.info("DataInsight API shutting down...")
    # Future: close Redis connections, flush caches, etc.


# ---------------------------------------------------------------------------
# FastAPI App Instance
# ---------------------------------------------------------------------------

app = FastAPI(
    title="DataInsight API",
    description=(
        "A production-quality data analytics platform built with FastAPI.\n\n"
        "Upload CSV datasets, run statistical analysis, generate visualisations, "
        "and export PDF reports — all via a clean REST API."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

# CORS — allow all origins in development; tighten in production via env var
_ALLOWED_ORIGINS: list[str] = os.getenv(
    "CORS_ORIGINS", "*"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Exception Handlers
# ---------------------------------------------------------------------------

# 1. Our custom domain exceptions (DatasetNotFoundError, etc.)
app.add_exception_handler(DataInsightBaseError, datainsight_exception_handler)  # type: ignore[arg-type]

# 2. Standard FastAPI/Starlette HTTP errors (404, 405, etc.)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)  # type: ignore[arg-type]

# 3. Pydantic request body / query parameter validation failures
app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore[arg-type]

# 4. Catch-all for any unexpected Python exceptions (500)
app.add_exception_handler(Exception, unhandled_exception_handler)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

# Health check (no versioning prefix — consumed by load balancers directly)
app.include_router(health_router.router)

# Versioned API routes
app.include_router(
    datasets_router.router,
    prefix="/api/v1",
)

app.include_router(
    cleaning_router.router,
    prefix="/api/v1",
)

app.include_router(
    analysis_router.router,
    prefix="/api/v1",
)

app.include_router(
    missing_values_router.router,
    prefix="/api/v1",
)

app.include_router(
    outliers_router.router,
    prefix="/api/v1",
)

app.include_router(
    correlation_router.router,
    prefix="/api/v1",
)

app.include_router(
    visualization_router.router,
    prefix="/api/v1",
)

app.include_router(
    reports_router.router,
    prefix="/api/v1",
)


# ---------------------------------------------------------------------------
# Root endpoint
# ---------------------------------------------------------------------------

@app.get("/", tags=["Root"], summary="API root")
async def root() -> dict:
    """
    Root endpoint — returns a welcome message and links to documentation.
    """
    return {
        "message": "Welcome to DataInsight API",
        "version": "1.0.0",
        "docs": "/docs",
        "redoc": "/redoc",
        "health": "/health",
    }
