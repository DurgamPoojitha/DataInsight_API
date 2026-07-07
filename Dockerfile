# ============================================================
# DataInsight API — Production Dockerfile
# ============================================================
# Multi-stage build:
#   Stage 1 (builder): Install Python dependencies into a venv
#   Stage 2 (runtime): Install Redis, copy the venv and source into a slim image
#
# Render deployment:
#   Render will automatically inject the $PORT environment variable.
#   The start.sh script will bind Uvicorn to this port and start Redis.

# ── Stage 1: Frontend Builder ────────────────────────────────
FROM node:20-slim AS frontend-builder

WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ .
RUN npm run build

# ── Stage 2: Backend Builder ─────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

# Install build tools (needed for some C-extension packages)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Create an isolated virtual environment for reproducibility
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install dependencies first (Docker layer cache optimization)
COPY requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# ── Stage 2: Runtime ─────────────────────────────────────────
FROM python:3.12-slim AS runtime

# Install Redis server and Chromium (required by Kaleido for PNG/PDF chart generation)
RUN apt-get update && apt-get install -y --no-install-recommends \
    redis-server \
    chromium \
    && rm -rf /var/lib/apt/lists/*

# Non-root user for security
RUN useradd --create-home --shell /bin/bash appuser

WORKDIR /app

# Copy the virtual environment from the builder stage
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application source
COPY --chown=appuser:appuser . .

# Copy compiled frontend from frontend-builder stage
COPY --from=frontend-builder --chown=appuser:appuser /app/frontend/dist /app/frontend/dist

# Create storage directories with correct ownership
RUN mkdir -p uploads plots reports && \
    chown -R appuser:appuser uploads plots reports

# Make start script executable
RUN chmod +x start.sh

# Switch to non-root user
USER appuser

# Expose the default application port (Render overrides this with $PORT at runtime)
EXPOSE 8000

# Environment variable defaults (override at runtime)
ENV HOST=0.0.0.0 \
    PORT=8000 \
    WORKERS=1 \
    LOG_LEVEL=info \
    REDIS_URL=redis://localhost:6379

# Health check for container orchestrators
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request, os; urllib.request.urlopen('http://localhost:' + os.environ.get('PORT', '8000') + '/health')" || exit 1

# Start the application (Redis + Uvicorn)
CMD ["./start.sh"]
