# DataForge — Data Flow Specification (Per Module)


---

## Purpose

For each of the 10 DataForge modules, this document specifies: (1) input schema — field names, types, and format; (2) output schema; and (3) latency and throughput expectations under prototype conditions. This document is the direct input to the Week 3 Requirements Document finalization and the M2 schema design.

---

## Prototype Performance Context

All latency and throughput figures below reference the **Prototype Performance Bar**, not industrial targets. The system runs on team laptops via Docker Compose (single-broker Kafka, no hardware PTP).

| Metric | Prototype Bar |
|---|---|
| End-to-end p95 latency | ≤ 500 ms |
| Data loss | ≤ 1% |
| Throughput | ≥ 10K events/sec |
| Time sync accuracy | ±1 ms (software timestamp) |
| AI model AUC | ≥ 0.85 |
| False positive rate | ≤ 5% |

---

## Module 1 — ALICE Data Source

**Type:** Source | **Owner:** Beyza | **Implementation:** M3

### Input
| Field | Type | Format | Description |
|---|---|---|---|
| (none — external portal) | — | HTTP download | CERN Open Data Portal Run 3 dataset |

### Output Schema (ROOT → Parquet conversion)
| Field | Type | Format | Description |
|---|---|---|---|
| `event_id` | `string` | UUID / ALICE ID | Unique identifier per particle collision event |
| `timestamp_ms` | `int64` | Unix ms | Software-assigned ingestion timestamp |
| `position_x` | `float32` | metres | X position of reconstructed track vertex |
| `position_y` | `float32` | metres | Y position |
| `position_z` | `float32` | metres | Z position |
| `momentum_x` | `float32` | GeV/c | Track momentum X component |
| `momentum_y` | `float32` | GeV/c | Track momentum Y component |
| `momentum_z` | `float32` | GeV/c | Track momentum Z component |
| `energy_gev` | `float32` | GeV | Cluster energy (calorimeter) |
| `source_type` | `string` | enum | Fixed value: `"alice"` |

**Output format:** Parquet files on disk (`/data/alice/raw/`) + optional ROOT native  
**Interface:** File (batch read by Module 3)  
**Throughput expectation:** Batch ingest of a manageable Run 3 subset (~1–5 GB); not a real-time stream  
**Latency:** N/A (batch, not streaming)

---

## Module 2 — Sensor Data Source (synthetic)

**Type:** Source | **Owner:** Omer | **Implementation:** M3

### Input
| Field | Type | Format | Description |
|---|---|---|---|
| `config.rate_hz` | `int` | Config file | Target event emission rate (e.g. 1000 Hz per sensor) |
| `config.sensor_type` | `string` | Config file | `"radar"` / `"lidar"` / `"telemetry"` |
| `config.noise_level` | `float` | Config file | Gaussian noise sigma for synthetic variation |

### Output Schema (JSON stream → Parquet)
| Field | Type | Format | Description |
|---|---|---|---|
| `sensor_id` | `string` | UUID | Unique identifier for the sensor instance |
| `sensor_type` | `string` | enum | `"radar"` / `"lidar"` / `"telemetry"` |
| `timestamp_ms` | `int64` | Unix ms | Python `time.time_ns()` converted to ms |
| `value_primary` | `float32` | unit varies | Main reading (e.g. radar: range in metres; LIDAR: point distance; telemetry: voltage) |
| `value_secondary` | `float32` | unit varies | Secondary reading (e.g. bearing, intensity, current) |
| `status` | `string` | enum | `"nominal"` / `"noisy"` / `"dropout"` |
| `source_type` | `string` | enum | Fixed value: `"sensor"` |

**Output format:** JSON lines streamed to Parquet files (`/data/sensor/raw/`) at batch intervals  
**Interface:** File (read by Module 3)  
**Throughput expectation:** ~1K–5K events/sec per sensor type; 3 types active simultaneously  
**Latency:** N/A (synthetic generation, configurable rate)

---

## Module 3 — Data Adaptation Layer

**Type:** Pipeline | **Owner:** Abdullah + Omer | **Implementation:** M4

### Input
- Module 1 Parquet files (ALICE events) from `/data/alice/raw/`
- Module 2 Parquet files (Sensor events) from `/data/sensor/raw/`

Input fields: refer to Module 1 and Module 2 output schemas above.

### Output Schema (Avro — streaming; Parquet — storage)

**Unified Avro schema** (common schema for all source types):

| Field | Type | Format | Description |
|---|---|---|---|
| `event_id` | `string` | UUID | Passed through from source |
| `source_type` | `string` | enum | `"alice"` / `"radar"` / `"lidar"` / `"telemetry"` |
| `timestamp_ms` | `int64` | Unix ms | Original source timestamp |
| `ingestion_ts_ms` | `int64` | Unix ms | Timestamp at adaptation layer ingestion |
| `energy_gev` | `float32` | GeV | From ALICE; `null` for sensor events |
| `momentum_x` | `float32` | GeV/c | From ALICE; `null` for sensor events |
| `momentum_y` | `float32` | GeV/c | From ALICE; `null` for sensor events |
| `momentum_z` | `float32` | GeV/c | From ALICE; `null` for sensor events |
| `sensor_id` | `string` | UUID | From sensor; `null` for ALICE events |
| `sensor_value_primary` | `float32` | unit varies | From sensor; `null` for ALICE events |
| `sensor_value_secondary` | `float32` | unit varies | From sensor; `null` for ALICE events |
| `schema_version` | `string` | semver | e.g. `"1.0.0"` — supports backward-compatible evolution |

**Output format:**  
- Avro-serialized records → pushed to Kafka topics `alice_events` and `sensor_events`  
- Parquet files → `/data/adapted/` (storage sink for later batch analysis)

**Interface:** File in → Kafka topic out  
**Throughput expectation:** Must sustain ≥ 10K events/sec combined  
**Latency budget:** ≤ 50ms transformation overhead per event batch

---

## Module 4 — Streaming Layer (Kafka)

**Type:** Pipeline | **Owner:** Omer | **Implementation:** M5

### Input
| Kafka Topic | Source | Message Format | Description |
|---|---|---|---|
| `alice_events` | Module 3 | Avro | ALICE-adapted event records |
| `sensor_events` | Module 3 | Avro | Sensor-adapted event records |

### Output (Kafka topics, partitioned)
| Kafka Topic | Consumer | Message Format | Description |
|---|---|---|---|
| `alice_events` | Module 5 | Avro | Partitioned by `source_type`; same schema as input |
| `sensor_events` | Module 5 | Avro | Partitioned by `sensor_type` |

**Interface:** Kafka topic (producer → consumer)  
**Throughput expectation:** Single-broker Docker setup; target ≥ 10K events/sec sustained  
**Latency budget:** ≤ 20ms broker round-trip at prototype scale  
**Durability:** `replication.factor=1` (prototype); `retention.ms=3600000` (1 hour)  
**Key design:** Events keyed by `event_id` to ensure ordering per event within a partition

---

## Module 5 — Cleaning & Synchronization

**Type:** Pipeline | **Owner:** Beyza + Omer | **Implementation:** M5

### Input
- Kafka topics: `alice_events`, `sensor_events` (Avro, from Module 4)

### Cleaning Rules Applied
| Rule | Action | Field(s) |
|---|---|---|
| Null `event_id` | Drop record | `event_id` |
| `timestamp_ms` in future by > 5s | Drop record | `timestamp_ms` |
| Duplicate `event_id` within 10s window | Drop duplicate | `event_id` |
| Null energy/momentum for ALICE events | Flag as `"incomplete"`, retain | `energy_gev`, `momentum_*` |
| Sensor `status = "dropout"` | Drop record | `status` |

### Synchronization
- **Method:** Software timestamp-based alignment using PySpark watermark windows
- **Watermark delay tolerance:** 2 seconds (events arriving > 2s late are dropped)
- **Accuracy target:** ±1 ms synchronization between ALICE and sensor timestamps

### Output Schema (adds cleaning metadata)
All fields from Module 3 output schema, plus:

| Field | Type | Format | Description |
|---|---|---|---|
| `quality_flag` | `string` | enum | `"clean"` / `"incomplete"` |
| `cleaned_ts_ms` | `int64` | Unix ms | Timestamp at cleaning/sync stage |

**Output Kafka topic:** `clean_events`  
**Interface:** Kafka topic  
**Throughput expectation:** ≥ 10K events/sec (assuming ≤ 5% drop rate from cleaning)  
**Latency budget:** ≤ 100ms processing window for watermark alignment

---

## Module 6 — Data Fusion Layer

**Type:** Pipeline | **Owner:** Abdullah + Omer | **Implementation:** M6

### Input
- Kafka topic: `clean_events` (Avro, from Module 5)

### Fusion Logic
- **Type:** PySpark stream-stream join on a configurable time window
- **Join key:** `timestamp_ms` window (±500ms default); secondary key: spatial proximity for radar/LIDAR
- **Window size:** 2-second tumbling window (configurable)
- **Match condition:** One ALICE event matched to one or more sensor events within the time window

### Output Schema (fused event record)
| Field | Type | Format | Description |
|---|---|---|---|
| `fused_event_id` | `string` | UUID | New ID for the fused record |
| `alice_event_id` | `string` | UUID | Source ALICE event ID |
| `sensor_event_ids` | `array<string>` | JSON array | IDs of matched sensor events |
| `timestamp_ms` | `int64` | Unix ms | Earliest timestamp in the fused set |
| `fusion_window_ms` | `int64` | Unix ms | Time span of events in the fused set |
| `energy_gev` | `float32` | GeV | From ALICE event |
| `momentum_x/y/z` | `float32` | GeV/c | From ALICE event |
| `sensor_readings` | `array<object>` | JSON array | All matched sensor readings (type, value_primary, value_secondary) |
| `fusion_quality` | `string` | enum | `"full"` / `"partial"` (partial = no ALICE match found) |
| `schema_version` | `string` | semver | e.g. `"1.0.0"` |

**Output destinations:**  
- Kafka topic: `fused_events`  
- Parquet sink: `/data/fused/` (for ML training and batch analysis)

**Interface:** Kafka topic + File  
**Throughput expectation:** ≥ 10K fused records/sec (after fusion reduction)  
**Latency budget:** ≤ 150ms fusion window processing overhead

---

## Module 7 — AI/ML Anomaly Detection

**Type:** Intelligence | **Owner:** Abdullah | **Implementation:** M7

### Input
- Kafka topic: `fused_events` (Avro, from Module 6)

### Feature Engineering (applied at inference time)
| Feature | Derived From | Type | Description |
|---|---|---|---|
| `energy_gev` | Module 6 output | `float32` | Direct passthrough |
| `momentum_magnitude` | `sqrt(x²+y²+z²)` | `float32` | Computed from momentum components |
| `sensor_spread` | std(sensor readings) | `float32` | Statistical spread of matched sensor values |
| `fusion_quality_encoded` | `full=1 / partial=0` | `int8` | Encoded quality flag |
| `time_since_last_event_ms` | Rolling | `float32` | Inter-arrival time |
| `event_rate_10s` | Rolling count | `float32` | Events per second in last 10s window |

### Output Schema
All fields from Module 6 output, plus:

| Field | Type | Format | Description |
|---|---|---|---|
| `anomaly_label` | `int8` | 0/1 | `1` = anomalous, `0` = nominal |
| `risk_score` | `float32` | 0.0–1.0 | Model confidence that event is anomalous |
| `confidence` | `float32` | 0.0–1.0 | Model certainty in its prediction |
| `model_version` | `string` | semver | e.g. `"1.0.0"` (Isolation Forest baseline) |

**Output Kafka topic:** `anomaly_events`  
**Interface:** Kafka topic  
**Performance targets:** AUC ≥ 0.85 | FPR ≤ 5%  
**Latency budget:** ≤ 100ms model inference per event  
**Model:** Isolation Forest (scikit-learn) as baseline; PyTorch deep model as stretch goal

---

## Module 8 — Explainable AI (XAI)

**Type:** Intelligence | **Owner:** Abdullah | **Implementation:** M8

### Input
- Kafka topic: `anomaly_events` (from Module 7)
- Input includes all Module 7 fields + feature values used for prediction

### SHAP Processing
- **Method:** SHAP TreeExplainer (for Isolation Forest) or DeepExplainer (for PyTorch)
- **Output:** SHAP values per feature for each anomalous event
- **Template:** Cause-effect chain — top 3 contributing features rendered as human-readable text

### Output Schema
All fields from Module 7 output, plus:

| Field | Type | Format | Description |
|---|---|---|---|
| `shap_values` | `object` | JSON | Dict of {feature_name: shap_value} for top features |
| `top_features` | `array<string>` | JSON array | Top 3 feature names by |SHAP value| |
| `explanation_text` | `string` | Natural language | e.g. "High energy (3.2 GeV) with abnormal sensor spread flagged this event" |
| `xai_version` | `string` | semver | e.g. `"1.0.0"` |

**Output destinations:**  
- TimescaleDB table: `xai_explanations` (written by Module 8 or Module 9 API)  
- HTTP endpoint: served via Module 9 FastAPI

**Interface:** HTTP + TimescaleDB SQL  
**Latency budget:** ≤ 200ms SHAP computation per event (offline SHAP acceptable for prototype)

---

## Module 9 — Dashboard & API

**Type:** Delivery | **Owner:** Beyza | **Implementation:** M9

### Input
| Source | Interface | Data |
|---|---|---|
| TimescaleDB `fused_events` table | SQL | Live and historical fused records |
| TimescaleDB `anomaly_alerts` table | SQL | Anomaly events with risk scores |
| TimescaleDB `xai_explanations` table | SQL | SHAP explanations per alert |
| TimescaleDB `system_performance_metrics` table | SQL | Latency, throughput, data loss metrics |

### Output (FastAPI endpoints → ReactJS dashboard)
| Dashboard Page | Key Metrics Served | Refresh |
|---|---|---|
| Home | System status, events today, active alerts, event throughput | 5s poll |
| Live Stream | Real-time event table (event_id, source, timestamp, status) | WebSocket / real-time |
| Fusion Monitor | Fused event counts, fusion quality ratio, timeline chart | 10s poll |
| AI Alerts | Alert list (risk_score, anomaly_label, timestamp) | 5s poll |
| XAI Panel | SHAP explanation_text, top_features, shap_values chart | On-demand |
| Performance | p95 latency, throughput, data loss, AUC, FPR | 30s poll |
| Reports | Downloadable performance test report (PDF/CSV) | On-demand |

**Interface:** HTTP (JSON endpoints) + TimescaleDB SQL (internal)  
**Latency budget:** API response ≤ 200ms for all endpoints; dashboard load ≤ 1s

---

## Module 10 — Testing & Validation

**Type:** Validation (cross-cutting) | **Owner:** Beyza + Abdullah | **Implementation:** M10

### Input
All pipeline outputs — every module's output is a test input for Module 10.

### Test Types and Coverage
| Test Type | Tool | What It Validates |
|---|---|---|
| Unit tests | pytest | Individual module logic (cleaning rules, schema conversion, SHAP output format) |
| Integration tests | pytest + Docker | End-to-end: M1→M9 pipeline produces valid output |
| Load tests | Custom load generator | ≥ 10K events/sec throughput under sustained load |
| Latency tests | Kafka consumer timestamp delta | p95 end-to-end latency ≤ 500ms |
| Data loss tests | Event count reconciliation | Lost events ≤ 1% under normal conditions |
| AI/ML evaluation | scikit-learn `roc_auc_score` | AUC ≥ 0.85, FPR ≤ 5% on held-out test set |

### Output
- Performance test report (PDF): measurements against Prototype Performance Bar
- pytest HTML report: test coverage and pass/fail per module

**Interface:** Cross-cutting — reads from all module outputs  
**Throughput expectation:** Tests run against the full pipeline; load test duration ≥ 5 minutes sustained

---

