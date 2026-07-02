# DataForge — API Response Contracts (Final)

> **Revision note (2 July 2026):** Three corrections applied: (1) Endpoint 3 `latency_ms`/`data_loss_pct` module attribution corrected (was swapped, inconsistent with Endpoints 4/11/12/15 in this same document), (2) Endpoint 13 `latency_p95_ms` source updated to reflect the `perf_1min` CAGG's corrected `percentile_agg` implementation (extraction via `approx_percentile`, not a direct float read), (3) explicit WebSocket M1-design-rationale confirmation note added ahead of Endpoint 5, per the Week 8 locked decision.

**Cross-check rules:**
- `fused_event_id` = primary linkage key in all alerts and XAI responses (not `event_id`)
- `data_loss_pct` and `latency_ms` = pipeline-written in all payloads
- `GET /api/v1/summary` = minimum 30s polling interval
- All field names match fused_event_schema_v1 / sensor_schema_v1 / alice_event_schema_v1 exactly

---

## 1. `GET /api/v1/summary`

**Source:** `summary_5min` CAGG (`fused_events`) + `fusion_status`
**Poll:** REST — ⚠️ minimum 30s (CAGG refresh interval)
**Dashboard:** Home — summary cards

| Field | Type | Source | Notes |
|---|---|---|---|
| `active_sensors` | int | `fusion_status` count where status=online | |
| `total_events_5m` | int | `summary_5min.total_fused_events` | Last 5-min bucket |
| `anomaly_count_5m` | int | `summary_5min.anomaly_count` | anomaly_label=1 |
| `avg_risk_score` | float | `summary_5min.avg_risk_score` | Nullable |
| `max_risk_score` | float | `summary_5min.max_risk_score` | Nullable |
| `system_status` | string | Derived Module 9 | active / warning / critical |
| `last_updated_ms` | long | `summary_5min.bucket` | Last materialized bucket |
| `cagg_refresh_s` | int | Hardcoded | 30 — informs frontend |

---

## 2. `GET /api/v1/stream/info`

**Source:** Kafka consumer stats + `fusion_status`
**Poll:** On load
**Dashboard:** Live Stream — metadata

| Field | Type | Source |
|---|---|---|
| `ws_endpoint` | string | Config |
| `throughput_evt_sec` | int | Kafka — sliding 60s window |
| `active_sensors` | int | `fusion_status` |
| `stream_status` | string | Derived — live / paused / disconnected |

---

## 3. `WS /api/v1/ws/stream`

**Source:** `events` HT — Kafka consumer bridge
**Dashboard:** Live Stream — event table

| Field | Type | Source | Notes |
|---|---|---|---|
| `event_id` | string (UUID v4) | `events.event_id` | |
| `timestamp_ms` | long | `events.timestamp_ms` | |
| `source_type` | string | `events.source_type` | alice / radar / lidar / telemetry |
| `anomaly_label` | int | `events.anomaly_label` | Omitted if null (pre-M7) |
| `risk_score` | float | `events.risk_score` | Omitted if null (pre-M7) |
| `quality_flag` | string | `events.quality_flag` | Pipeline-written Module 5 |
| `latency_ms` | float | `events.latency_ms` | **Pipeline-written Module 5** |
| `data_loss_pct` | float | `events.data_loss_pct` | **Pipeline-written Module 3** |

---

## 4. `WS /api/v1/ws/fusion`

**Source:** `fusion_status` HT — Module 6 heartbeat
**Dashboard:** Fusion Monitor — live status

| Field | Type | Source | Notes |
|---|---|---|---|
| `source_type` | string | `fusion_status.source_type` | |
| `quality_score` | int | `fusion_status.quality_score` | 0–100 |
| `contribution_weight` | float | `fusion_status.contribution_weight` | 0.0–1.0 |
| `data_loss_pct` | float | `fusion_status.data_loss` | **Pipeline-written Module 5** |
| `latency_ms` | float | `fusion_status.latency` | **Pipeline-written Module 5** |
| `status` | string | `fusion_status.status` | online / degraded / offline |

---

> **WebSocket design confirmation:** `WS /api/v1/ws/stream` (Endpoint 3) and `WS /api/v1/ws/fusion` (Endpoint 4) are consistent with the original M1 design decision (`ui_api_requirements_final.docx`) — WebSocket was specifically chosen over REST polling for Live Stream and Fusion Monitor because 5-second polling would miss events at the 10K events/sec prototype throughput bar. This was a documentation gap at Week 7, not an open architecture question; no change to either endpoint's design is required.

---

## 5. `GET /api/v1/alerts/recent?limit=N`

**Source:** `anomaly_alerts` HT
**Poll:** REST 5s
**Dashboard:** Home — Recent Alerts + Critical Alert Banner

| Field | Type | Source | Notes |
|---|---|---|---|
| `alerts[].fused_event_id` | string (UUID v4) | `anomaly_alerts.fused_event_id` | **Primary linkage** |
| `alerts[].timestamp_ms` | long | `anomaly_alerts.time` | |
| `alerts[].source_type` | string | `anomaly_alerts.source_type` | |
| `alerts[].anomaly_label` | int | `anomaly_alerts.anomaly_label` | Always 1 |
| `alerts[].risk_score` | float | `anomaly_alerts.risk_score` | |
| `alerts[].confidence` | float | `anomaly_alerts.confidence` | |
| `alerts[].status` | string | `anomaly_alerts.status` | active / reviewed / closed |
| `alerts[].explanation_summary` | string | `anomaly_alerts.explanation_summary` | Nullable |
| `total_active` | int | COUNT | status=active |
| `critical_count` | int | COUNT | risk_score > 0.7 AND status=active |

---

## 6. `GET /api/v1/alerts`

**Source:** `anomaly_alerts` HT
**Poll:** REST 5s
**Dashboard:** AI Alerts — filtered table
**Query params:** `start`, `end`, `source_type`, `status`, `min_risk`, `page`, `limit=25`

| Field | Type | Source | Notes |
|---|---|---|---|
| `alerts[].fused_event_id` | string (UUID v4) | `anomaly_alerts.fused_event_id` | **Primary linkage** |
| `alerts[].timestamp_ms` | long | `anomaly_alerts.time` | Sorted DESC |
| `alerts[].source_type` | string | `anomaly_alerts.source_type` | |
| `alerts[].anomaly_label` | int | `anomaly_alerts.anomaly_label` | |
| `alerts[].risk_score` | float | `anomaly_alerts.risk_score` | |
| `alerts[].confidence` | float | `anomaly_alerts.confidence` | |
| `alerts[].model_version` | string | `anomaly_alerts.model_version` | |
| `alerts[].status` | string | `anomaly_alerts.status` | |
| `alerts[].explanation_summary` | string | `anomaly_alerts.explanation_summary` | Nullable |
| `pagination.page` | int | — | |
| `pagination.total` | int | — | |

---

## 7. `GET /api/v1/alerts/summary`

**Source:** `anomaly_alerts` HT
**Poll:** REST 5s
**Dashboard:** AI Alerts — summary cards

| Field | Type | Source |
|---|---|---|
| `active_count` | int | COUNT status=active |
| `critical_count` | int | COUNT risk_score > 0.7 AND status=active |
| `closed_today` | int | COUNT status=closed since midnight |

---

## 8. `GET /api/v1/alerts/{fused_event_id}`

**Source:** `anomaly_alerts` HT
**Poll:** On demand
**Dashboard:** AI Alerts — row accordion
**Path param:** `fused_event_id` UUID v4

| Field | Type | Source |
|---|---|---|
| `fused_event_id` | string (UUID v4) | `anomaly_alerts.fused_event_id` |
| `timestamp_ms` | long | `anomaly_alerts.time` |
| `source_type` | string | `anomaly_alerts.source_type` |
| `anomaly_label` | int | `anomaly_alerts.anomaly_label` |
| `risk_score` | float | `anomaly_alerts.risk_score` |
| `confidence` | float | `anomaly_alerts.confidence` |
| `model_version` | string | `anomaly_alerts.model_version` |
| `status` | string | `anomaly_alerts.status` |
| `status_updated_at` | long | `anomaly_alerts.status_updated_at` |
| `explanation_summary` | string | `anomaly_alerts.explanation_summary` |

---

## 9. `PATCH /api/v1/alerts/{fused_event_id}`

**Trigger:** Acknowledge / Close button
**Dashboard:** AI Alerts
**Path param:** `fused_event_id` UUID v4
**Request body:** `{ "status": "reviewed" }`

| Response Field | Type | Source |
|---|---|---|
| `fused_event_id` | string (UUID v4) | `anomaly_alerts.fused_event_id` |
| `status` | string | Updated value |
| `status_updated_at` | long | NOW() |

---

## 10. `GET /api/v1/xai/{fused_event_id}`

**Source:** `xai_explanations` + `anomaly_alerts` (joined)
**Poll:** On demand
**Dashboard:** XAI Panel
**Path param:** `fused_event_id` UUID v4

| Field | Type | Source | Notes |
|---|---|---|---|
| `fused_event_id` | string (UUID v4) | `xai_explanations.fused_event_id` | **Primary linkage** |
| `risk_score` | float | `anomaly_alerts.risk_score` | Joined |
| `anomaly_label` | int | `anomaly_alerts.anomaly_label` | Joined |
| `source_type` | string | `anomaly_alerts.source_type` | Joined |
| `timestamp_ms` | long | `anomaly_alerts.time` | Joined |
| `explanation_text` | string | `xai_explanations.explanation_text` | |
| `shap_values` | array | `xai_explanations.shap_values` | JSONB — [{feature, shap_value, direction}] |
| `top_features` | array | `xai_explanations.top_features` | Top 3 precomputed |
| `model_version` | string | `xai_explanations.model_version` | |

**Error 404:** XAI not yet available for this event.

---

## 11. `GET /api/v1/fusion/sensors`

**Source:** `fusion_status` HT — latest row per sensor
**Poll:** REST 10s
**Dashboard:** Fusion Monitor — sensor grid

| Field | Type | Source | Notes |
|---|---|---|---|
| `sensors[].source_type` | string | `fusion_status.source_type` | |
| `sensors[].quality_score` | int | `fusion_status.quality_score` | 0–100 |
| `sensors[].contribution_weight` | float | `fusion_status.contribution_weight` | 0.0–1.0 |
| `sensors[].data_loss_pct` | float | `fusion_status.data_loss` | **Pipeline-written Module 5** |
| `sensors[].latency_ms` | float | `fusion_status.latency` | **Pipeline-written Module 5** |
| `sensors[].status` | string | `fusion_status.status` | online / degraded / offline |
| `fusion_window_ms` | int | Config | Default 500 |

---

## 12. `GET /api/v1/fusion/events`

**Source:** `fused_events` HT
**Poll:** On demand (sensor card click)
**Dashboard:** Fusion Monitor — drill-down
**Query params:** `source_type`, `limit=50`

| Field | Type | Source | Notes |
|---|---|---|---|
| `events[].fused_event_id` | string (UUID v4) | `fused_events.fused_event_id` | |
| `events[].alice_event_id` | string (UUID v4) | `fused_events.alice_event_id` | FK to events (ALICE) |
| `events[].sensor_event_id` | string (UUID v4) | `fused_events.sensor_event_id` | FK to events (sensor) |
| `events[].timestamp_ms` | long | `fused_events.timestamp_ms` | |
| `events[].sensor_type` | string | `fused_events.sensor_type` | |
| `events[].fusion_window_ms` | int | `fused_events.fusion_window_ms` | |
| `events[].latency_ms` | float | `fused_events.latency_ms` | **Pipeline-written Module 5** |
| `events[].data_loss_pct` | float | `fused_events.data_loss_pct` | **Pipeline-written Module 3** |

---

## 13. `GET /api/v1/performance`

**Source:** TWO CAGGs — `perf_1min` (events) + `pipeline_health_1min` (system_performance_metrics)
**Poll:** REST 10s
**Dashboard:** Performance Metrics
**Query params:** `bucket` (1m/5m/15m), `source_type`

| Field | Type | CAGG Source | Notes |
|---|---|---|---|
| `series[].timestamp_ms` | long | `perf_1min.bucket` | |
| `series[].event_count` | int | `perf_1min.event_count` | From `events` HT |
| `series[].latency_p95_ms` | float | `approx_percentile(0.95, perf_1min.latency_p95_agg)` | From `events` HT — timescaledb-toolkit; `latency_p95_agg` is a `percentile_agg` state, not a plain float |
| `series[].avg_data_loss_pct` | float | `perf_1min.avg_data_loss` | From `events` HT — **pipeline-written** |
| `series[].avg_time_sync_ms` | float | `pipeline_health_1min.avg_time_sync` | From `system_performance_metrics` |
| `series[].avg_pipeline_latency` | float | `pipeline_health_1min.avg_pipeline_latency` | From `system_performance_metrics` — **pipeline-written** |
| `thresholds` | object | `config/prototype_bar.yaml` | Loaded on startup |

---

## 14. `GET /api/v1/performance/thresholds`

**Source:** `config/prototype_bar.yaml`
**Poll:** On load
**Dashboard:** Performance — threshold bands

| Field | Type |
|---|---|
| `latency_p95_ms` | int — 500 |
| `data_loss_pct` | float — 1.0 |
| `time_sync_ms` | float — 1.0 |
| `throughput_min` | int — 10000 |
| `model_auc_min` | float — 0.85 |
| `false_positive_max` | float — 0.05 |

---

## 15. `GET /api/v1/reports`

**Source:** `anomaly_alerts` + `fused_events` + `alerts_daily` CAGG
**Poll:** On demand
**Dashboard:** Reports
**Query params:** `start`, `end`, `source_type`, `min_risk`

| Field | Type | Source | Notes |
|---|---|---|---|
| `summary.total_events` | int | `fused_events` COUNT | |
| `summary.total_anomalies` | int | `anomaly_alerts` COUNT | |
| `summary.avg_risk_score` | float | `anomaly_alerts` AVG | |
| `summary.avg_latency_ms` | float | `fused_events.latency_ms` | **Pipeline-written Module 5** |
| `summary.avg_data_loss_pct` | float | `fused_events.data_loss_pct` | **Pipeline-written Module 3** |
| `anomaly_trend[].bucket_ms` | long | `alerts_daily.bucket` | Daily |
| `anomaly_trend[].anomaly_count` | int | `alerts_daily.anomaly_count` | |
| `sensor_performance[].source_type` | string | `anomaly_alerts.source_type` | |
| `sensor_performance[].anomaly_count` | int | COUNT | |
| `top_events[].fused_event_id` | string (UUID v4) | `anomaly_alerts.fused_event_id` | **Primary linkage** |
| `top_events[].risk_score` | float | `anomaly_alerts.risk_score` | Sorted DESC |

---

## 16. `GET /api/v1/reports/export`

**Source:** Same as `/api/v1/reports`
**Poll:** On button click
**Query params:** `format` (pdf/csv), `start`, `end`, `source_type`, `min_risk`
**Response:** File download — PDF (ReportLab server-side) or CSV

---

## 17. `GET /api/v1/health`

**Source:** Internal service checks
**Poll:** On load
**Dashboard:** StatusBand — all pages

| Field | Type | Values |
|---|---|---|
| `status` | string | healthy / degraded / down |
| `db` | string | ok / error |
| `kafka` | string | ok / error |
| `spark` | string | ok / error |
| `ai_model` | string | ok / warming / error |

---

## 18. `GET /api/v1/health/upstream`

**Source:** Module health checks + Kafka consumer lag
**Poll:** REST 60s
**Dashboard:** StatusBand — detailed view

| Field | Type | Notes |
|---|---|---|
| `timescaledb.status` | string | ok / error |
| `timescaledb.latency_ms` | float | |
| `kafka.status` | string | ok / error |
| `kafka.consumer_lag` | int | |
| `spark.status` | string | ok / error |
| `spark.throughput_evt_sec` | int | |
| `ai_model.status` | string | ok / warming / error |
| `ai_model.model_version` | string | |
| `xai_module.status` | string | ok / error |

---

## Error Format (RFC 7807)

```json
{ "type": "...", "title": "...", "status": 404, "detail": "..." }
```

---

## Endpoint Index

| # | Method | Path | Poll | Dashboard |
|---|---|---|---|---|
| 1 | GET | `/api/v1/summary` | **30s min** | Home |
| 2 | GET | `/api/v1/stream/info` | On load | Live Stream |
| 3 | WS | `/api/v1/ws/stream` | Real-time | Live Stream |
| 4 | WS | `/api/v1/ws/fusion` | Real-time | Fusion Monitor |
| 5 | GET | `/api/v1/alerts/recent` | 5s | Home |
| 6 | GET | `/api/v1/alerts` | 5s | AI Alerts |
| 7 | GET | `/api/v1/alerts/summary` | 5s | AI Alerts |
| 8 | GET | `/api/v1/alerts/{fused_event_id}` | On demand | AI Alerts |
| 9 | PATCH | `/api/v1/alerts/{fused_event_id}` | On button | AI Alerts |
| 10 | GET | `/api/v1/xai/{fused_event_id}` | On demand | XAI Panel |
| 11 | GET | `/api/v1/fusion/sensors` | 10s | Fusion Monitor |
| 12 | GET | `/api/v1/fusion/events` | On demand | Fusion Monitor |
| 13 | GET | `/api/v1/performance` | 10s | Performance |
| 14 | GET | `/api/v1/performance/thresholds` | On load | Performance |
| 15 | GET | `/api/v1/reports` | On demand | Reports |
| 16 | GET | `/api/v1/reports/export` | On button | Reports |
| 17 | GET | `/api/v1/health` | On load | All pages |
| 18 | GET | `/api/v1/health/upstream` | 60s | All pages |
