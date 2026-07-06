## 1. ERD Design Decisions

**Hypertables:** `events`, `fused_events`, `anomaly_alerts`, `system_performance_metrics`, `fusion_status`, `xai_explanations`. All time-partitioned because every dashboard query against them is time-bounded. `xai_explanations` was converted from a plain table to a hypertable, partitioned on the same `time` as its paired `anomaly_alerts` row — an explanation has no standalone value once its alert expires.

**Composite indexes:**
```sql
CREATE INDEX idx_fused_time_label ON fused_events (timestamp_ms, anomaly_label);
CREATE INDEX idx_alerts_fused_risk ON anomaly_alerts (fused_event_id, risk_score DESC);
```
`idx_fused_time_label` serves Fusion Monitor and Reports time-window queries. `idx_alerts_fused_risk` serves the AI Alerts default sort and XAI Panel lookup.

**Retention policy:**

| Table | Retention | Rationale |
|---|---|---|
| `events` | 30 days | Covers M10 testing window; CAGGs serve queries beyond this |
| `fused_events` | 90 days | Covers full M7 ML training period |
| `anomaly_alerts` | 365 days | 12-month trend analysis; low volume |
| `xai_explanations` | 365 days | Matched to its paired anomaly_alerts row |
| `system_performance_metrics` | 30 days | Matched to events retention |
| `fusion_status` | 7 days | High-frequency heartbeat; only latest row per sensor matters operationally |

`report_snapshots` is excluded from M2 scope — no endpoint reads from it; `GET /api/v1/reports` computes live from `anomaly_alerts`, `fused_events`, and the `alerts_daily` CAGG.

---

## 2. Continuous Aggregate Strategy

Three CAGGs cover three distinct polling patterns:

- `perf_1min` (over `events`) — throughput and latency for Performance Metrics
- `pipeline_health_1min` (over `system_performance_metrics`) — time sync and data loss for the same page
- `summary_5min` (over `fused_events`) — Home page summary cards

Each source table maps to exactly one CAGG, kept independent so write cadence differences don't force a shared refresh policy. Bucket sizes follow each table's consumer: `perf_1min`/`pipeline_health_1min` use 1-minute buckets to match the Performance page's finest range selector; `summary_5min` uses 5-minute buckets since Home cards don't need minute-level granularity.

The 30-second minimum polling constraint on `GET /api/v1/summary` directly set the `summary_5min` refresh interval — both `schedule_interval` and `end_offset` are 30 seconds.

No cascading aggregates exist in the current three definitions; TimescaleDB ≥ 2.9 is listed as an infrastructure requirement as a precaution for future cascading CAGG additions.

---

## 3. API Contract Design Philosophy

Endpoint scoping traces directly to `ui_api_requirements_final.docx` — each of the 18 endpoints maps to a specific dashboard page and component from that document.

Schema alignment is enforced three ways: `fused_event_id` is the primary linkage key in every alerts and XAI response (never `event_id`); no field is silently renamed from the Avro schemas; `data_loss_pct` and `latency_ms` are explicitly labelled pipeline-written wherever they appear.

Polling cadence follows the data source: `GET /api/v1/summary` has a 30-second minimum because `summary_5min` only refreshes every 30 seconds; `GET /api/v1/alerts/recent` polls every 5 seconds because `anomaly_alerts` has no CAGG lag to account for.

WebSocket endpoints `ws/stream` and `ws/fusion` are confirmed consistent with the original M1 design rationale — WebSocket was chosen over REST polling because 5-second polling would miss events at the 10K events/sec prototype bar. This was a documentation gap from Week 7's peer review, not an architecture change.

---

## 4. Notable Technical Choices

**TimescaleDB over plain PostgreSQL** — every dashboard query is time-bounded; hypertable chunking and continuous aggregates cut response times from seconds to milliseconds.

**Per-event granularity, not per-track** — ALICE events store aggregated momentum/energy fields per event rather than per track, avoiding a write-volume multiplier of hundreds to thousands with no corresponding benefit at prototype scale.

**`fused_event_id` as the single FK linkage key** — both `anomaly_alerts` and `xai_explanations` reference `fused_events.fused_event_id`, anchoring the alert and explanation lifecycle to the fusion output the AI model actually scores, rather than to either raw source record.
