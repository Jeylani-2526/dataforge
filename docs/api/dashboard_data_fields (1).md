# DataForge — Dashboard Data Field Specifications (T9)

**Milestone 1 · Week 2 · Task M1W2T9**  
**Owner:** Beyza Ülkümen  
**Brief:** For each dashboard page, list every displayed data field with: field name, data type, source module number, refresh interval, and display widget type (chart / table / badge / gauge).  
**Brief example:** `'event_timestamp' | datetime | Module 4 (Kafka) | real-time | table column`  
**Format note:** Source Module uses `Module N - Name` full format (aligned with brief example). Widget Type uses brief categories `chart / table / badge / gauge` with parenthetical refinements.  
**Aligned with:** Abdullah's `data_flow_spec.md` (authoritative module mapping)  
**Status:** v3 — critical_alerts field added to Home; sort order clarified; reconciliation notes updated  
**Output paths:** `/dashboard/specs/dashboard_data_fields.{xlsx,md}`

---

## Module Legend

| # | Module | Owner | Type | Implementation |
|---|---|---|---|---|
| Module 1 | ALICE Data Source | Beyza | Source | M3 |
| Module 2 | Sensor Data Source (synthetic) | Omer | Source | M3 |
| Module 3 | Data Adaptation Layer | Abdullah + Omer | Pipeline | M4 |
| Module 4 | Streaming Layer (Kafka) | Omer | Pipeline | M5 |
| Module 5 | Cleaning & Synchronization | Beyza + Omer | Pipeline | M5 |
| Module 6 | Data Fusion Layer | Abdullah + Omer | Pipeline | M6 |
| Module 7 | AI/ML Anomaly Detection | Abdullah | Intelligence | M7 |
| Module 8 | Explainable AI (XAI) | Abdullah | Intelligence | M8 |
| Module 9 | Dashboard & API | Beyza | Delivery | M9 |
| Module 10 | Testing & Validation | Beyza + Abdullah | Validation | M10 |

## Widget Type Vocabulary

Brief categories: `chart`, `table`, `badge`, `gauge`. Refinements appear in parentheses.

| Category | Refinements used in this spec |
|---|---|
| `badge` | metric card, status band, alert banner, counter, in-row badge, chip list, header text, sub-text, footer text, timestamp, paragraph box, alert band |
| `table` | table column, table column (icon), table (dropdown filter), table (search filter), table (slider filter), table (date filter), table (toggle button), table (selector), table (button), table (accordion content) |
| `chart` | chart (sparkline), chart (counter), chart (bar), chart (line X-axis), chart (line Y-axis), chart (bar X-axis), chart (bar Y-axis), chart (area X-axis), chart (area Y-axis), chart (horizontal bar label), chart (horizontal bar value), chart (bar colour) |
| `gauge` | gauge (circular), gauge (overall fusion quality) |

---

## Reconciliation Notes (T2 poster ↔ M3 data_flow_spec)

- **Home refresh:** T2 poster used 30s; M3 spec mandates 5s. T9 follows M3 (5s).
- **Performance refresh:** T2 poster used 10s; M3 spec mandates 30s. T9 follows M3 (30s).
- **Module ordering:** T2 used inferred M1=Sensor / M2=ALICE; M3 spec is M1=ALICE, M2=Sensor (synthetic). T9 follows M3.
- **Source field naming:** Field 'sensor_type' from T2 poster -> unified as 'source_type' (enum: alice/radar/lidar/telemetry) in M3 spec. T9 follows M3.
- **anomaly_label type:** M3 spec: int8 (0/1) — not VARCHAR as assumed in T2. T9 follows M3.
- **API endpoint refresh intervals (T10):** Task 4 API poster will need same refresh-interval reconciliation (Home 30s->5s, Performance 10s->30s). ✅ Applied in T10 v2.
- **critical_alerts field added (v3):** `critical_alerts` (COUNT where risk_score>0.7 AND status=open) was present in T10 `/api/v1/summary` response but missing from this T9 Home page table. Added as field #5. `active_alerts` (field #4) remains the total open alert count; `critical_alerts` is the high-severity subset. Both are returned in a single `/summary` poll.
- **recent_alerts sort order clarified (v3):** Home page "Recent Alerts" table is sorted `timestamp DESC` (newest first) — consistent with the widget name "Recent". Severity sort (`risk_desc`) is available via query parameter on T10's `/api/v1/alerts/recent` endpoint for AI Alerts use.

---

## 01 Home — Home

**Default refresh:** REST 5s (poll)   |   **Total fields:** 17

| # | Field Name | Data Type | Source Module | Refresh | Widget | Notes |
|---|---|---|---|---|---|---|
| 1 | `system_status` | enum (active/warning/critical) | Module 9 - Dashboard (derived from M7) | 5s | badge (status band) | Driven by avg risk_score threshold |
| 2 | `active_sensors` | int | Module 2 - Sensor Source | 5s | badge (metric card) | Sensor count with status != dropout |
| 3 | `events_today` | int | Module 6 - Data Fusion | 5s | badge (metric card) | Total fused events since midnight |
| 4 | `active_alerts` | int | Module 7 - AI/ML | 5s | badge (metric card) | COUNT of anomaly_label=1 AND status=open alerts |
| 5 | `critical_alerts` | int | Module 7 - AI/ML | 5s | badge (metric card) | COUNT where risk_score > 0.7 AND status=open; 0 when none (never null) |
| 6 | `avg_risk_score_1h` | float (0-1) | Module 7 - AI/ML (aggregated) | 5s | badge (metric card) | Continuous aggregate from anomaly_alerts |
| 7 | `latency_p95_ms` | float | Module 10 - Testing | 5s | badge (metric card) | Threshold: <=500ms (prototype bar) |
| 8 | `throughput_evt_per_sec` | int | Module 5 - Cleaning / Module 4 - Kafka | 5s | chart (sparkline) | Recent event throughput visualization |
| 9 | `critical_alert.event_id` | string (UUID) | Module 7 - AI/ML | 5s | badge (alert banner) | Conditional render: risk_score>0.7 AND status=open |
| 10 | `critical_alert.risk_score` | float (0-1) | Module 7 - AI/ML | 5s | badge (alert banner) | Color-coded display |
| 11 | `critical_alert.source_type` | enum (alice/radar/lidar/telemetry) | Module 3 - Adaptation | 5s | badge (alert banner) | Helps operator identify origin |
| 12 | `recent_alerts[].event_id` | string (UUID) | Module 7 - AI/ML | 5s | table column | Clickable -> AI Alerts page |
| 13 | `recent_alerts[].timestamp` | datetime | Module 3 - Adaptation | 5s | table column | Format: HH:MM:SS; sorted newest-first |
| 14 | `recent_alerts[].source_type` | enum | Module 3 - Adaptation | 5s | table column | Color icon per source |
| 15 | `recent_alerts[].anomaly_label` | int (0/1) | Module 7 - AI/ML | 5s | table column | Filter: only label=1 shown |
| 16 | `recent_alerts[].risk_score` | float (0-1) | Module 7 - AI/ML | 5s | table column | Risk colour bar (left border) |
| 17 | `last_updated` | datetime | Module 9 - Dashboard (generated) | 5s | badge (timestamp) | Top-right; updates per poll cycle |

---

## 02 Live Stream — Live Stream

**Default refresh:** WebSocket (real-time)   |   **Total fields:** 15

| # | Field Name | Data Type | Source Module | Refresh | Widget | Notes |
|---|---|---|---|---|---|---|
| 1 | `connection_status` | enum (live/disconnected/reconnecting) | Module 9 - Dashboard (WS state) | N/A | badge | Exponential backoff: 1->2->4->8s |
| 2 | `throughput_evt_per_sec` | int | Module 4 - Kafka | real-time | chart (counter) | Sliding 60s window with 1s buckets |
| 3 | `filter.source_type` | enum | Module 9 - Dashboard (frontend state) | N/A | table (dropdown filter) | alice/radar/lidar/telemetry/all |
| 4 | `filter.anomaly_label` | string | Module 9 - Dashboard (frontend state) | N/A | table (search filter) | Debounced 300ms client-side |
| 5 | `filter.min_risk` | float (0-1) | Module 9 - Dashboard (frontend state) | N/A | table (slider filter) | Client-side filtering |
| 6 | `event.event_id` | string (UUID) | Module 3 - Adaptation | real-time | table column | From WS message |
| 7 | `event.timestamp_ms` | datetime | Module 3 - Adaptation | real-time | table column | Format: HH:MM:SS.mmm |
| 8 | `event.source_type` | enum | Module 3 - Adaptation | real-time | table column | Color icon |
| 9 | `event.anomaly_label` | int (0/1) | Module 7 - AI/ML | real-time | table column | When AI pipeline live |
| 10 | `event.risk_score` | float (0-1) | Module 7 - AI/ML | real-time | table column | Coloured left border (risk) |
| 11 | `event.quality_flag` | enum (clean/incomplete) | Module 5 - Cleaning | real-time | table column (icon) | From cleaning module |
| 12 | `total_processed` | int | Module 9 - Dashboard (session counter) | real-time | badge (counter) | Monotonic since page load |
| 13 | `filtered_count` | int | Module 9 - Dashboard (frontend derived) | real-time | badge (counter) | Matches active filters |
| 14 | `currently_showing` | int | Module 9 - Dashboard (frontend derived) | real-time | badge (counter) | Visible rows in virtual list |
| 15 | `pause_state` | bool | Module 9 - Dashboard (frontend state) | N/A | table (toggle button) | Buffers WS messages max 1000 |

---

## 03 Fusion Monitor — Fusion Monitor

**Default refresh:** REST 10s (poll)   |   **Total fields:** 13

| # | Field Name | Data Type | Source Module | Refresh | Widget | Notes |
|---|---|---|---|---|---|---|
| 1 | `fusion_quality_overall` | float (0-100) | Module 6 - Data Fusion | 10s | gauge | Full vs partial fusion ratio |
| 2 | `sensor.sensor_type` | enum | Module 2 - Sensor Source | 10s | badge (card title) | Per-sensor card |
| 3 | `sensor.status` | enum (nominal/noisy/dropout) | Module 2 - Sensor Source (via M5) | 10s | badge (card status) | Status colour coding |
| 4 | `sensor.fusion_match_rate` | float (0-1) | Module 6 - Data Fusion | 10s | chart (bar) | Ratio of fusion_quality=full |
| 5 | `sensor.data_loss_pct` | float (%) | Module 5 - Cleaning / Module 10 - Testing | 10s | badge (metric card) | Threshold: <=1% prototype bar |
| 6 | `sensor.latency_ms` | float | Module 5 - Cleaning | 10s | chart (sparkline) | Per-sensor latency trend |
| 7 | `sensor.contribution_weight` | float (0-1) | Module 6 - Data Fusion | 10s | chart (bar) | Sensor's share of fused events |
| 8 | `fusion_window_ms` | int | Module 6 - Data Fusion | 10s | badge (text) | Current tumbling window (default 2000ms) |
| 9 | `data_loss_alert` | bool | Module 9 - Dashboard (derived: data_loss>1%) | 10s | badge (alert banner) | Conditional render |
| 10 | `fused_event.fused_event_id` | string (UUID) | Module 6 - Data Fusion | on-demand | table column | Triggered on sensor card click |
| 11 | `fused_event.timestamp_ms` | datetime | Module 6 - Data Fusion | on-demand | table column | Earliest ts in fused set |
| 12 | `fused_event.alice_event_id` | string (UUID) | Module 6 - Data Fusion | on-demand | table column | Linked ALICE event |
| 13 | `fused_event.sensor_event_ids` | array<UUID> | Module 6 - Data Fusion | on-demand | table column | Matched sensor events |

---

## 04 AI Alerts — AI Alerts

**Default refresh:** REST 5s (poll)   |   **Total fields:** 18

| # | Field Name | Data Type | Source Module | Refresh | Widget | Notes |
|---|---|---|---|---|---|---|
| 1 | `summary.active_count` | int | Module 7 - AI/ML (status=open) | 5s | badge (metric card) | Total open alerts |
| 2 | `summary.critical_count` | int | Module 7 - AI/ML (risk_score>0.7) | 5s | badge (metric card) | Critical alerts |
| 3 | `summary.closed_today` | int | Module 9 - Dashboard (state) | 5s | badge (metric card) | Daily reset at midnight |
| 4 | `filter.date_range` | datetime range | Module 9 - Dashboard (frontend state) | N/A | table (date filter) | Server-side filter |
| 5 | `filter.source_type` | enum | Module 9 - Dashboard (frontend state) | N/A | table (dropdown filter) | alice/radar/lidar/telemetry |
| 6 | `filter.anomaly_label` | int (0/1) | Module 9 - Dashboard (frontend state) | N/A | table (dropdown filter) | Anomalous only / all |
| 7 | `filter.status` | enum (open/reviewed/closed) | Module 9 - Dashboard (frontend state) | N/A | table (dropdown filter) | Alert lifecycle stage |
| 8 | `filter.min_risk` | float (0-1) | Module 9 - Dashboard (frontend state) | N/A | table (slider filter) | Server-side filter |
| 9 | `alert.event_id` | string (UUID) | Module 7 - AI/ML | 5s | table column | Unique alert id |
| 10 | `alert.fused_event_id` | string (UUID) | Module 6 - Data Fusion | 5s | table column | Source fused event |
| 11 | `alert.timestamp_ms` | datetime | Module 3 - Adaptation | 5s | table column | Sortable; default DESC |
| 12 | `alert.source_type` | enum | Module 3 - Adaptation | 5s | table column | Color-coded |
| 13 | `alert.anomaly_label` | int (0/1) | Module 7 - AI/ML | 5s | table column (badge) | Anomaly classification |
| 14 | `alert.risk_score` | float (0-1) | Module 7 - AI/ML | 5s | table column | Color-coded; left-border severity |
| 15 | `alert.confidence` | float (0-1) | Module 7 - AI/ML | 5s | table column | Model certainty |
| 16 | `alert.status` | enum | Module 9 - Dashboard (state) | 5s | badge (in row) | PATCH'able via action buttons |
| 17 | `alert.model_version` | string (semver) | Module 7 - AI/ML | 5s | badge (footer text) | e.g. 1.0.0 |
| 18 | `alert.explanation_summary` | string (truncated) | Module 8 - XAI | 5s on expand | table (accordion content) | Top 1 SHAP feature inline |

---

## 05 XAI Panel — XAI Panel

**Default refresh:** REST on-demand   |   **Total fields:** 16

| # | Field Name | Data Type | Source Module | Refresh | Widget | Notes |
|---|---|---|---|---|---|---|
| 1 | `event.event_id` | string (UUID) | Module 7 - AI/ML | on load | badge (header text) | Page parameter ?event_id= |
| 2 | `event.timestamp_ms` | datetime | Module 3 - Adaptation | on load | badge (header text) | Full ISO format |
| 3 | `event.source_type` | enum | Module 3 - Adaptation | on load | badge (header) | Color-coded source |
| 4 | `event.risk_score` | float (0-1) | Module 7 - AI/ML | on load | gauge (circular) | Visual prominent display |
| 5 | `event.confidence` | float (0-1) | Module 7 - AI/ML | on load | badge (sub-text) | Below risk gauge |
| 6 | `event.anomaly_label` | int (0/1) | Module 7 - AI/ML | on load | badge | Anomalous / nominal |
| 7 | `explanation_text` | string (natural language) | Module 8 - XAI | on load | badge (paragraph box) | Plain-language operator-facing |
| 8 | `top_features` | array<string> | Module 8 - XAI | on load | badge (chip list) | Top 3 contributing features |
| 9 | `shap_values.feature` | string | Module 8 - XAI | on load | chart (horizontal bar label) | Feature name |
| 10 | `shap_values.value` | float | Module 8 - XAI | on load | chart (horizontal bar value) | SHAP magnitude |
| 11 | `shap_values.direction` | enum (positive/negative) | Module 8 - XAI (derived from sign) | on load | chart (bar colour) | Green=positive, red=negative |
| 12 | `feature_detail.feature` | string | Module 7 - AI/ML (features used) | on toggle | table column | Inline expand |
| 13 | `feature_detail.raw_value` | float | Module 7 - AI/ML | on toggle | table column | Original feature value |
| 14 | `xai_version` | string (semver) | Module 8 - XAI | on load | badge (footer text) | e.g. 1.0.0 |
| 15 | `model_version` | string (semver) | Module 7 - AI/ML | on load | badge (footer text) | Pair w/ XAI version |
| 16 | `raw_json_toggle` | bool | Module 9 - Dashboard (frontend state) | N/A | table (toggle button) | Expert view (raw SHAP JSON) |

---

## 06 Performance — Performance Metrics

**Default refresh:** REST 30s (poll)   |   **Total fields:** 11

| # | Field Name | Data Type | Source Module | Refresh | Widget | Notes |
|---|---|---|---|---|---|---|
| 1 | `time_range` | enum (15m/1h/6h/24h) | Module 9 - Dashboard (frontend state) | N/A | table (selector) | Determines query bucket size |
| 2 | `latency_p95.bucket_ts` | datetime | Module 10 - Testing | 30s | chart (line X-axis) | Time-series x-axis |
| 3 | `latency_p95.value_ms` | float | Module 10 - Testing | 30s | chart (line Y-axis) | Threshold line at 500ms (prototype bar) |
| 4 | `throughput.bucket_ts` | datetime | Module 10 - Testing | 30s | chart (bar X-axis) | Time-series buckets |
| 5 | `throughput.value_evt_per_sec` | int | Module 10 - Testing | 30s | chart (bar Y-axis) | Threshold line at 10K evt/s |
| 6 | `data_loss.bucket_ts` | datetime | Module 10 - Testing | 30s | chart (area X-axis) | Time-series buckets |
| 7 | `data_loss.value_pct` | float | Module 10 - Testing | 30s | chart (area Y-axis) | Threshold line at 1% |
| 8 | `model.auc` | float (0-1) | Module 10 - Testing (ML eval) | 30s | badge (metric card) | Threshold: >=0.85 prototype bar |
| 9 | `model.fpr` | float (0-1) | Module 10 - Testing (ML eval) | 30s | badge (metric card) | Threshold: <=5% prototype bar |
| 10 | `time_sync_accuracy_ms` | float | Module 5 - Cleaning (watermark stats) | 30s | badge (metric card) | Threshold: +/-1ms |
| 11 | `threshold_breach_alert` | string | Module 9 - Dashboard (derived) | 30s | badge (alert band) | Auto-render when any KPI breached |

---

## 07 Reports — Reports

**Default refresh:** REST on-demand   |   **Total fields:** 23

| # | Field Name | Data Type | Source Module | Refresh | Widget | Notes |
|---|---|---|---|---|---|---|
| 1 | `filter.date_range` | datetime range | Module 9 - Dashboard (frontend state) | N/A | table (date filter) | Required field |
| 2 | `filter.source_type` | enum | Module 9 - Dashboard (frontend state) | N/A | table (dropdown filter) | Optional filter |
| 3 | `filter.anomaly_label` | int (0/1) | Module 9 - Dashboard (frontend state) | N/A | table (dropdown filter) | Optional filter |
| 4 | `filter.min_risk` | float (0-1) | Module 9 - Dashboard (frontend state) | N/A | table (slider filter) | Optional filter |
| 5 | `summary.total_events` | int | Module 6 - Data Fusion (count) | on-demand | badge (metric card) | Aggregated over date range |
| 6 | `summary.total_anomalies` | int | Module 7 - AI/ML (label=1) | on-demand | badge (metric card) | Anomaly count |
| 7 | `summary.avg_risk_score` | float (0-1) | Module 7 - AI/ML | on-demand | badge (metric card) | Mean risk in window |
| 8 | `summary.avg_latency_ms` | float | Module 10 - Testing | on-demand | badge (metric card) | Average p95 across buckets |
| 9 | `summary.avg_data_loss_pct` | float | Module 10 - Testing | on-demand | badge (metric card) | Average across buckets |
| 10 | `anomaly_trend.bucket` | datetime (daily) | Module 7 - AI/ML (aggregated) | on-demand | chart (line X-axis) | Daily granularity |
| 11 | `anomaly_trend.count` | int | Module 7 - AI/ML | on-demand | chart (line Y-axis) | Anomalies per day |
| 12 | `sensor_perf.sensor_type` | enum | Module 2 - Sensor Source | on-demand | table column | Per-sensor breakdown row |
| 13 | `sensor_perf.uptime_pct` | float | Module 5 - Cleaning (derived from status) | on-demand | table column | Time with status != dropout |
| 14 | `sensor_perf.avg_latency_ms` | float | Module 5 - Cleaning / Module 10 - Testing | on-demand | table column | Average latency in window |
| 15 | `sensor_perf.event_count` | int | Module 5 - Cleaning | on-demand | table column | Cleaned events count |
| 16 | `sensor_perf.fusion_match_rate` | float (0-1) | Module 6 - Data Fusion | on-demand | table column | Fraction matched to ALICE |
| 17 | `top_riskiest.event_id` | string (UUID) | Module 7 - AI/ML | on-demand | table column | Top 10 by risk_score DESC |
| 18 | `top_riskiest.fused_event_id` | string (UUID) | Module 6 - Data Fusion | on-demand | table column | Linked fused event |
| 19 | `top_riskiest.timestamp_ms` | datetime | Module 3 - Adaptation | on-demand | table column | ISO timestamp |
| 20 | `top_riskiest.source_type` | enum | Module 3 - Adaptation | on-demand | table column | Source classification |
| 21 | `top_riskiest.risk_score` | float (0-1) | Module 7 - AI/ML | on-demand | table column | Default sort key |
| 22 | `top_riskiest.explanation_text` | string | Module 8 - XAI | on-demand | table column | Plain language explanation |
| 23 | `export.format` | enum (pdf/csv) | Module 9 - Dashboard (frontend state) | N/A | table (button) | Triggers /api/reports/export |

---

## Summary

- **Total fields documented:** 113 (was 112 — `critical_alerts` added to Home page in v3)
- **Pages with most fields:** AI Alerts (18) and Reports (23 — highest information density)
- **Real-time fields (WebSocket):** Live Stream only
- **On-demand fields:** XAI Panel and Reports (user-triggered loads)

## Next Steps

1. Share with Abdullah for review (M1W2T6 — deadline Thursday 22 May)
2. Update T10 (API endpoint list) refresh intervals to match (Home 30s -> 5s, Performance 10s -> 30s)
3. Use this as input to T11 (DB Table Sketches) — TimescaleDB hypertable design
4. Use this as input to T12 (API ↔ Dashboard Traceability Map)
5. Commit to `/dashboard/specs/` on GitHub by Friday 23 May (M1W2T16)
