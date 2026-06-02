# DataForge — First API Endpoint List (api_endpoints_v1)

**Task:** M1W2T10 — First API Endpoint List
**Owner:** Beyza Ülkümen — Full-Stack Developer (Module 9)
**Milestone:** 1 · Week 2 · 18–24 May 2026
**Output path:** `/docs/api/api_endpoints_v1.md`
**Status:** Draft v2 — sort order fixed on /alerts/recent; critical_alerts field aligned with T9 v3
**Aligned with:** Abdullah's `data_flow_spec.md` (authoritative) + T9 dashboard field specs (`dashboard_data_fields.xlsx`)
**Brief example:** `GET /api/v1/alerts/recent?limit=50 — returns latest 50 anomaly alerts with risk score and timestamp.`

---

## 1. Purpose

This document defines the initial list of FastAPI endpoints that Module 9 (Dashboard & API) will expose to serve the 7 dashboard pages defined in T9. Each endpoint specification includes HTTP method, versioned path, description, expected query parameters, and a response payload sketch. Endpoint count: **18** (16 REST + 2 WebSocket) — within the 12–18 brief target.

This list is a draft for Abdullah's review and is not yet final. Schema details (especially response payload shapes) will be finalised in M2 alongside the OpenAPI spec.

---

## 2. Conventions

| Convention | Decision | Rationale |
|---|---|---|
| **Versioning** | All paths prefixed `/api/v1/` | Stable contract; future v2 can ship in parallel |
| **Framework** | FastAPI (Python 3.11+) | Async support, native OpenAPI `/docs`, Pydantic validation |
| **Content type** | `application/json` (responses), `application/json` (request bodies for PATCH/POST) | Standard REST |
| **Auth** | None in M1; JWT Bearer added in M9 | CORS open for `localhost:3000` during development |
| **Pagination** | OFFSET-LIMIT (`page`, `limit` query params); cursor-based pagination is a stretch goal | Simple to implement; revisited if "page drift" becomes a problem |
| **Error format** | RFC 7807 — `{ type, title, status, detail }` | Consistent across all endpoints |
| **Timestamps** | ISO 8601 UTC (`2026-05-22T14:32:05.123Z`) in responses; backend stores `timestamp_ms` int64 | Human-readable on wire, efficient in DB |
| **IDs** | UUID v4 strings (`evt_8f3a2c1d...`) | Stable across systems |
| **WebSocket** | `ws://host/api/v1/ws/...` paths; exponential backoff reconnect (1→2→4→8 s) | Per T4 decision, carried into v2 |
| **DB driver** | `asyncpg` (TimescaleDB-compatible PostgreSQL) | Async I/O matches FastAPI runtime |

---

## 3. Communication Type Decision Matrix

| Page | Communication | Polling rate | Endpoint family |
|---|---|---|---|
| Home | REST polling | 5 s | `/api/v1/summary` |
| Live Stream | WebSocket | real-time (event push) | `/api/v1/ws/stream` + `/api/v1/stream/info` |
| Fusion Monitor | REST + WebSocket | 10 s poll + live | `/api/v1/fusion/*` + `/api/v1/ws/fusion` |
| AI Alerts | REST polling | 5 s | `/api/v1/alerts/*` |
| XAI Panel | REST on-demand | user-triggered | `/api/v1/alerts/{id}/xai` |
| Performance | REST polling | 30 s | `/api/v1/performance/*` |
| Reports | REST on-demand | user-triggered | `/api/v1/reports/*` |
| (cross-cutting) | REST on-demand | — | `/api/v1/health/*` |

---

## 4. REST Endpoints

### 4.1 `GET /api/v1/summary` — Home page

**Description:** Returns the system-wide snapshot displayed on the Home page.
**Page:** Home
**Polling rate:** 5 s
**Query parameters:** none

**Response (200 OK):**
```json
{
  "system_status": "active",
  "active_sensors": 4,
  "events_today": 1247856,
  "active_alerts": 23,
  "critical_alerts": 4,
  "avg_risk_score_1h": 0.412,
  "latency_p95_ms": 287.4,
  "throughput_evt_per_sec": 9842,
  "critical_alert": {
    "event_id": "evt_8f3a2c1d",
    "risk_score": 0.91,
    "source_type": "radar",
    "timestamp": "2026-05-22T14:32:05.123Z"
  },
  "last_updated": "2026-05-22T14:32:05.123Z"
}
```

**Field clarification — `active_alerts` vs `critical_alerts`:**

| Field | Definition | T9 Home field | Widget |
|---|---|---|---|
| `active_alerts` | COUNT of all anomaly_label=1 AND status=open alerts | Field #4 | Metric card |
| `critical_alerts` | COUNT where risk_score > 0.7 AND status=open | Field #5 | Metric card |

Both fields are returned in every `/summary` poll so the frontend can populate both cards in one request. `critical_alerts` was absent from the original T9 Home table and has been added in T9 v3.

**Notes:** `critical_alert` (singular, nested object) is `null` if no event with `risk_score > 0.7 AND status = open` exists. `critical_alerts` (integer count) is `0` in the same case — it is never null. Aggregated values are computed via TimescaleDB continuous aggregates over the last 1 h window.

---

### 4.2 `GET /api/v1/stream/info` — Live Stream meta

**Description:** Returns metadata about the live event stream (used by Live Stream page on load, separate from the WS connection itself).
**Page:** Live Stream
**Polling rate:** on-demand (page load)
**Query parameters:** none

**Response (200 OK):**
```json
{
  "ws_endpoint": "ws://host/api/v1/ws/stream",
  "current_throughput_evt_per_sec": 9842,
  "supported_filters": {
    "source_type": ["alice", "radar", "lidar", "telemetry"],
    "anomaly_label": [0, 1],
    "min_risk": { "min": 0.0, "max": 1.0, "step": 0.01 }
  },
  "session_start_time": "2026-05-22T14:30:00Z"
}
```

---

### 4.3 `GET /api/v1/alerts/recent` — Recent alerts (brief example)

**Description:** Returns the latest N anomaly alerts sorted by `timestamp DESC` (most recent first), with `risk_score DESC` as a tiebreaker. Used by Home's RecentAlertsList (recency-focused) and as a starting view on AI Alerts. For severity-first ordering, pass `sort=risk_desc`.
**Page:** Home, AI Alerts
**Polling rate:** 5 s
**Query parameters:**

| Param | Type | Default | Description |
|---|---|---|---|
| `limit` | int | 50 | Max rows (1–200) |
| `sort` | enum | `time_desc` | `time_desc` — timestamp DESC, risk tiebreaker (default, used by Home); `risk_desc` — risk_score DESC, timestamp tiebreaker (used by AI Alerts severity view) |

**Response (200 OK):**
```json
{
  "alerts": [
    {
      "event_id": "evt_8f3a2c1d",
      "timestamp": "2026-05-22T14:32:05.123Z",
      "source_type": "radar",
      "anomaly_label": 1,
      "risk_score": 0.91,
      "status": "open"
    },
    {
      "event_id": "evt_7e2b1a9c",
      "timestamp": "2026-05-22T14:31:47.211Z",
      "source_type": "lidar",
      "anomaly_label": 1,
      "risk_score": 0.78,
      "status": "open"
    }
  ],
  "total": 50,
  "as_of": "2026-05-22T14:32:05.123Z"
}
```

---

### 4.4 `GET /api/v1/alerts` — Filtered alert list

**Description:** Paginated alert list with full filter support. Used by AI Alerts main table.
**Page:** AI Alerts
**Polling rate:** 5 s
**Query parameters:**

| Param | Type | Default | Description |
|---|---|---|---|
| `start` | ISO datetime | — | Date range start |
| `end` | ISO datetime | — | Date range end |
| `source_type` | enum | — | alice / radar / lidar / telemetry |
| `anomaly_label` | int (0/1) | — | Filter anomalous-only |
| `status` | enum | — | open / reviewed / closed |
| `min_risk` | float (0–1) | 0.0 | Minimum risk_score threshold |
| `page` | int | 1 | Page number (1-indexed) |
| `limit` | int | 25 | Page size (1–100) |
| `order` | enum | `risk_desc` | Sort: `risk_desc` / `time_desc` / `time_asc` |

**Response (200 OK):**
```json
{
  "alerts": [
    {
      "event_id": "evt_8f3a2c1d",
      "fused_event_id": "fus_12ab34cd",
      "timestamp": "2026-05-22T14:32:05.123Z",
      "source_type": "radar",
      "anomaly_label": 1,
      "risk_score": 0.91,
      "confidence": 0.87,
      "status": "open",
      "model_version": "1.0.0",
      "explanation_summary": "High radar latency triggered anomaly"
    }
  ],
  "pagination": {
    "page": 1,
    "limit": 25,
    "total": 1247,
    "total_pages": 50
  }
}
```

**Notes:** Server-side filtering via TimescaleDB indices. `explanation_summary` is truncated `explanation_text` (top-1 SHAP feature). Cursor-based pagination is a stretch goal.

---

### 4.5 `GET /api/v1/alerts/summary` — Alert count cards

**Description:** Returns aggregate counts for the 3 summary cards on AI Alerts page.
**Page:** AI Alerts
**Polling rate:** 5 s
**Query parameters:** none

**Response (200 OK):**
```json
{
  "active_count": 23,
  "critical_count": 4,
  "closed_today": 17,
  "as_of": "2026-05-22T14:32:05.123Z"
}
```

**Notes:** `critical_count` = alerts with `risk_score > 0.7 AND status = open`. `closed_today` resets at UTC midnight.

---

### 4.6 `GET /api/v1/alerts/{id}` — Single alert detail

**Description:** Returns full detail of one alert including explanation summary.
**Page:** AI Alerts (accordion expand), XAI Panel header
**Polling rate:** on-demand
**Path parameters:** `id` (UUID)
**Query parameters:** none

**Response (200 OK):**
```json
{
  "event_id": "evt_8f3a2c1d",
  "fused_event_id": "fus_12ab34cd",
  "timestamp": "2026-05-22T14:32:05.123Z",
  "source_type": "radar",
  "anomaly_label": 1,
  "risk_score": 0.91,
  "confidence": 0.87,
  "status": "open",
  "model_version": "1.0.0",
  "explanation_summary": "High radar latency (387 ms) triggered anomaly",
  "raw_features": {
    "energy_gev": 3.21,
    "momentum_magnitude": 4.78,
    "sensor_spread": 0.45,
    "fusion_quality_encoded": 1,
    "time_since_last_event_ms": 12.4,
    "event_rate_10s": 9842
  },
  "created_at": "2026-05-22T14:32:05.123Z",
  "updated_at": "2026-05-22T14:32:05.123Z"
}
```

**Error (404):** `{ "type": "/errors/alert-not-found", "title": "Alert not found", "status": 404, "detail": "No alert with id evt_xxx" }`

---

### 4.7 `PATCH /api/v1/alerts/{id}` — Update alert status

**Description:** Updates the lifecycle status of an alert (open → reviewed → closed).
**Page:** AI Alerts (action buttons)
**Polling rate:** on-button
**Path parameters:** `id` (UUID)
**Request body:**
```json
{ "status": "reviewed" }
```

**Allowed values:** `reviewed`, `closed`
**Response (200 OK):**
```json
{
  "event_id": "evt_8f3a2c1d",
  "status": "reviewed",
  "updated_at": "2026-05-22T14:35:18.000Z",
  "updated_by": "operator_001"
}
```

**Notes:** Frontend uses optimistic update — UI changes immediately, rolls back on error. Status changes logged to `alert_status_log` table.

---

### 4.8 `GET /api/v1/alerts/{id}/xai` — SHAP explanation

**Description:** Returns the full SHAP explanation for one alert. Core endpoint for the XAI Panel.
**Page:** XAI Panel, AI Alerts (accordion content)
**Polling rate:** on-demand
**Path parameters:** `id` (UUID)
**Query parameters:**

| Param | Type | Default | Description |
|---|---|---|---|
| `format` | enum | `summary` | `summary` (top-1 feature) or `full` (top-3 + raw shap_values) |

**Response (200 OK):**
```json
{
  "event_id": "evt_8f3a2c1d",
  "risk_score": 0.91,
  "confidence": 0.87,
  "explanation_text": "High radar latency (387 ms) combined with abnormal sensor spread (0.45) flagged this event as anomalous.",
  "top_features": ["latency_ms", "sensor_spread", "event_rate_10s"],
  "shap_values": [
    { "feature": "latency_ms", "shap_value": 0.312, "direction": "positive" },
    { "feature": "sensor_spread", "shap_value": 0.198, "direction": "positive" },
    { "feature": "event_rate_10s", "shap_value": -0.087, "direction": "negative" }
  ],
  "xai_version": "1.0.0",
  "model_version": "1.0.0"
}
```

**Notes:** Contract to be finalised with Abdullah at M2 (M1W2T6 review item Q1). For `format=summary`, only `top_features[0]` and `shap_values[0]` are returned.

---

### 4.9 `GET /api/v1/fusion/sensors` — Per-sensor status

**Description:** Returns the live status of each fusion-contributing sensor. Used by Fusion Monitor SensorStatusGrid.
**Page:** Fusion Monitor
**Polling rate:** 10 s
**Query parameters:** none

**Response (200 OK):**
```json
{
  "fusion_quality_overall": 87.3,
  "sensors": [
    {
      "sensor_type": "radar",
      "status": "nominal",
      "fusion_match_rate": 0.94,
      "contribution_weight": 0.38,
      "data_loss_pct": 0.2,
      "latency_ms": 287.4,
      "quality_score": 92.1
    },
    {
      "sensor_type": "lidar",
      "status": "noisy",
      "fusion_match_rate": 0.81,
      "contribution_weight": 0.27,
      "data_loss_pct": 1.4,
      "latency_ms": 342.7,
      "quality_score": 78.5
    },
    {
      "sensor_type": "telemetry",
      "status": "nominal",
      "fusion_match_rate": 0.97,
      "contribution_weight": 0.35,
      "data_loss_pct": 0.1,
      "latency_ms": 198.2,
      "quality_score": 95.8
    }
  ],
  "fusion_window_ms": 2000,
  "as_of": "2026-05-22T14:32:05.123Z"
}
```

---

### 4.10 `GET /api/v1/fusion/events` — Fused event drill-down

**Description:** Returns recent fused events for a chosen sensor. Triggered when the operator clicks a sensor card.
**Page:** Fusion Monitor (drill-down modal)
**Polling rate:** on-demand
**Query parameters:**

| Param | Type | Default | Description |
|---|---|---|---|
| `sensor_type` | enum | — | Filter by sensor (required) |
| `limit` | int | 50 | Max rows (1–200) |

**Response (200 OK):**
```json
{
  "events": [
    {
      "fused_event_id": "fus_12ab34cd",
      "alice_event_id": "evt_8f3a2c1d",
      "sensor_event_ids": ["snd_aa11", "snd_bb22"],
      "timestamp": "2026-05-22T14:32:05.123Z",
      "fusion_window_ms": 2000,
      "fusion_quality": "full"
    }
  ],
  "total": 50,
  "filter": { "sensor_type": "radar" }
}
```

---

### 4.11 `GET /api/v1/performance` — Performance time series

**Description:** Returns time-bucketed performance metrics for the Performance page charts.
**Page:** Performance Metrics
**Polling rate:** 30 s
**Query parameters:**

| Param | Type | Default | Description |
|---|---|---|---|
| `start` | ISO datetime | now-1h | Range start |
| `end` | ISO datetime | now | Range end |
| `bucket` | enum | `1m` | Aggregation: `30s` / `1m` / `5m` |
| `metrics` | csv | all | Subset: `latency`, `throughput`, `data_loss`, `auc`, `fpr`, `time_sync` |

**Response (200 OK):**
```json
{
  "range": { "start": "2026-05-22T13:32:00Z", "end": "2026-05-22T14:32:00Z", "bucket": "1m" },
  "series": {
    "latency_p95_ms": [
      { "bucket_ts": "2026-05-22T13:32:00Z", "value": 287.4 },
      { "bucket_ts": "2026-05-22T13:33:00Z", "value": 291.2 }
    ],
    "throughput_evt_per_sec": [
      { "bucket_ts": "2026-05-22T13:32:00Z", "value": 9842 }
    ],
    "data_loss_pct": [
      { "bucket_ts": "2026-05-22T13:32:00Z", "value": 0.4 }
    ]
  },
  "current": {
    "model_auc": 0.912,
    "model_fpr": 0.038,
    "time_sync_accuracy_ms": 0.7
  },
  "thresholds_breached": false
}
```

**Notes:** Backed by TimescaleDB continuous aggregates on `system_performance_metrics`. `thresholds_breached` is `true` if any current value crosses the prototype bar.

---

### 4.12 `GET /api/v1/performance/thresholds` — Threshold configuration

**Description:** Returns the prototype performance bar thresholds (configurable, not hardcoded). Used by Performance charts to draw threshold lines.
**Page:** Performance Metrics
**Polling rate:** on-demand (page load, cached)
**Query parameters:** none

**Response (200 OK):**
```json
{
  "latency_p95_ms_max": 500,
  "data_loss_pct_max": 1.0,
  "throughput_evt_per_sec_min": 10000,
  "model_auc_min": 0.85,
  "model_fpr_max": 0.05,
  "time_sync_accuracy_ms_max": 1.0,
  "config_source": "prototype_bar.yaml",
  "last_updated": "2026-05-18T08:00:00Z"
}
```

**Notes:** Threshold values are read from a backend config file, not hardcoded in the frontend (per design risk mitigation in T9 Section 9.2).

---

### 4.13 `GET /api/v1/reports` — Aggregated report data

**Description:** Returns aggregated report data for the Reports page based on filter criteria.
**Page:** Reports
**Polling rate:** on-demand (filter submit)
**Query parameters:**

| Param | Type | Required | Description |
|---|---|---|---|
| `start` | ISO datetime | **yes** | Range start |
| `end` | ISO datetime | **yes** | Range end |
| `source_type` | enum | no | Filter by sensor type |
| `anomaly_label` | int (0/1) | no | Anomalous-only |
| `min_risk` | float | no | Minimum risk_score |

**Response (200 OK):**
```json
{
  "range": { "start": "2026-04-22T00:00:00Z", "end": "2026-05-22T23:59:59Z" },
  "summary": {
    "total_events": 287912450,
    "total_anomalies": 4527,
    "avg_risk_score": 0.234,
    "avg_latency_ms": 312.8,
    "avg_data_loss_pct": 0.6
  },
  "anomaly_trend": [
    { "bucket": "2026-04-22", "count": 142 },
    { "bucket": "2026-04-23", "count": 158 }
  ],
  "sensor_performance": [
    {
      "sensor_type": "radar",
      "uptime_pct": 99.4,
      "avg_latency_ms": 287.4,
      "event_count": 95971150,
      "fusion_match_rate": 0.94
    }
  ],
  "top_riskiest": [
    {
      "event_id": "evt_xyz",
      "fused_event_id": "fus_abc",
      "timestamp": "2026-05-21T03:14:22Z",
      "source_type": "radar",
      "risk_score": 0.97,
      "explanation_text": "Extreme latency spike during reactor cycle"
    }
  ]
}
```

**Error (400):** `date_range required` if `start`/`end` missing.
**Notes:** Date range is required to prevent unbounded queries. Top-riskiest array capped at 10.

---

### 4.14 `GET /api/v1/reports/export` — Report file download

**Description:** Streams a generated PDF or CSV file with the same data as `/api/v1/reports`.
**Page:** Reports (Export button)
**Polling rate:** on-demand
**Query parameters:** Same as `/api/v1/reports` + `format` (enum, required: `pdf` or `csv`)

**Response (200 OK):**
- Content-Type: `application/pdf` or `text/csv`
- Content-Disposition: `attachment; filename="dataforge_report_2026-05-22.pdf"`
- Body: file stream

**Notes:** Backend uses ReportLab for PDF generation. Stretch goal: async job queue for large date ranges (>30 s), returns `202 Accepted` + email link.

---

### 4.15 `GET /api/v1/health` — Service health

**Description:** Lightweight health-check endpoint for monitoring and load balancers.
**Page:** (cross-cutting)
**Polling rate:** external (every 10 s by uptime monitor)
**Query parameters:** none

**Response (200 OK):**
```json
{
  "status": "ok",
  "uptime_seconds": 86412,
  "version": "0.1.0",
  "as_of": "2026-05-22T14:32:05.123Z"
}
```

---

### 4.16 `GET /api/v1/health/upstream` — Upstream module status

**Description:** Reports the readiness of upstream modules that M9 depends on. Used internally and for debugging dashboards.
**Page:** (cross-cutting, debug)
**Polling rate:** on-demand
**Query parameters:** none

**Response (200 OK):**
```json
{
  "kafka_broker": { "status": "up", "lag_seconds": 0.2 },
  "timescaledb": { "status": "up", "connection_pool": "8/10" },
  "ai_model_m7": { "status": "up", "version": "1.0.0", "last_inference_at": "2026-05-22T14:32:04Z" },
  "xai_module_m8": { "status": "degraded", "reason": "slow SHAP compute (>500ms)" },
  "performance_metrics_m10": { "status": "up", "last_write_at": "2026-05-22T14:31:30Z" }
}
```

**Notes:** "degraded" is informational, not failing. Used by Beyza for debugging during development.

---

## 5. WebSocket Endpoints

### 5.1 `WS /api/v1/ws/stream` — Live event stream

**Description:** Pushes every clean event (post-Module 5) to the Live Stream dashboard in real time.
**Page:** Live Stream
**Connection lifetime:** while the Live Stream page is open in the browser
**Reconnect strategy:** Exponential backoff — 1 s, 2 s, 4 s, 8 s, capped at 8 s

**Message format (per event push):**
```json
{
  "event_id": "evt_8f3a2c1d",
  "timestamp": "2026-05-22T14:32:05.123Z",
  "source_type": "radar",
  "anomaly_label": 1,
  "risk_score": 0.847,
  "quality_flag": "clean"
}
```

**Server-side throughput cap:** 5 000 messages/second per connection (backpressure beyond that).
**Notes:** Direct Kafka consumer bridge in the FastAPI app. Per T9 design, the frontend buffers up to 1 000 messages and applies pause/filter client-side.

---

### 5.2 `WS /api/v1/ws/fusion` — Live fusion status

**Description:** Pushes per-sensor fusion-engine status updates as they change (not on a fixed cadence).
**Page:** Fusion Monitor
**Connection lifetime:** while the Fusion Monitor page is open
**Reconnect strategy:** Same exponential backoff as `/ws/stream`

**Message format (per status update):**
```json
{
  "sensor_type": "lidar",
  "status": "noisy",
  "quality_score": 78.5,
  "data_loss_pct": 1.4,
  "latency_ms": 342.7,
  "fusion_window_ms": 2000,
  "as_of": "2026-05-22T14:32:05.123Z"
}
```

**Notes:** Emitted only when a sensor's status, quality_score, or data_loss_pct crosses a threshold. Supplements the 10-second REST poll of `/api/v1/fusion/sensors`.

---

## 6. Endpoint Summary Table

| # | Method | Path | Page | Refresh | Source modules |
|---|---|---|---|---|---|
| 1 | GET | `/api/v1/summary` | Home | 5 s | Module 7, 10 (aggregated) |
| 2 | GET | `/api/v1/stream/info` | Live Stream | on-load | Module 9 (own state) |
| 3 | GET | `/api/v1/alerts/recent` | Home, AI Alerts | 5 s | Module 7 |
| 4 | GET | `/api/v1/alerts` | AI Alerts | 5 s | Module 7 |
| 5 | GET | `/api/v1/alerts/summary` | AI Alerts | 5 s | Module 7 |
| 6 | GET | `/api/v1/alerts/{id}` | AI Alerts, XAI Panel | on-demand | Module 7, 8 |
| 7 | PATCH | `/api/v1/alerts/{id}` | AI Alerts | on-button | Module 9 (state) |
| 8 | GET | `/api/v1/alerts/{id}/xai` | XAI Panel | on-demand | Module 8 |
| 9 | GET | `/api/v1/fusion/sensors` | Fusion Monitor | 10 s | Module 5, 6 |
| 10 | GET | `/api/v1/fusion/events` | Fusion Monitor | on-demand | Module 6 |
| 11 | GET | `/api/v1/performance` | Performance | 30 s | Module 10 |
| 12 | GET | `/api/v1/performance/thresholds` | Performance | on-load | Module 9 (config) |
| 13 | GET | `/api/v1/reports` | Reports | on-demand | Module 5, 6, 7, 10 |
| 14 | GET | `/api/v1/reports/export` | Reports | on-demand | Module 5, 6, 7, 10 + ReportLab |
| 15 | GET | `/api/v1/health` | (cross-cutting) | external | Module 9 (own state) |
| 16 | GET | `/api/v1/health/upstream` | (cross-cutting, debug) | on-demand | All upstream modules |
| 17 | WS | `/api/v1/ws/stream` | Live Stream | real-time | Module 4 (Kafka bridge) |
| 18 | WS | `/api/v1/ws/fusion` | Fusion Monitor | live | Module 6 |

**Total: 18 endpoints (16 REST + 2 WebSocket) — within brief target of 12–18.**

---

## 7. Common Patterns

### 7.1 Error responses (RFC 7807)

All errors follow the same shape regardless of endpoint:

```json
{
  "type": "/errors/alert-not-found",
  "title": "Alert not found",
  "status": 404,
  "detail": "No alert with id evt_8f3a2c1d exists",
  "instance": "/api/v1/alerts/evt_8f3a2c1d"
}
```

Common error codes used across endpoints:

| Status | Type | When |
|---|---|---|
| 400 | `/errors/invalid-query` | Missing required query param (e.g. Reports without date_range) |
| 401 | `/errors/unauthorized` | M9+: missing/invalid JWT |
| 404 | `/errors/not-found` | Unknown ID in path |
| 422 | `/errors/validation` | Pydantic validation failure |
| 500 | `/errors/internal` | Unhandled server-side error |
| 503 | `/errors/upstream-unavailable` | Kafka or TimescaleDB unreachable |

### 7.2 Pagination

Endpoints with `page` and `limit`: response includes a `pagination` block:

```json
{
  "pagination": {
    "page": 1,
    "limit": 25,
    "total": 1247,
    "total_pages": 50
  }
}
```

### 7.3 WebSocket lifecycle

- Connection open → server pushes `{"type":"hello","session_id":"…"}` once
- Server pushes message frames until either side closes
- Heartbeat: server pings every 30 s; client must pong within 10 s
- Reconnect: client implements exponential backoff (1, 2, 4, 8 s)
- Maximum buffer on client: 1 000 messages (configurable per page)

---

## 8. Tech Stack Decisions

| Decision | Selection | Rationale |
|---|---|---|
| Framework | FastAPI (Python 3.11+) | Async, auto OpenAPI, native Pydantic |
| Auth | JWT Bearer (deferred to M9) | M1: CORS open for localhost:3000 dev |
| Pagination | OFFSET-LIMIT (M1) | Simple to ship; cursor-based stretch goal |
| Error format | RFC 7807 | Industry standard for HTTP problem details |
| PDF Export | Backend (ReportLab) | More reliable than frontend; streamed response |
| WS Reconnect | Exponential backoff 1→2→4→8 s | Carried from T4 |
| DB Layer | TimescaleDB + asyncpg | Async PostgreSQL driver; continuous aggregates support |
| Versioning | URL path `/api/v1/` | Stable contract, future v2 in parallel |

---

## 9. Open Questions for Abdullah (Wednesday review)

1. **XAI endpoint contract** — does `/api/v1/alerts/{id}/xai` return `summary` (top-1) or `full` (top-3) when `format` is omitted? T9 Q1 still open.
2. **Pagination strategy** — should cursor-based pagination be in M1, or is OFFSET-LIMIT acceptable through M3?
3. **Export async** — for date ranges > 30 days, is async-with-email-link acceptable, or must it always be synchronous download?
4. **Health-check authentication** — should `/api/v1/health` and `/health/upstream` require any auth in production (M9+), or remain public?
5. **WebSocket auth** — JWT in query string vs initial message vs cookie? Default plan: JWT in `Sec-WebSocket-Protocol` header (post-M9).
6. ~~**API versioning policy** — at what point do we cut `v2`? Major schema change (e.g., per-track records instead of per-event) would trigger it; minor additions stay in `v1`.~~ **✅ RESOLVED** — Granularity decision locked at per-event. A future shift to per-track would require `v2`; all other additions stay in `v1`.
7. **Threshold config source** — is `prototype_bar.yaml` (file-based) acceptable, or should thresholds live in TimescaleDB so they can be edited via admin UI later?

---

## 10. Aligned with T9 — Refresh Interval Reconciliation

These endpoints reflect the v2 T9 reconciliations (vs the original Task 4 poster):

| Endpoint | Task 4 poster | T9 v2 + T10 (this doc) |
|---|---|---|
| `/api/v1/summary` (Home) | 30 s | **5 s** |
| `/api/v1/performance` | 10 s | **30 s** |

These match `dashboard_data_fields.xlsx` v2 refresh column.

---

## 11. Next Steps

1. **Wednesday 22 May EOD** — Share this draft with Abdullah for M1W2T6 review.
2. **Thursday 22 May** — Incorporate Abdullah's feedback into v2.
3. **Friday 23 May** — Commit `api_endpoints_v1.md` to `/docs/api/` on GitHub (M1W2T16).
4. **Week 3** — OpenAPI/Swagger schema generation; integration into `requirements_draft_v1.docx` FR section.
5. **M2** — Final schema sign-off with Abdullah; FastAPI router scaffolding (`/api/v1/`) per project structure plan (M1W2T13).

---

## 12. References

- T9 deliverable — `dashboard_data_fields.xlsx` + `.md` (in `/dashboard/specs/`)
- T9 detailed report — `DataForge_T9_Detailed_Report_EN_v2.docx`
- Abdullah's data flow spec — `data_flow_spec.md`
- Hafta 1 Task 4 poster — `task4_api_requirements_poster.html` (superseded by this doc)
- M1W2T13 (forthcoming) — FastAPI project folder structure plan

---

*Draft v1 prepared 22 May 2026 by Beyza Ülkümen. To be reviewed by Abdullah (M1W2T6). Final committed to `/docs/api/api_endpoints_v1.md` on GitHub by Friday 23 May (M1W2T16).*
