# DataForge — Milestone 1 Package
## Dashboard & Database Section

**Section Owner:** Beyza Ülkümen — Full-Stack Developer (Module 9)  
**Assembled by:** Abdullah (M1 Package Lead)  
**Milestone:** 1 · Weeks 1–3 · 11 May – 7 June 2026  
**Submitted to:** Emrah Uysal — Dataseed Yazılım Elektronik  
**Document path:** `/docs/milestone1/m1_dashboard_db_section.md`

---

## Executive Summary

During Milestone 1, Beyza Ülkümen produced the complete design specification for DataForge's dashboard and database layer — the operator-facing component of Module 9. This section documents what was designed, why specific decisions were made, and how this work feeds into the Milestone 2 and Milestone 9 implementation phases.

**Deliverables produced (Weeks 1–3):**

| Task | Deliverable | GitHub Path |
|---|---|---|
| M1W1T2 | 7 Dashboard Pages Definition poster | `/docs/` |
| M1W1T4 | API Requirements poster | `/docs/` |
| M1W1T5 | Wireframe Sketches guide + poster | `/docs/` |
| M1W2T9 | Dashboard Data Field Specifications (112 fields) | `/services/dashboard/specs/dashboard_data_fields.md` |
| M1W2T10 | API Endpoint List v1 (18 endpoints) | `/docs/api/api_endpoints_v1.md` |
| M1W2T11 | Database Table Sketches v1 (7 tables) | `/docs/database/db_table_sketches.md` |
| M1W2T12 | API-to-Dashboard Traceability Map (132 components) | `/docs/api/api_dashboard_traceability.md` |
| M1W2T13 | FastAPI Project Folder Structure Plan | `/docs/api/fastapi_project_structure.md` |
| M1W3T8 | Wireframes — All 7 Dashboard Pages | `/services/dashboard/wireframes/` |
| M1W3T9 | Empty / Loading / Error States — All 7 Pages | `/services/dashboard/specs/ui_states.md` |
| M1W3T10 | UI/API Requirements Document — Final Version | `/docs/api/ui_api_requirements_final.docx` |
| M1W3T11 | Database Table Sketches v2 — Revised & Expanded | `/docs/database/db_table_sketches_v2.md` |
| M1W3T12 | TimescaleDB Continuous Aggregates Research Note | `/docs/research/timescaledb_continuous_aggregates.md` |
| M1W3T13 | High-Fidelity Mockups — Home & AI Alerts | `/services/dashboard/wireframes/mockup_*_hifi.png` |

---

## 1. Dashboard Overview — 7 Pages

The DataForge dashboard is the operator's window into the entire pipeline — from raw sensor ingestion through AI anomaly detection to explainable decisions. It is built in ReactJS with a FastAPI backend and TimescaleDB as the time-series database. The dashboard has 7 pages, each designed for a specific operator use case.

### 1.1 Page-by-Page Summary

#### Page 01 — Home (System Health Overview)

**Operator use case:** First screen operators see when they open DataForge. Answers one question: *"Is the system OK right now?"* in under 3 seconds.

The Home page displays four summary KPI cards (active sensors, active alert count, average risk score over the last hour, and latency p95), a throughput sparkline, and a conditional critical alert banner that appears only when a risk score exceeds 0.7. Below these, the five most recent alerts are listed in a compact table with risk colour-coding. Three quick navigation buttons link directly to Live Stream, AI Alerts, and Performance pages.

**Data source:** `GET /api/v1/summary` polling every 5 seconds. Summary metrics are served from the `summary_1h` TimescaleDB continuous aggregate — making the response time under 5ms regardless of raw event volume.

**Key design decision:** The Home page is deliberately minimal. Operators should be able to assess system health in a single glance. Detailed analysis is one click away in the relevant sub-page.

---

#### Page 02 — Live Stream (Real-Time Event Monitor)

**Operator use case:** Watch raw sensor events arrive in real time. Used during pipeline bring-up, incident investigation, and performance monitoring. Answers: *"What is happening right now, event by event?"*

The Live Stream page connects to a WebSocket endpoint and displays events as they arrive from the Kafka pipeline. A virtual list (react-window) keeps exactly 50 rows in the DOM and 200 in memory — preventing browser freeze at high event rates. Events are colour-coded by risk score using a left-border strip. A filter bar allows client-side filtering by sensor type, anomaly label, and minimum risk score without server round trips. A pause button buffers up to 1,000 incoming messages while the operator reads the table.

**Data source:** `WS /api/v1/ws/stream` — persistent WebSocket connection. The backend bridges the Kafka `clean_events` topic directly to connected WebSocket clients. No database read occurs during live streaming — this is by design.

**Key design decision:** WebSocket (not REST polling) is the only viable choice for this page. At up to 10,000 events per second, a 5-second REST poll would return 50,000 events per request — too large to render and too slow to feel live. WebSocket pushes each event individually as it arrives from Kafka.

---

#### Page 03 — Fusion Monitor (Multi-Sensor Fusion Status)

**Operator use case:** Monitor the health of the data fusion layer (Module 6). Answers: *"Are all sensors contributing correctly? Is any sensor losing data?"*

The Fusion Monitor displays a 2×2 grid of sensor status cards — one per sensor type (RADAR, LIDAR, IMU, TELEMETRY). Each card shows the sensor's current quality score (0–100), contribution weight to the fusion output, pipeline latency, and data loss percentage. A horizontal bar chart visualises contribution weights side by side. A conditional alert banner appears when any sensor's data loss exceeds the 1% prototype bar threshold. A table of recent fused events is available on demand by clicking a sensor card.

**Data source:** `GET /api/v1/fusion/sensors` polling every 10 seconds. Additionally, `WS /api/v1/ws/fusion` pushes fusion engine heartbeats in real time for the status indicators.

**Key design decision:** The Fusion Monitor is the operator's early warning system for data quality degradation. If IMU data loss rises above 1%, the dashboard signals this before it affects AI model accuracy. This page bridges Omer's pipeline work (Module 6) and Beyza's frontend in a way that is immediately actionable for the operator.

---

#### Page 04 — AI Alerts (Anomaly Alert Inbox)

**Operator use case:** Review, acknowledge, and close AI-generated anomaly alerts. Answers: *"What has the AI model flagged, and how serious is it?"*

The AI Alerts page is the primary operational interface for anomaly management. It presents all alerts sorted by risk score descending (highest risk first) in a filterable table. Each row shows the event ID, timestamp, sensor type, anomaly label, risk score, model confidence, and current status (active / reviewed / closed). Rows are colour-coded by risk level using a left border strip. Clicking a row expands an inline explanation summary. Two action buttons per row allow the operator to view the full XAI explanation (links to XAI Panel) or acknowledge/close the alert via a PATCH request.

Three summary cards at the top show active alert count, critical alert count (risk > 0.9), and alerts closed today — giving an instant triage overview.

**Data source:** `GET /api/v1/alerts` polling every 5 seconds with support for date, sensor, status, and minimum risk filters. `GET /api/v1/alerts/summary` polling every 5 seconds for the three summary cards. `PATCH /api/v1/alerts/{id}` on button click for status updates.

**Key design decision:** Alerts are sorted by risk score, not by time. An operator facing 200 active alerts must triage the most dangerous ones first. Time-sorted alerts would bury a 0.91-risk event behind dozens of 0.1-risk events received more recently.

---

#### Page 05 — XAI Panel (Explainable AI Decision View)

**Operator use case:** Understand *why* the AI model flagged a specific event. Answers: *"What drove this decision, and should I trust it?"*

The XAI Panel is reached by clicking "View XAI" on any AI Alert row. It displays the full SHAP feature attribution for that event. A risk gauge shows the overall risk score. A plain-language explanation box translates the SHAP output into a sentence an operator without ML knowledge can understand (e.g. *"High radar signal loss detected. Primary driver: unusually high radar latency."*). A horizontal SHAP bar chart shows each feature's contribution — positive contributions (increasing risk) in red, negative contributions (reducing risk) in green. A feature detail table lists exact values and SHAP scores. An expert JSON toggle reveals the raw SHAP payload for technical users.

**Data source:** `GET /api/v1/alerts/{id}/xai` on demand, called once when the operator navigates to this page from an alert row. The SHAP values are stored as JSONB in the `xai_explanations` table (produced by Abdalla's Module 8).

**Key design decision:** The XAI Panel deliberately separates plain language from expert data. Operators without ML backgrounds need the natural language explanation; data scientists and engineers need the raw SHAP values. Both are served from the same endpoint — the frontend presents them in appropriate layers.

---

#### Page 06 — Performance Metrics (System Health Time-Series)

**Operator use case:** Track pipeline performance against the prototype bar over time. Answers: *"Are we meeting the performance targets? Which sensor is underperforming?"*

The Performance Metrics page shows four KPI cards — latency p95, data loss, throughput (events/second), and time sync delta — each with a coloured badge indicating whether the prototype bar target is met (OK / WARN / FAIL). Below, four time-series charts visualise these metrics over a selectable time range (15 minutes, 1 hour, 24 hours). A sensor performance table breaks down latency and data loss per sensor type. Threshold bands on the charts show the prototype bar limits visually.

**Data source:** `GET /api/v1/performance` polling every 10 seconds, served from TimescaleDB continuous aggregate views (`perf_1min`, `perf_5min`, `perf_15min`) depending on the selected time range. `GET /api/v1/performance/thresholds` on page load, reading from `config/prototype_bar.yaml`.

**Key design decision:** Performance thresholds are read from a YAML configuration file, not hardcoded in the frontend or backend. This allows Emrah to adjust the prototype bar targets without a code change — critical during the M1 sign-off process.

---

#### Page 07 — Reports (Historical Reporting with Export)

**Operator use case:** Generate and export historical reports for a selected date range and sensor filter. Answers: *"What happened over the past week? Which sensor produced the most anomalies?"*

The Reports page provides date-range and sensor filtering for historical analysis. Four summary cards show total anomaly count, average risk score, average latency p95, and average data loss for the selected period. A daily anomaly trend bar chart shows event distribution over time. A top-10 riskiest events table lists the most dangerous events in the period. A sensor performance summary table aggregates by sensor type. Two export buttons generate a PDF report (server-side via ReportLab) or a CSV data export — both applying the same filters as the on-screen view.

**Data source:** `GET /api/v1/reports` on demand (triggered by filter changes), served partially from the `alerts_daily` continuous aggregate and partially from direct `anomaly_alerts` queries. `GET /api/v1/reports/export?format=pdf|csv` on button click, streamed as a file download.

**Key design decision:** PDF generation is handled server-side by ReportLab, not client-side by jsPDF. Server-side generation is more reliable for complex layouts, supports pagination, and does not depend on the operator's browser rendering the page correctly before capture. The PDF is streamed directly as a response — no temporary file storage required.

---

## 2. Data Model Overview

The DataForge database runs on TimescaleDB (a PostgreSQL extension optimised for time-series workloads). Seven tables store the full pipeline output from raw ingestion through AI explanation.

### 2.1 Tables

| Table | Type | Hypertable | Purpose |
|---|---|---|---|
| `events` | Raw ingestion | ✅ Yes | Every raw event from Kafka (Module 3–5 output) |
| `fused_events` | Fusion output | ✅ Yes | Matched multi-sensor records (Module 6 output) |
| `anomaly_alerts` | AI output | ✅ Yes | Flagged anomaly events (Module 7 output) |
| `xai_explanations` | XAI output | ❌ No | SHAP feature attribution per alert (Module 8 output) |
| `system_performance_metrics` | Pipeline metrics | ✅ Yes | Latency, throughput, data loss snapshots (every 10s) |
| `fusion_status` | Fusion heartbeat | ✅ Yes | Per-sensor quality, contribution weight, data loss |
| `report_snapshots` | Report cache | ❌ No | Cached report results for PDF/CSV export (24h TTL) |

### 2.2 Table Relationships

```
events (raw)
  └─→ fused_events        (event_id — same event, post-fusion)
  └─→ anomaly_alerts      (event_id — same event, AI-flagged)
         └─→ xai_explanations  (event_id — SHAP explanation for this alert)

system_performance_metrics
  └─→ perf_1min / perf_5min / perf_15min  (continuous aggregates)

anomaly_alerts
  └─→ summary_1h    (continuous aggregate — serves Home page)
  └─→ alerts_daily  (continuous aggregate — serves Reports trend chart)

report_snapshots  (standalone cache, no foreign key relationships)
fusion_status     (standalone heartbeat, no foreign key relationships)
```

### 2.3 Write Volume at Prototype Bar

| Table | Write volume | Basis |
|---|---|---|
| `events` | ~600,000 rows/min | ≥10K evt/s prototype bar |
| `fused_events` | ~600,000 rows/min | 1 fused record per raw event |
| `anomaly_alerts` | ~3,000 rows/min | 0.5% anomaly rate assumption |
| `xai_explanations` | ~3,000 rows/min | 1 explanation per alert |
| `system_performance_metrics` | ~24 rows/min | 4 sensors × every 10s |
| `fusion_status` | ~24 rows/min | 4 sensors × every 10s |
| `report_snapshots` | On demand only | Operator-triggered |

### 2.4 Retention Policies

| Table | Retention | Reason |
|---|---|---|
| `events` | 30 days | Raw events are large; continuous aggregates serve long-term queries |
| `fused_events` | 30 days | Same as events |
| `anomaly_alerts` | 90 days | Alerts need longer history for operator review and reporting |
| `xai_explanations` | 90 days | Follows anomaly_alerts retention |
| `system_performance_metrics` | 7 days | Continuous aggregates serve all time-range queries |
| `fusion_status` | 7 days | Real-time and short-term trend only |
| `report_snapshots` | 24 hours | Auto-expire stale cached reports |

### 2.5 Continuous Aggregates

Five pre-computed materialized views serve the most frequent dashboard polling queries without raw table scans:

| View | Source | Bucket | Serves |
|---|---|---|---|
| `summary_1h` | `anomaly_alerts` | 1 hour | Home page `/api/v1/summary` (5s poll) |
| `perf_1min` | `system_performance_metrics` | 1 minute | Performance page (15-min range) |
| `perf_5min` | `perf_1min` (cascading) | 5 minutes | Performance page (1-hour range) |
| `perf_15min` | `perf_5min` (cascading) | 15 minutes | Performance page (24-hour range) |
| `alerts_daily` | `anomaly_alerts` | 1 day | Reports page anomaly trend chart |

The `summary_1h` aggregate reduces a potential 180,000-row scan (1 hour of alerts at 3,000/min) to a single-row lookup. The cascading performance aggregates allow the Performance page to serve 15-minute, 1-hour, and 24-hour views from pre-computed data at all three resolutions.

---

## 3. API Design Philosophy

### 3.1 Framework Choice — FastAPI

FastAPI (Python 3.11+) was chosen over Django REST Framework for three reasons specific to DataForge's requirements:

**Async-first architecture.** The Live Stream and Fusion Monitor pages require persistent WebSocket connections that run concurrently with REST polling. FastAPI is built on ASGI and handles thousands of concurrent WebSocket connections natively. Django REST Framework is WSGI-based and requires additional configuration for async support.

**Native WebSocket support.** FastAPI's WebSocket handling integrates cleanly with the aiokafka async Kafka consumer library. The Kafka→WebSocket bridge runs as a FastAPI background task, consuming the `clean_events` Kafka topic and broadcasting to all connected dashboard clients.

**Automatic OpenAPI documentation.** FastAPI generates interactive API documentation at `/docs` automatically from Pydantic schemas. This is directly usable by Abdalla when integrating his AI model output and by Omer when writing Kafka producers — eliminating the need for a separate API specification document during implementation.

### 3.2 REST Polling vs WebSocket

The API uses two communication patterns, each chosen for specific reasons:

**WebSocket — used for Live Stream and Fusion Monitor status:**

WebSocket maintains a persistent connection between the browser and the FastAPI backend. The backend pushes data to the client as events arrive from Kafka — the frontend never requests data. This is the correct choice when data changes faster than a polling interval could reasonably capture (Live Stream: up to 10,000 events/second) or when the latency of a missed polling cycle would be perceptible to the operator (Fusion Monitor: sensor status changes mid-cycle).

**REST Polling — used for all other pages:**

REST polling sends a standard HTTP GET request at a fixed interval and closes the connection. This is simpler to implement, stateless, fault-tolerant, and appropriate when updates every 5–30 seconds are sufficient. Home page (5s), AI Alerts (5s), Fusion sensor data (10s), Performance metrics (10s), and Reports (on demand) all fall into this category. A missed poll simply retries on the next cycle — no session state to recover.

The decision boundary: if the operator would notice a 5-second delay in the data, use WebSocket. If 5–30 seconds is acceptable, use REST polling.

### 3.3 API Structure

All endpoints follow a consistent structure:

- **Base path:** `/api/v1/` — versioned from day one to allow contract evolution at M2
- **Error format:** RFC 7807 (`{ type, title, status, detail }`) — consistent across all endpoints
- **Authentication:** JWT Bearer stub in M1 (CORS open for `localhost:3000`); activated at M9
- **Pagination:** Offset-limit on list endpoints (alerts, reports); cursor-based pagination as stretch goal for M2
- **Database layer:** Raw asyncpg queries (not ORM) — required for TimescaleDB-specific functions (`create_hypertable`, `time_bucket`, continuous aggregate policies)

### 3.4 Endpoint Summary

The API exposes 18 endpoints: 2 WebSocket and 16 REST.

| Category | Count | Examples |
|---|---|---|
| System summary | 1 | `GET /api/v1/summary` |
| Stream info | 1 | `GET /api/v1/stream/info` |
| Alert management | 5 | `GET /api/v1/alerts`, `PATCH /api/v1/alerts/{id}`, `GET /api/v1/alerts/{id}/xai` |
| Fusion monitoring | 2 | `GET /api/v1/fusion/sensors`, `GET /api/v1/fusion/events` |
| Performance metrics | 2 | `GET /api/v1/performance`, `GET /api/v1/performance/thresholds` |
| Reports & export | 2 | `GET /api/v1/reports`, `GET /api/v1/reports/export` |
| Health checks | 2 | `GET /api/v1/health`, `GET /api/v1/health/upstream` |
| WebSocket | 2 | `WS /api/v1/ws/stream`, `WS /api/v1/ws/fusion` |

Full endpoint specifications with query parameters and response schemas are in `/docs/api/ui_api_requirements_final.docx`.

---

## 4. Key Technical Decisions

### 4.1 TimescaleDB over Plain PostgreSQL

**Decision:** Use TimescaleDB (a PostgreSQL extension) as the time-series database rather than plain PostgreSQL.

**Rationale:** Every dashboard query in DataForge is fundamentally a time-series query — *"what was the latency p95 over the last 15 minutes, grouped by sensor?"*, *"how many anomalies occurred per day this week?"*. In plain PostgreSQL, these queries would require full table scans over hundreds of millions of rows at prototype bar throughput.

TimescaleDB adds three capabilities that directly address this:

*Hypertables* automatically partition the data into time-based chunks. A query for the last 15 minutes only scans the current chunk — not the entire table. This alone reduces query time from seconds to milliseconds for time-bounded queries.

*Continuous aggregates* pre-compute frequently needed aggregations (hourly summaries, per-minute performance metrics, daily anomaly counts) and refresh them incrementally as new data arrives. The Home page `summary_1h` aggregate reduces a potential 180,000-row scan to a single-row lookup.

*Retention policies* automatically drop old data chunks past a configured age, keeping the database size bounded without manual intervention.

**Why not ClickHouse or other column stores?** The DataForge team has PostgreSQL expertise. TimescaleDB extends PostgreSQL — the same SQL dialect, the same asyncpg driver, the same tooling. No new query language, no new operational overhead. ClickHouse would provide better analytical query performance at very large scale, but introduces significant operational complexity that is inappropriate for a 12-month prototype.

### 4.2 FastAPI over Django REST Framework

Covered in Section 3.1. Key reasons: async-first (WebSocket + Kafka bridge), native WebSocket support, automatic OpenAPI docs generation.

### 4.3 ReactJS for the Frontend

**Decision:** Build the dashboard frontend in ReactJS.

**Rationale:** ReactJS is Beyza's primary frontend expertise, ensuring the highest quality implementation during the short M9 window (8 weeks). The react-window library solves the virtual list requirement for Live Stream (200 events in DOM, 1,000+ events/second arriving). The React ecosystem provides well-maintained libraries for all dashboard requirements: charting (Recharts or Chart.js), WebSocket management (native browser API with useEffect hooks), and PDF export triggering (window.open on the export endpoint URL).

### 4.4 JSONB for SHAP Explanation Storage

**Decision:** Store SHAP feature attribution as JSONB in the `xai_explanations` table rather than a normalised relational structure.

**Rationale:** SHAP output is a variable-length array of feature attribution objects — the number of features varies by model version and the feature names are not fixed at schema design time. A normalised structure (one row per feature per event) would require a join across potentially 10+ rows per alert query, adding complexity without benefit. JSONB stores the complete attribution flexibly, supports GIN indexing for feature-level queries, and is natively queryable from PostgreSQL SQL. The `top_features` field (pre-computed top 3 features) is stored separately for fast access by the Home page critical alert banner without parsing the full JSONB payload.

### 4.5 Server-Side PDF Generation (ReportLab)

**Decision:** Generate PDF reports server-side via ReportLab rather than client-side via jsPDF.

**Rationale:** Client-side PDF generation captures the browser's rendered DOM — which is unreliable for complex data tables (pagination differs, fonts may not embed, charts may render at screen resolution). ReportLab generates PDFs programmatically from data, producing consistent output regardless of the operator's browser, screen resolution, or zoom level. The PDF is streamed as a response from `GET /api/v1/reports/export?format=pdf` — no temporary file storage is required on the server.

### 4.6 Wireframe-First, Code-Last Approach

**Decision:** Produce complete wireframes, UI state definitions, data field specifications, and API contracts before writing any ReactJS or FastAPI code.

**Rationale:** M9 (Dashboard, API & Integration) does not begin until December 2026. Producing the full specification now — while the requirements are fresh and the team is aligned on the pipeline design — prevents the common failure mode of discovering UI requirements during implementation. The wireframes (T8), UI states (T9), data field specs (M1W2T9), and API endpoint list (M1W2T10) collectively define exactly what code Beyza needs to write in M9. No design decisions will need to be made under time pressure.

---

## 5. Alignment with Other Milestone 1 Deliverables

This section's work connects directly to deliverables produced by Abdalla and Omer:

| This document's element | Connects to |
|---|---|
| `anomaly_alerts` table schema | Abdalla's Module 7 (AI/ML) output format — `anomaly_label` INT8, `risk_score` FLOAT, `confidence` FLOAT, `model_version` VARCHAR |
| `xai_explanations` JSONB schema | Abdalla's Module 8 (XAI/SHAP) output format — contract to be finalised at M2 |
| `events` table `source_type` field | Omer's Kafka topic structure — ALICE / RADAR / LIDAR / IMU / TEL |
| `system_performance_metrics` table | Omer's Module 5 (Spark) performance publisher — writes every 10s per sensor |
| `fusion_status` table | Omer's Module 6 (Fusion) heartbeat publisher — writes every 10s per sensor |
| API endpoint `/api/v1/alerts/{id}/xai` | Abdalla's SHAP module — response contract to be finalised at M2 Week 6 |
| Prototype bar thresholds in `config/prototype_bar.yaml` | Abdalla's prototype bar document (M1W3T3) — same values used |

**Open items for M2 (requiring cross-team input):**

| Item | Owner | Target |
|---|---|---|
| Confirm `anomaly_label` encoding (0/1 binary or multi-class) | Abdalla | M2 Week 5 |
| Finalise SHAP response contract for `/api/v1/alerts/{id}/xai` | Abdalla + Beyza | M2 Week 6 |
| Confirm ALICE Run 1 field names map to `events` schema | Omer | M2 Week 5 |
| Confirm `raw_payload JSONB` column — keep or drop from `events` | All | M2 Week 5 |

---

## 6. What This Section Feeds in the Roadmap

The M1 dashboard and database design work directly enables the following future milestones:

**Milestone 2 (Data Schema & Model Design — June 2026):** The `db_table_sketches_v2.md` and continuous aggregates research note feed directly into the M2 TimescaleDB ERD. The API endpoint list feeds the M2 API contract finalisation with Abdalla.

**Milestone 9 (Dashboard, API & Integration — Dec 2026–Feb 2027):** The complete wireframe set (7 pages), UI state definitions (empty/loading/error for all 7 pages), data field specifications (112 fields), FastAPI folder structure, and high-fidelity mockups collectively mean that M9 implementation can begin immediately without additional design work. Beyza estimates that the M1 design investment reduces M9 implementation risk by eliminating all architecture and UI design decisions from the critical path.

---

## 7. Summary

Milestone 1 produced a complete, production-ready design specification for the DataForge dashboard and database layer. The specification covers all 7 dashboard pages with wireframes and high-fidelity mockups, 18 API endpoints with full parameter documentation, 7 TimescaleDB tables with schema, indexes, and write volume estimates, 5 continuous aggregate views, and a FastAPI project structure ready for M9 implementation.

All decisions — framework choice, communication pattern, database technology, PDF generation approach — are documented with explicit rationale traceable to DataForge's specific requirements. No design decision was made by default or convention; each was chosen because it best serves the prototype bar targets and the operator's use cases.

This section, together with Abdalla's requirements document and Omer's infrastructure specification, forms the complete Milestone 1 technical record for Emrah's review.

---

*Prepared by Beyza Ülkümen — Full-Stack Developer, DataForge Module 9.*  
*Milestone 1 · May 2026 · Dataseed Yazılım Elektronik.*
