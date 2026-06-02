# DataForge — API ↔ Dashboard Traceability Map

**Task:** M1W2T12 — API-to-Dashboard Traceability Map
**Owner:** Beyza Ülkümen — Full-Stack Developer (Module 9)
**Milestone:** 1 · Week 2 · 18–24 May 2026
**Output path:** `/docs/api/api_dashboard_traceability.md`
**Status:** Draft v1 — pending Abdullah review (M1W2T6)
**Aligned with:** T9 (`dashboard_data_fields.xlsx`) + T10 (`api_endpoints_v1.md`) + T11 (`db_table_sketches.md`) + Abdullah's `data_flow_spec.md`

---

## 1. Purpose

This document is a **traceability table** showing for every component on every dashboard page (a) which API endpoint feeds it, (b) which source module produces the data, and (c) which exact data field is consumed. The required format per brief is:

> **Page | Component | API Endpoint | Module Source | Data Field**

This map enforces two invariants:

1. **No orphan components** — every UI component on the dashboard has an identified data source.
2. **No orphan endpoints** — every API endpoint listed in T10 has at least one dashboard consumer.

Failure to maintain either invariant means we have shipped a component that won't render real data, or paid for an endpoint nobody calls. Both are bugs.

---

## 2. Methodology

The traceability was assembled by walking each page and:

1. Listing every UI component defined in T9 Section 5 (page-by-page deep dive).
2. For each component, identifying the field(s) it displays from T9 Overview sheet.
3. For each field, looking up the source module per T9 (already aligned with Abdullah's `data_flow_spec.md`).
4. For each field × refresh combination, mapping to the API endpoint that delivers it per T10.

Conventions used in the tables below:

| Marker | Meaning |
|---|---|
| **N/A (frontend)** | Component is frontend-state only — filter inputs, toggles, navigation links. No backend dependency. |
| **(derived)** | Field is computed by Module 9 from upstream module data, not stored directly. |
| **(config)** | Field is configuration data loaded from `prototype_bar.yaml` via `/api/v1/performance/thresholds`, not a runtime metric. |
| **(via WS)** | Endpoint delivers the field via WebSocket push rather than REST polling. |

---

## 3. Per-Page Traceability Tables

### 3.1 Home (REST 5s)

| Component | API Endpoint | Module Source | Data Field |
|---|---|---|---|
| StatusBand | `GET /api/v1/summary` | Module 9 (derived from Module 7) | `system_status` |
| SummaryCard (Active Sensors) | `GET /api/v1/summary` | Module 2 - Sensor Source | `active_sensors` |
| SummaryCard (Events Today) | `GET /api/v1/summary` | Module 6 - Data Fusion | `events_today` |
| SummaryCard (Active Alerts) | `GET /api/v1/summary` | Module 7 - AI/ML | `active_alerts` |
| SummaryCard (Critical Count) | `GET /api/v1/summary` | Module 7 - AI/ML | `critical_alerts` |
| SummaryCard (Avg Risk 1h) | `GET /api/v1/summary` | Module 7 - AI/ML (aggregated) | `avg_risk_score_1h` |
| SummaryCard (Latency p95) | `GET /api/v1/summary` | Module 10 - Testing | `latency_p95_ms` |
| Sparkline (Throughput) | `GET /api/v1/summary` | Module 4 - Kafka / Module 5 - Cleaning | `throughput_evt_per_sec` |
| CriticalAlertBanner.event_id | `GET /api/v1/summary` | Module 7 - AI/ML | `critical_alert.event_id` |
| CriticalAlertBanner.risk_score | `GET /api/v1/summary` | Module 7 - AI/ML | `critical_alert.risk_score` |
| CriticalAlertBanner.source_type | `GET /api/v1/summary` | Module 3 - Adaptation | `critical_alert.source_type` |
| CriticalAlertBanner.timestamp | `GET /api/v1/summary` | Module 3 - Adaptation | `critical_alert.timestamp` |
| RecentAlertsList row.event_id | `GET /api/v1/alerts/recent?limit=5` | Module 7 - AI/ML | `alerts[].event_id` |
| RecentAlertsList row.timestamp | `GET /api/v1/alerts/recent?limit=5` | Module 3 - Adaptation | `alerts[].timestamp` |
| RecentAlertsList row.source_type | `GET /api/v1/alerts/recent?limit=5` | Module 3 - Adaptation | `alerts[].source_type` |
| RecentAlertsList row.anomaly_label | `GET /api/v1/alerts/recent?limit=5` | Module 7 - AI/ML | `alerts[].anomaly_label` |
| RecentAlertsList row.risk_score | `GET /api/v1/alerts/recent?limit=5` | Module 7 - AI/ML | `alerts[].risk_score` |
| QuickNav.LiveStreamLink | N/A (frontend) | — | — |
| QuickNav.AIAlertsLink | N/A (frontend) | — | — |
| QuickNav.PerformanceLink | N/A (frontend) | — | — |
| LastUpdated | `GET /api/v1/summary` | Module 9 (generated) | `last_updated` |

**Endpoints used:** 2 — `/api/v1/summary`, `/api/v1/alerts/recent`

---

### 3.2 Live Stream (WebSocket real-time)

| Component | API Endpoint | Module Source | Data Field |
|---|---|---|---|
| ConnectionStatus | `WS /api/v1/ws/stream` (connection state) | Module 9 (WS state) | `connection_status` |
| ThroughputCounter | `GET /api/v1/stream/info` (initial) + WS (derived) | Module 4 - Kafka | `current_throughput_evt_per_sec` |
| FilterBar.source_type dropdown | N/A (frontend) | — | `filter.source_type` |
| FilterBar.anomaly_label search | N/A (frontend) | — | `filter.anomaly_label` |
| FilterBar.min_risk slider | N/A (frontend) | — | `filter.min_risk` |
| PauseButton | N/A (frontend) | — | `pause_state` |
| LiveEventTable col event_id | `WS /api/v1/ws/stream` | Module 3 - Adaptation | `event.event_id` |
| LiveEventTable col timestamp | `WS /api/v1/ws/stream` | Module 3 - Adaptation | `event.timestamp` |
| LiveEventTable col source_type | `WS /api/v1/ws/stream` | Module 3 - Adaptation | `event.source_type` |
| LiveEventTable col anomaly_label | `WS /api/v1/ws/stream` | Module 7 - AI/ML | `event.anomaly_label` |
| LiveEventTable col risk_score | `WS /api/v1/ws/stream` | Module 7 - AI/ML | `event.risk_score` |
| LiveEventTable col quality_flag (icon) | `WS /api/v1/ws/stream` | Module 5 - Cleaning | `event.quality_flag` |
| EventCounter.total_processed | `WS /api/v1/ws/stream` (session counter) | Module 9 (own state) | `total_processed` |
| EventCounter.filtered_count | N/A (frontend derived) | — | `filtered_count` |
| EventCounter.currently_showing | N/A (frontend derived) | — | `currently_showing` |

**Endpoints used:** 2 — `WS /api/v1/ws/stream`, `GET /api/v1/stream/info`

---

### 3.3 Fusion Monitor (REST 10s + WebSocket)

| Component | API Endpoint | Module Source | Data Field |
|---|---|---|---|
| FusionQualityGauge | `GET /api/v1/fusion/sensors` | Module 6 - Data Fusion | `fusion_quality_overall` |
| SensorStatusGrid card.sensor_type | `GET /api/v1/fusion/sensors` | Module 2 - Sensor Source | `sensors[].sensor_type` |
| SensorStatusGrid card.status | `GET /api/v1/fusion/sensors` | Module 2 - Sensor Source (via M5) | `sensors[].status` |
| SensorStatusGrid card.fusion_match_rate | `GET /api/v1/fusion/sensors` | Module 6 - Data Fusion | `sensors[].fusion_match_rate` |
| SensorStatusGrid card.data_loss_pct | `GET /api/v1/fusion/sensors` | Module 5 - Cleaning / Module 10 | `sensors[].data_loss_pct` |
| SensorStatusGrid card.quality_score | `GET /api/v1/fusion/sensors` | Module 6 - Data Fusion | `sensors[].quality_score` |
| ContributionWeightBars | `GET /api/v1/fusion/sensors` | Module 6 - Data Fusion | `sensors[].contribution_weight` |
| LatencySparkline (per sensor) | `GET /api/v1/fusion/sensors` | Module 5 - Cleaning | `sensors[].latency_ms` |
| FusionWindowText | `GET /api/v1/fusion/sensors` | Module 6 - Data Fusion | `fusion_window_ms` |
| DataLossAlert (conditional banner) | `GET /api/v1/fusion/sensors` (derived) | Module 9 (derived: data_loss>1%) | `data_loss_alert` |
| FusedEventDrillDown.fused_event_id | `GET /api/v1/fusion/events?sensor_type=…` | Module 6 - Data Fusion | `events[].fused_event_id` |
| FusedEventDrillDown.timestamp | `GET /api/v1/fusion/events` | Module 6 - Data Fusion | `events[].timestamp` |
| FusedEventDrillDown.alice_event_id | `GET /api/v1/fusion/events` | Module 6 - Data Fusion | `events[].alice_event_id` |
| FusedEventDrillDown.sensor_event_ids | `GET /api/v1/fusion/events` | Module 6 - Data Fusion | `events[].sensor_event_ids` |
| LiveSensorStatusUpdate | `WS /api/v1/ws/fusion` | Module 6 - Data Fusion | (per-sensor status push) |

**Endpoints used:** 3 — `GET /api/v1/fusion/sensors`, `GET /api/v1/fusion/events`, `WS /api/v1/ws/fusion`

---

### 3.4 AI Alerts (REST 5s)

| Component | API Endpoint | Module Source | Data Field |
|---|---|---|---|
| SummaryCard.active_count | `GET /api/v1/alerts/summary` | Module 7 - AI/ML | `active_count` |
| SummaryCard.critical_count | `GET /api/v1/alerts/summary` | Module 7 - AI/ML | `critical_count` |
| SummaryCard.closed_today | `GET /api/v1/alerts/summary` | Module 9 (state) | `closed_today` |
| FilterBar.date_range picker | N/A (frontend) | — | `filter.date_range` |
| FilterBar.source_type dropdown | N/A (frontend) | — | `filter.source_type` |
| FilterBar.anomaly_label dropdown | N/A (frontend) | — | `filter.anomaly_label` |
| FilterBar.status dropdown | N/A (frontend) | — | `filter.status` |
| FilterBar.min_risk slider | N/A (frontend) | — | `filter.min_risk` |
| AlertTable col event_id | `GET /api/v1/alerts` | Module 7 - AI/ML | `alerts[].event_id` |
| AlertTable col fused_event_id | `GET /api/v1/alerts` | Module 6 - Data Fusion | `alerts[].fused_event_id` |
| AlertTable col timestamp | `GET /api/v1/alerts` | Module 3 - Adaptation | `alerts[].timestamp` |
| AlertTable col source_type | `GET /api/v1/alerts` | Module 3 - Adaptation | `alerts[].source_type` |
| AlertTable col anomaly_label | `GET /api/v1/alerts` | Module 7 - AI/ML | `alerts[].anomaly_label` |
| AlertTable col risk_score | `GET /api/v1/alerts` | Module 7 - AI/ML | `alerts[].risk_score` |
| AlertTable col confidence | `GET /api/v1/alerts` | Module 7 - AI/ML | `alerts[].confidence` |
| AlertTable col status (badge) | `GET /api/v1/alerts` | Module 9 (state) | `alerts[].status` |
| AlertTable.actionButton (PATCH) | `PATCH /api/v1/alerts/{id}` | Module 9 (state) | `status` (body) |
| AlertTable col model_version (footer) | `GET /api/v1/alerts` | Module 7 - AI/ML | `alerts[].model_version` |
| AccordionRow.explanation_summary | `GET /api/v1/alerts/{id}` | Module 8 - XAI | `explanation_summary` |
| Pagination controls | `GET /api/v1/alerts` (page/limit params) | Module 9 (server-side) | `pagination.{page, limit, total, total_pages}` |

**Endpoints used:** 4 — `GET /api/v1/alerts`, `/alerts/summary`, `/alerts/{id}`, `PATCH /alerts/{id}`

---

### 3.5 XAI Panel (REST on-demand)

| Component | API Endpoint | Module Source | Data Field |
|---|---|---|---|
| EventHeader.event_id | `GET /api/v1/alerts/{id}/xai` | Module 7 - AI/ML | `event_id` |
| EventHeader.timestamp | `GET /api/v1/alerts/{id}/xai` (or `/alerts/{id}`) | Module 3 - Adaptation | `event.timestamp` |
| EventHeader.source_type badge | `GET /api/v1/alerts/{id}/xai` | Module 3 - Adaptation | `event.source_type` |
| RiskGauge (circular) | `GET /api/v1/alerts/{id}/xai` | Module 7 - AI/ML | `risk_score` |
| ConfidenceSubText | `GET /api/v1/alerts/{id}/xai` | Module 7 - AI/ML | `confidence` |
| AnomalyLabelBadge | `GET /api/v1/alerts/{id}/xai` | Module 7 - AI/ML | `anomaly_label` |
| PlainLanguageBox | `GET /api/v1/alerts/{id}/xai` | Module 8 - XAI | `explanation_text` |
| TopFeaturesChipList | `GET /api/v1/alerts/{id}/xai` | Module 8 - XAI | `top_features[]` |
| SHAPBarChart feature labels | `GET /api/v1/alerts/{id}/xai` | Module 8 - XAI | `shap_values[].feature` |
| SHAPBarChart value bars | `GET /api/v1/alerts/{id}/xai` | Module 8 - XAI | `shap_values[].shap_value` |
| SHAPBarChart bar colour | `GET /api/v1/alerts/{id}/xai` | Module 8 - XAI (derived from sign) | `shap_values[].direction` |
| FeatureDetailTable feature | `GET /api/v1/alerts/{id}` (raw_features) | Module 7 - AI/ML | `raw_features.{key}` |
| FeatureDetailTable raw_value | `GET /api/v1/alerts/{id}` (raw_features) | Module 7 - AI/ML | `raw_features.{key}` |
| Footer.xai_version | `GET /api/v1/alerts/{id}/xai` | Module 8 - XAI | `xai_version` |
| Footer.model_version | `GET /api/v1/alerts/{id}/xai` | Module 7 - AI/ML | `model_version` |
| ExpertJSONToggle | N/A (frontend) | — | `raw_json_toggle` |

**Endpoints used:** 2 — `GET /api/v1/alerts/{id}/xai`, `GET /api/v1/alerts/{id}` (for raw_features)

---

### 3.6 Performance Metrics (REST 30s)

| Component | API Endpoint | Module Source | Data Field |
|---|---|---|---|
| TimeRangeSelector | N/A (frontend) | — | `time_range` |
| LatencyP95LineChart X-axis | `GET /api/v1/performance` | Module 10 - Testing | `series.latency_p95_ms[].bucket_ts` |
| LatencyP95LineChart Y-axis | `GET /api/v1/performance` | Module 10 - Testing | `series.latency_p95_ms[].value` |
| LatencyP95 threshold line (500ms) | `GET /api/v1/performance/thresholds` | Module 9 (config) | `latency_p95_ms_max` |
| ThroughputBarChart X-axis | `GET /api/v1/performance` | Module 10 - Testing | `series.throughput_evt_per_sec[].bucket_ts` |
| ThroughputBarChart Y-axis | `GET /api/v1/performance` | Module 10 - Testing | `series.throughput_evt_per_sec[].value` |
| Throughput threshold line (≥10K) | `GET /api/v1/performance/thresholds` | Module 9 (config) | `throughput_evt_per_sec_min` |
| DataLossAreaChart X-axis | `GET /api/v1/performance` | Module 10 - Testing | `series.data_loss_pct[].bucket_ts` |
| DataLossAreaChart Y-axis | `GET /api/v1/performance` | Module 10 - Testing | `series.data_loss_pct[].value` |
| DataLoss threshold line (1%) | `GET /api/v1/performance/thresholds` | Module 9 (config) | `data_loss_pct_max` |
| AUCMetricCard | `GET /api/v1/performance` | Module 10 - Testing | `current.model_auc` |
| AUC threshold (≥0.85) | `GET /api/v1/performance/thresholds` | Module 9 (config) | `model_auc_min` |
| FPRMetricCard | `GET /api/v1/performance` | Module 10 - Testing | `current.model_fpr` |
| FPR threshold (≤5%) | `GET /api/v1/performance/thresholds` | Module 9 (config) | `model_fpr_max` |
| TimeSyncCard | `GET /api/v1/performance` | Module 5 - Cleaning (watermark stats) | `current.time_sync_accuracy_ms` |
| TimeSync threshold (±1ms) | `GET /api/v1/performance/thresholds` | Module 9 (config) | `time_sync_accuracy_ms_max` |
| ThresholdBreachAlert | `GET /api/v1/performance` (derived) | Module 9 (derived) | `thresholds_breached` |

**Endpoints used:** 2 — `GET /api/v1/performance`, `GET /api/v1/performance/thresholds`

---

### 3.7 Reports (REST on-demand)

| Component | API Endpoint | Module Source | Data Field |
|---|---|---|---|
| FilterPanel.date_range (required) | N/A (frontend) | — | `filter.date_range` |
| FilterPanel.source_type | N/A (frontend) | — | `filter.source_type` |
| FilterPanel.anomaly_label | N/A (frontend) | — | `filter.anomaly_label` |
| FilterPanel.min_risk | N/A (frontend) | — | `filter.min_risk` |
| SummaryCard.total_events | `GET /api/v1/reports` | Module 6 - Data Fusion (count) | `summary.total_events` |
| SummaryCard.total_anomalies | `GET /api/v1/reports` | Module 7 - AI/ML (label=1) | `summary.total_anomalies` |
| SummaryCard.avg_risk_score | `GET /api/v1/reports` | Module 7 - AI/ML | `summary.avg_risk_score` |
| SummaryCard.avg_latency_ms | `GET /api/v1/reports` | Module 10 - Testing | `summary.avg_latency_ms` |
| SummaryCard.avg_data_loss_pct | `GET /api/v1/reports` | Module 10 - Testing | `summary.avg_data_loss_pct` |
| AnomalyTrendChart X (daily bucket) | `GET /api/v1/reports` | Module 7 - AI/ML (aggregated) | `anomaly_trend[].bucket` |
| AnomalyTrendChart Y (count) | `GET /api/v1/reports` | Module 7 - AI/ML (aggregated) | `anomaly_trend[].count` |
| SensorPerformanceTable col sensor_type | `GET /api/v1/reports` | Module 2 - Sensor Source | `sensor_performance[].sensor_type` |
| SensorPerformanceTable col uptime_pct | `GET /api/v1/reports` | Module 5 - Cleaning (derived from status) | `sensor_performance[].uptime_pct` |
| SensorPerformanceTable col avg_latency_ms | `GET /api/v1/reports` | Module 5 - Cleaning / Module 10 | `sensor_performance[].avg_latency_ms` |
| SensorPerformanceTable col event_count | `GET /api/v1/reports` | Module 5 - Cleaning | `sensor_performance[].event_count` |
| SensorPerformanceTable col fusion_match_rate | `GET /api/v1/reports` | Module 6 - Data Fusion | `sensor_performance[].fusion_match_rate` |
| Top10RiskiestTable col event_id | `GET /api/v1/reports` | Module 7 - AI/ML | `top_riskiest[].event_id` |
| Top10RiskiestTable col fused_event_id | `GET /api/v1/reports` | Module 6 - Data Fusion | `top_riskiest[].fused_event_id` |
| Top10RiskiestTable col timestamp | `GET /api/v1/reports` | Module 3 - Adaptation | `top_riskiest[].timestamp` |
| Top10RiskiestTable col source_type | `GET /api/v1/reports` | Module 3 - Adaptation | `top_riskiest[].source_type` |
| Top10RiskiestTable col risk_score | `GET /api/v1/reports` | Module 7 - AI/ML | `top_riskiest[].risk_score` |
| Top10RiskiestTable col explanation_text | `GET /api/v1/reports` | Module 8 - XAI | `top_riskiest[].explanation_text` |
| ExportButton (PDF/CSV) | `GET /api/v1/reports/export?format=…` | Module 9 + ReportLab | (file stream) |

**Endpoints used:** 2 — `GET /api/v1/reports`, `GET /api/v1/reports/export`

---

## 4. Reverse View 1 — Endpoint × Consuming Pages

For each of the 18 endpoints, which page(s) consume it. This validates that **no endpoint is orphaned**.

| # | Endpoint | Consuming pages | Status |
|---|---|---|---|
| 1 | `GET /api/v1/summary` | Home | ✓ consumed |
| 2 | `GET /api/v1/stream/info` | Live Stream | ✓ consumed |
| 3 | `GET /api/v1/alerts/recent` | Home, AI Alerts | ✓ consumed (multi-page) |
| 4 | `GET /api/v1/alerts` | AI Alerts | ✓ consumed |
| 5 | `GET /api/v1/alerts/summary` | AI Alerts | ✓ consumed |
| 6 | `GET /api/v1/alerts/{id}` | AI Alerts, XAI Panel | ✓ consumed (multi-page) |
| 7 | `PATCH /api/v1/alerts/{id}` | AI Alerts | ✓ consumed |
| 8 | `GET /api/v1/alerts/{id}/xai` | XAI Panel | ✓ consumed |
| 9 | `GET /api/v1/fusion/sensors` | Fusion Monitor | ✓ consumed |
| 10 | `GET /api/v1/fusion/events` | Fusion Monitor | ✓ consumed |
| 11 | `GET /api/v1/performance` | Performance | ✓ consumed |
| 12 | `GET /api/v1/performance/thresholds` | Performance | ✓ consumed |
| 13 | `GET /api/v1/reports` | Reports | ✓ consumed |
| 14 | `GET /api/v1/reports/export` | Reports | ✓ consumed |
| 15 | `GET /api/v1/health` | (none — external monitor) | ⚠ no dashboard consumer (expected — health check) |
| 16 | `GET /api/v1/health/upstream` | (none — debug only) | ⚠ no dashboard consumer (expected — debug) |
| 17 | `WS /api/v1/ws/stream` | Live Stream | ✓ consumed |
| 18 | `WS /api/v1/ws/fusion` | Fusion Monitor | ✓ consumed |

**Result:** 16/18 endpoints have a dashboard consumer. The 2 exceptions (`/health`, `/health/upstream`) are intentional — they serve external uptime monitors and dev debugging, not the dashboard UI. **No accidentally orphan endpoints.**

---

## 5. Reverse View 2 — Module × Downstream Pages

For each upstream module, which dashboard pages depend on it. This shows where outages propagate.

| Module | Pages affected | Risk if module unavailable |
|---|---|---|
| Module 1 - ALICE Data Source | (transitively all event-driven pages) | Pipeline empty; no ALICE-based fused events |
| Module 2 - Sensor Source | Home (Active Sensors), Fusion Monitor (cards), Reports (sensor_perf) | Sensor cards empty, active_sensors=0 |
| Module 3 - Data Adaptation | All 7 pages (event_id, timestamp, source_type are universal) | Dashboard entirely empty |
| Module 4 - Kafka | Live Stream (WS bridge), Home (throughput sparkline) | Live Stream cannot connect; Home throughput=0 |
| Module 5 - Cleaning | Live Stream (quality_flag), Fusion Monitor (latency, data_loss), Performance (time_sync), Reports (uptime, event_count) | Quality icons missing; latency sparklines empty; uptime can't be computed |
| Module 6 - Data Fusion | Fusion Monitor (core), Home (events_today), AI Alerts (fused_event_id), Reports (fusion_match_rate, total_events) | Fusion Monitor empty; Home events_today=0; AI Alerts missing fused id |
| Module 7 - AI/ML | Home (critical alerts, avg_risk), AI Alerts (core), XAI Panel (risk, anomaly_label), Reports (anomaly_trend, top_riskiest) | AI Alerts entirely empty; XAI Panel contentless; Home no critical alerts |
| Module 8 - XAI | XAI Panel (core), AI Alerts (accordion summary), Reports (top_riskiest.explanation_text) | XAI Panel contentless; AI Alerts loses inline explanation |
| Module 10 - Testing | Home (latency_p95), Performance (all KPIs), Reports (avg_latency, avg_data_loss) | Performance page entirely empty; Home latency card missing |

**Result:** Every module that produces fields has at least one downstream consumer. **No orphan modules in the dashboard.**

The page most resilient to upstream outages is **Live Stream with M7 down**: it can still show raw events from M3/M4/M5, just without AI labels — the table degrades gracefully to a plain event stream. The page **least resilient** is **AI Alerts**: it requires M7 + M9 state + M8 (for accordion) to be useful at all.

---

## 6. Coverage Statistics

| Metric | Value |
|---|---|
| Total UI components mapped | **132** across 7 pages |
| Components with API endpoint | **101** (76.5%) |
| Components purely frontend (N/A) | **31** (23.5%) — filter inputs, toggles, nav links |
| Distinct REST endpoints consumed by UI | **14 of 16** (87.5%; 2 health endpoints excluded by design) |
| Distinct WS endpoints consumed by UI | **2 of 2** (100%) |
| Distinct modules referenced | **9 of 10** (Module 1 transitively only — not directly named in UI) |

Components per page:

| Page | Components | API-backed | Frontend-only |
|---|---|---|---|
| Home | 21 | 18 | 3 (QuickNav links) |
| Live Stream | 15 | 10 | 5 (filters, pause, derived counters) |
| Fusion Monitor | 15 | 15 | 0 |
| AI Alerts | 20 | 15 | 5 (filter inputs) |
| XAI Panel | 16 | 15 | 1 (ExpertJSONToggle) |
| Performance | 17 | 16 | 1 (TimeRangeSelector) |
| Reports | 28 | 24 | 4 (filter inputs) |

**Most API-dependent page:** Reports (24/28 components hit the backend).
**Most frontend-heavy page:** Live Stream (5/15 components are pure frontend state — typical for streaming UIs where the WS feed is one channel and the user controls everything else locally).

---

## 7. Gap Analysis

A walkthrough looking for missing connections:

### Orphan components (components without a data source)

**None found.** Every UI component listed in T9 Section 5 maps to either an endpoint or N/A (frontend-only).

### Orphan endpoints (endpoints without a consumer)

**2 expected, 0 unexpected.**
- `/api/v1/health` — by design (external monitor consumer)
- `/api/v1/health/upstream` — by design (dev debugging)

### Modules with no UI surface

**Module 1 (ALICE Data Source)** is the only module that does not appear by name in any dashboard component. This is correct: M1 is a data source, not a metric-producing module. Its output flows through M3 (Adaptation) which is the named source for `event_id`, `source_type`, etc. **No action needed.**

### Single points of failure (modules feeding many pages)

Three modules are critical to dashboard usability:
1. **Module 3 - Adaptation** → if down, dashboard is fully empty (all 7 pages).
2. **Module 7 - AI/ML** → if down, 4 pages lose major functionality (Home, AI Alerts, XAI Panel, Reports).
3. **Module 10 - Testing** → if KPIs aren't being written, Performance page is empty and Home metric card breaks.

Recommendation: M9 should explicitly handle "module degraded" states. The `/api/v1/health/upstream` endpoint already reports per-module status; the dashboard should display a banner when a critical upstream is degraded. **Action item for M2.**

### Endpoints with single consumer (potential to merge)

- `/api/v1/performance/thresholds` is only consumed by Performance page. Could it be inlined into `/api/v1/performance`? Yes, but keeping it separate allows caching (thresholds change rarely) and simpler config refresh. **Keep separate.**
- `/api/v1/stream/info` is only used at Live Stream page load. Could it be merged into `WS /api/v1/ws/stream` as the first message after connect? Possibly cleaner. **Consider M2.**

---

## 8. Open Questions for Abdullah (Wednesday review)

1. **Live Stream WS `connection_status` field** — is "Module 9 (WS state)" an acceptable source label, or should this be reframed as a frontend-only state with no backend dependency? Currently listed as Module 9 since the WS server lifecycle drives it.
2. **`/api/v1/alerts/{id}` vs `/alerts/{id}/xai`** — XAI Panel reads from both (`/xai` for SHAP, `/{id}` for `raw_features`). Should `raw_features` be moved into `/xai` to make XAI Panel a single-endpoint page?
3. **Threshold lines vs current values on Performance page** — currently 2 separate endpoints (`/performance` for time-series, `/performance/thresholds` for static config). Acceptable?
4. **`/api/v1/health/upstream`** — should there be a dashboard component (e.g. a hidden "system health" page or a status banner) that consumes this, or remain admin-only? Currently no UI consumer.
5. **PATCH consumption granularity** — `PATCH /api/v1/alerts/{id}` shows in the table once but is consumed by every AlertTable action button. Should we expand or aggregate it in the chain? Currently aggregated.
6. **WebSocket vs REST for Fusion Monitor sensor updates** — sensor status comes from both `/api/v1/fusion/sensors` (10s poll) AND `WS /api/v1/ws/fusion` (push). Is this duplication acceptable for prototype, or should one be eliminated?

---

## 9. Implications for Implementation

### For Module 9 (Beyza — own work)

- **API routers** should be organised one file per endpoint family. `/api/v1/alerts/*` becomes `routers/alerts.py`, etc. (Feeds T13 FastAPI folder structure.)
- **Frontend page components** should consume one endpoint set per page; aggregate hooks (e.g. `useHomeData()`) wrap the relevant calls.
- **Critical-path testing priority** (M10): start with Home and AI Alerts since they have the most cross-module dependencies.

### For other modules (coordination)

- **Module 7 + Module 8 contracts** — finalised at M2 sync. The `/api/v1/alerts/{id}/xai` response schema must be locked before M9 implementation starts.
- **Module 4 (Omer)** — Kafka topic for WS bridge needs to be agreed. Currently assumed: `clean_events` (output of M5).
- **Module 10 (shared)** — `system_performance_metrics` writer schedule needs to be defined. 1-minute cron? Streaming aggregation? Decision feeds the index strategy.

---

## 10. Next Steps

1. **Wednesday 22 May EOD** — Share this map with Abdullah for M1W2T6 review (alongside T9, T10, T11 deliverables).
2. **Thursday 22 May** — Incorporate feedback into v2.
3. **Friday 23 May** — Commit `api_dashboard_traceability.md` to `/docs/api/` on GitHub (M1W2T16).
4. **M2** — Use this map as a checklist when implementing FastAPI routers; every endpoint listed here must have a passing integration test.
5. **M5–M9** — Re-validate the map as modules ship; any new component or endpoint must update this document.

---

## 11. References

- T9 deliverable — `dashboard_data_fields.xlsx` + `.md` (in `/dashboard/specs/`)
- T10 deliverable — `api_endpoints_v1.md` (in `/docs/api/`)
- T11 deliverable — `db_table_sketches.md` (in `/docs/database/`)
- Abdullah's data flow spec — `data_flow_spec.md`
- T9 detailed report — `DataForge_T9_Detailed_Report_EN_v2.docx` (Section 5 component breakdown)

---

*Draft v1 prepared 22 May 2026 by Beyza Ülkümen. To be reviewed by Abdullah (M1W2T6). Final committed to `/docs/api/api_dashboard_traceability.md` on GitHub by Friday 23 May (M1W2T16).*
