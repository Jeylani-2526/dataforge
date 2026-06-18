# DataForge — API Response Contracts Draft v1

## 1. `GET /api/v1/events/live`

**Source:** `events` hypertable  
**Poll:** WebSocket (`WS /api/v1/ws/stream`) — real-time push  
**Dashboard:** Live Stream page

### Response (single WS message)
```json
{
  "event_id":       "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "timestamp_ms":   1283299200100,
  "source_type":    "RADAR",
  "anomaly_label":  1,
  "risk_score":     0.91,
  "quality_flag":   "clean",
  "latency_ms":     47.2,
  "data_loss_pct":  0.4
}
```

| Field | Type | Source | Notes |
|---|---|---|---|
| `event_id` | string (UUID v4) | `events.event_id` | |
| `timestamp_ms` | long | `events.timestamp_ms` | |
| `source_type` | string | `events.source_type` | alice / radar / lidar / telemetry |
| `anomaly_label` | int | `events.anomaly_label` | NULL until M7 — omitted from WS message if null |
| `risk_score` | float | `events.risk_score` | NULL until M7 — omitted if null |
| `quality_flag` | string | `events.quality_flag` | Pipeline-written by Module 5 |
| `latency_ms` | float | `events.latency_ms` | Pipeline-written by Module 3 |
| `data_loss_pct` | float | `events.data_loss_pct` | Pipeline-written by Module 5 |

---

## 2. `GET /api/v1/alerts/recent?limit=N`

**Source:** `anomaly_alerts` hypertable  
**Poll:** REST 5s  
**Dashboard:** Home page — Recent Alerts list + Critical Alert Banner  
**Primary linkage key:** `fused_event_id` (not `event_id`)

### Request
```
GET /api/v1/alerts/recent?limit=5
```

### Response
```json
{
  "alerts": [
    {
      "fused_event_id":     "d7e8f9a0-b1c2-3456-defa-bc0123456789",
      "timestamp_ms":       1283299200150,
      "source_type":        "RADAR",
      "anomaly_label":      1,
      "risk_score":         0.91,
      "confidence":         0.94,
      "status":             "active",
      "explanation_summary": "High radar signal loss. Primary: signal_strength_db (SHAP=0.312)."
    }
  ],
  "total_active": 7,
  "critical_count": 3
}
```

| Field | Type | Source | Notes |
|---|---|---|---|
| `fused_event_id` | string (UUID v4) | `anomaly_alerts.fused_event_id` | Primary linkage — not event_id |
| `timestamp_ms` | long | `anomaly_alerts.time` | |
| `source_type` | string | `anomaly_alerts.source_type` | Denormalized |
| `anomaly_label` | int | `anomaly_alerts.anomaly_label` | Always 1 in this table |
| `risk_score` | float | `anomaly_alerts.risk_score` | 0.0–1.0 |
| `confidence` | float | `anomaly_alerts.confidence` | 0.0–1.0 |
| `status` | string | `anomaly_alerts.status` | active / reviewed / closed |
| `explanation_summary` | string | `anomaly_alerts.explanation_summary` | Nullable |
| `total_active` | int | `anomaly_alerts` COUNT | status=active |
| `critical_count` | int | `anomaly_alerts` COUNT | risk_score > 0.7 AND status=active |

---

## 3. `GET /api/v1/xai/{fused_event_id}`

**Source:** `xai_explanations` table  
**Poll:** REST on-demand (triggered by AI Alerts row click)  
**Dashboard:** XAI Panel  
**Path param:** `fused_event_id` UUID v4

### Request
```
GET /api/v1/xai/d7e8f9a0-b1c2-3456-defa-bc0123456789
```

### Response
```json
{
  "fused_event_id":   "d7e8f9a0-b1c2-3456-defa-bc0123456789",
  "risk_score":       0.91,
  "anomaly_label":    1,
  "source_type":      "RADAR",
  "timestamp_ms":     1283299200150,
  "explanation_text": "High radar signal loss detected. Primary driver: signal_strength_db (SHAP=+0.312). Secondary: data_loss_pct (SHAP=+0.187). Fusion quality dropped below threshold.",
  "shap_values": [
    { "feature": "signal_strength_db", "shap_value": 0.312,  "direction": "positive" },
    { "feature": "data_loss_pct",      "shap_value": 0.187,  "direction": "positive" },
    { "feature": "fusion_quality",     "shap_value": 0.142,  "direction": "positive" },
    { "feature": "event_count_1m",     "shap_value": -0.078, "direction": "negative" }
  ],
  "top_features": [
    { "feature": "signal_strength_db", "shap_value": 0.312 }
  ],
  "model_version": "v0.1.0-M7"
}
```

| Field | Type | Source | Notes |
|---|---|---|---|
| `fused_event_id` | string (UUID v4) | `xai_explanations.fused_event_id` | PK lookup |
| `risk_score` | float | `anomaly_alerts.risk_score` | Joined from anomaly_alerts |
| `anomaly_label` | int | `anomaly_alerts.anomaly_label` | Joined from anomaly_alerts |
| `source_type` | string | `anomaly_alerts.source_type` | Joined from anomaly_alerts |
| `timestamp_ms` | long | `anomaly_alerts.time` | Joined from anomaly_alerts |
| `explanation_text` | string | `xai_explanations.explanation_text` | |
| `shap_values` | array | `xai_explanations.shap_values` | JSONB array |
| `top_features` | array | `xai_explanations.top_features` | JSONB — top 3 precomputed |
| `model_version` | string | `xai_explanations.model_version` | |

**Error — 404 (XAI not yet generated):**
```json
{ "status": 404, "detail": "XAI explanation not yet available for this event." }
```

---

## 4. `GET /api/v1/performance`

**Source:** TWO CAGGs — `perf_1min` (from `events`) + `pipeline_health_1min` (from `system_performance_metrics`)  
**Poll:** REST 10s  
**Dashboard:** Performance Metrics page

### Request
```
GET /api/v1/performance?bucket=1m&source_type=all
```

### Response
```json
{
  "bucket": "1m",
  "source_type": "all",
  "series": [
    {
      "timestamp_ms":          1283299200000,
      "event_count":           9842,
      "latency_p95_ms":        287.4,
      "avg_data_loss_pct":     0.4,
      "avg_time_sync_ms":      0.8,
      "avg_pipeline_latency":  312.1
    }
  ],
  "thresholds": {
    "latency_p95_ms":   500,
    "data_loss_pct":    1.0,
    "time_sync_ms":     1.0,
    "throughput_min":   10000
  }
}
```

| Field | Type | CAGG Source | Notes |
|---|---|---|---|
| `timestamp_ms` | long | `perf_1min.bucket` | Time bucket start |
| `event_count` | int | `perf_1min.event_count` | From `events` HT |
| `latency_p95_ms` | float | `perf_1min.latency_p95` | From `events` HT — requires timescaledb-toolkit |
| `avg_data_loss_pct` | float | `perf_1min.avg_data_loss` | From `events` HT |
| `avg_time_sync_ms` | float | `pipeline_health_1min.avg_time_sync` | From `system_performance_metrics` HT |
| `avg_pipeline_latency` | float | `pipeline_health_1min.avg_pipeline_latency` | From `system_performance_metrics` HT |
| `thresholds` | object | `config/prototype_bar.yaml` | Loaded on startup — not from DB |

---

## 5. `GET /api/v1/summary`

**Source:** `summary_5min` CAGG (from `fused_events`)  
**Poll:** REST 30s  
**Dashboard:** Home page — summary cards  
**⚠️ Refresh note:** `summary_5min` CAGG refreshes every 30 seconds. Frontend must poll at ≥30s intervals. Data may lag up to 30s behind real-time.

### Response
```json
{
  "active_sensors":    4,
  "total_events_5m":  49210,
  "anomaly_count_5m": 23,
  "avg_risk_score":   0.41,
  "max_risk_score":   0.91,
  "system_status":    "warning",
  "last_updated_ms":  1283299200000,
  "cagg_refresh_s":   30
}
```

| Field | Type | Source | Notes |
|---|---|---|---|
| `active_sensors` | int | `fusion_status` — count where status=online | Separate query |
| `total_events_5m` | int | `summary_5min.total_fused_events` | Last 5-min bucket |
| `anomaly_count_5m` | int | `summary_5min.anomaly_count` | anomaly_label=1 in last bucket |
| `avg_risk_score` | float | `summary_5min.avg_risk_score` | Nullable — null if no anomalies |
| `max_risk_score` | float | `summary_5min.max_risk_score` | Nullable |
| `system_status` | string | Derived by Module 9 | active / warning / critical based on thresholds |
| `last_updated_ms` | long | `summary_5min.bucket` | Timestamp of last materialized bucket |
| `cagg_refresh_s` | int | Hardcoded 30 | Informs frontend polling interval |
