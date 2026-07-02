# ============================================================
# DataInsight API — Dockerfile
# ============================================================
# Multi-stage build:
#   Stage 1 (builder): Install Python dependencies into a venv
#   Stage 2 (runtime): Copy the venv and source into a slim image
#
# Build:  docker build -t datainsight-api .
# Run:    docker run -p 8000:8000 datainsight-api

# ── Stage 1: Builder ─────────────────────────────────────────
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

# Install dependencies first (Docker layer cache optimisation)
COPY requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# ── Stage 2: Runtime ─────────────────────────────────────────
FROM python:3.12-slim AS runtime

# Non-root user for security
RUN useradd --create-home --shell /bin/bash appuser

WORKDIR /app

# Copy the virtual environment from the builder stage
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application source
COPY --chown=appuser:appuser . .

# Create storage directories with correct ownership
RUN mkdir -p uploads plots reports && \
    chown -R appuser:appuser uploads plots reports

# Make start script executable
RUN chmod +x start.sh

# Switch to non-root user
USER appuser

# Expose the default application port
EXPOSE 8000

# Environment variable defaults (override at runtime)
ENV HOST=0.0.0.0 \
    PORT=8000 \
    WORKERS=1 \
    LOG_LEVEL=info

# Health check for container orchestrators
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Start the application
CMD ["./start.sh"]
