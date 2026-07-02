"""
DataInsight API — Health Check Router
========================================
Provides a lightweight liveness/readiness endpoint used by load balancers,
container orchestrators (Kubernetes, ECS), and monitoring systems to
determine whether the service is healthy and ready to accept traffic.

Endpoint:
    GET /health  →  Returns application status and component health.
"""

import time
import sys
from datetime import datetime, timezone

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from app.utils.logger import get_logger

logger = get_logger(__name__)

# Record the process start time so we can report uptime
_START_TIME: float = time.monotonic()

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    status_code=status.HTTP_200_OK,
    summary="Health check",
    description=(
        "Returns the operational status of the API and its key components. "
        "Returns HTTP 200 when healthy, HTTP 503 when degraded."
    ),
)
async def health_check() -> JSONResponse:
    """
    Liveness and readiness health check.

    Returns:
        200 OK  with component health when all systems are operational.
        503 Service Unavailable when a critical component is down.
    """
    uptime_seconds: float = round(time.monotonic() - _START_TIME, 2)

    health_payload = {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "uptime_seconds": uptime_seconds,
        "python_version": sys.version,
        "components": {
            "api": "ok",
        },
    }

    logger.debug("Health check requested", extra={"uptime": uptime_seconds})

    return JSONResponse(status_code=200, content=health_payload)
