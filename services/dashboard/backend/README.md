# Module 9b — FastAPI Backend

**Owner:** Beyza  
**Milestone:** M9 (implementation)  
**Status:** 🔲 Not started

## Purpose

Serves the ReactJS dashboard and external consumers with real-time data via REST and WebSocket endpoints. Connects to TimescaleDB and Kafka.

## Planned Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| GET | `/api/events/live` | Latest fused events (paginated) |
| GET | `/api/anomalies` | Anomaly detection results |
| GET | `/api/anomalies/{id}/explanation` | SHAP explanation for an anomaly |
| GET | `/api/performance` | Current pipeline performance metrics |
| GET | `/api/reports` | Summary reports |
| WS | `/ws/stream` | WebSocket — live event stream |

Full API contracts will be defined in M2 (`docs/api/`).

## Setup

```bash
pip install -r requirements.txt
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

API docs available at: http://localhost:8000/docs
