# DataInsight API

A production-quality **data analytics platform** built with **FastAPI** and Python 3.12.

Upload CSV datasets, inspect metadata, and lay the foundation for statistical analysis, Plotly visualisations, and ReportLab PDF reports — all via a clean, versioned REST API.

---

## Tech Stack

| Concern | Library |
|---|---|
| Web Framework | FastAPI 0.111 + Uvicorn |
| Data Processing | Pandas 2.2 + NumPy 1.26 + SciPy 1.13 |
| Visualisation | Plotly 5.22 + Kaleido |
| PDF Reports | ReportLab 4.2 |
| Caching | Redis 5 (async) |
| Validation | Pydantic v2 + pydantic-settings |
| File I/O | aiofiles |

---

## Project Structure

```
DataInsight_API/
├── app/
│   ├── main.py                  # FastAPI app, middleware, exception handlers, routers
│   ├── config.py                # Pydantic Settings (env vars)
│   ├── models/
│   │   └── dataset.py           # DatasetMetadata domain dataclass
│   ├── schemas/
│   │   ├── response.py          # Generic SuccessResponse / ErrorResponse envelopes
│   │   └── dataset.py           # Upload / list / detail response schemas
│   ├── routers/
│   │   ├── health.py            # GET /health
│   │   └── datasets.py          # POST /upload, GET /, GET /{id}, DELETE /{id}
│   ├── services/
│   │   └── dataset_service.py   # All dataset business logic (upload, parse, store)
│   └── utils/
│       ├── exceptions.py        # Custom exception hierarchy
│       ├── exception_handlers.py# Centralised FastAPI exception handlers
│       ├── file_utils.py        # Validation, sanitization, path helpers
│       └── logger.py            # Structured logging setup
├── uploads/                     # Stored CSV files (auto-created)
├── plots/                       # Generated chart files (auto-created)
├── reports/                     # Generated PDF reports (auto-created)
├── requirements.txt
├── Dockerfile
├── start.sh
└── .env.example
```

---

## Quick Start

### 1. Clone & set up environment

```bash
cd DataInsight_API
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env as needed (defaults work for local development)
```

### 3. Run the server

```bash
uvicorn app.main:app --reload
# or
./start.sh
```

Visit **http://localhost:8000/docs** for the interactive Swagger UI.

---

## API Endpoints

### Health

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Liveness check — returns status, uptime |

### Datasets

| Method | Path | Description |
|---|---|---|
| POST | `/api/v1/datasets/upload` | Upload a CSV file |
| GET | `/api/v1/datasets/` | List all uploaded datasets |
| GET | `/api/v1/datasets/{dataset_id}` | Get full dataset metadata |
| DELETE | `/api/v1/datasets/{dataset_id}` | Delete a dataset |

---

## Example: Upload a CSV

```bash
curl -X POST http://localhost:8000/api/v1/datasets/upload \
     -F "file=@sales_data.csv"
```

**Response (201 Created):**
```json
{
  "success": true,
  "data": {
    "dataset_id": "3f2504e0-4f89-11d3-9a0c-0305e82c3301",
    "filename": "sales_data.csv",
    "rows": 1024,
    "columns": 8,
    "column_names": ["date", "revenue", "region", "product", "quantity", "cost", "profit", "category"],
    "file_size_kb": 45.23,
    "checksum": "e3b0c44298fc1c149afb4c8996fb92427ae41e4649b934ca495991b7852b855",
    "uploaded_at": "2024-01-15T10:23:45.123456+00:00"
  }
}
```

---

## Error Handling

All errors follow a consistent JSON envelope:

```json
{
  "success": false,
  "error": {
    "code": 415,
    "type": "UnsupportedFileTypeError",
    "message": "File 'report.pdf' has an unsupported type. Allowed types: csv.",
    "detail": "filename=report.pdf"
  }
}
```

| Error Type | HTTP Code | Trigger |
|---|---|---|
| `UnsupportedFileTypeError` | 415 | Non-CSV file uploaded |
| `FileTooLargeError` | 413 | File exceeds MAX_UPLOAD_SIZE_MB |
| `CorruptedFileError` | 422 | Malformed or unreadable CSV |
| `EmptyDatasetError` | 422 | CSV has no data rows |
| `DatasetNotFoundError` | 404 | Dataset ID doesn't exist |
| `ValidationError` | 422 | Invalid request schema |

---

## Docker

```bash
# Build
docker build -t datainsight-api .

# Run
docker run -p 8000:8000 \
  -e LOG_LEVEL=info \
  -v $(pwd)/uploads:/app/uploads \
  datainsight-api
```

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `HOST` | `0.0.0.0` | Uvicorn bind host |
| `PORT` | `8000` | Uvicorn bind port |
| `WORKERS` | `1` | Worker process count |
| `LOG_LEVEL` | `INFO` | Log verbosity |
| `UPLOAD_DIR` | `uploads` | Upload storage directory |
| `MAX_UPLOAD_SIZE_MB` | `50` | Maximum file size |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection |
| `CORS_ORIGINS` | `*` | Allowed CORS origins |

---

## SOLID Principles

| Principle | How It's Applied |
|---|---|
| **S** — Single Responsibility | Routers handle HTTP only; services handle business logic; utils handle infrastructure concerns |
| **O** — Open/Closed | New exception types extend `DataInsightBaseError` without modifying exception handlers |
| **L** — Liskov Substitution | Service dependencies are type-hinted to interfaces, not concrete classes |
| **I** — Interface Segregation | Schemas are split by concern (upload response ≠ list summary ≠ full detail) |
| **D** — Dependency Inversion | Routes depend on `DatasetService` injected via `Depends()`, not instantiated inline |
