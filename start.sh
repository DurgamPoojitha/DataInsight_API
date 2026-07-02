#!/usr/bin/env bash
# ============================================================
# DataInsight API — Server Start Script
# ============================================================
# Usage:
#   chmod +x start.sh
#   ./start.sh
#
# Environment variables (all optional, have defaults):
#   HOST      - Bind host          (default: 0.0.0.0)
#   PORT      - Bind port          (default: 8000)
#   WORKERS   - Worker processes   (default: 1)
#   LOG_LEVEL - Uvicorn log level  (default: info)

set -euo pipefail

HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8000}"
WORKERS="${WORKERS:-1}"
LOG_LEVEL="${LOG_LEVEL:-info}"

echo "=============================================="
echo "  DataInsight API"
echo "  Host:    ${HOST}:${PORT}"
echo "  Workers: ${WORKERS}"
echo "  Log:     ${LOG_LEVEL}"
echo "=============================================="

exec uvicorn app.main:app \
    --host "${HOST}" \
    --port "${PORT}" \
    --workers "${WORKERS}" \
    --log-level "${LOG_LEVEL}"
