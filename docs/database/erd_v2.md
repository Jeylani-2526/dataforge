# DataForge — TimescaleDB ERD v2

## ERD Diagram (Mermaid)

```mermaid
erDiagram

    events {
        TIMESTAMPTZ time PK "Hypertable partition col"
        uuid event_id
        VARCHAR20 source_type
        INTEGER run_number "NULL for sensor events"
        BIGINT timestamp_ms
        BIGINT ingestion_ts_ms
        INTEGER track_count "NULL for sensor events"
        REAL net_momentum_x "NULL until M3 ROOT Docker"
        REAL net_momentum_y "NULL until M3 ROOT Docker"
        REAL net_momentum_z "NULL until M3 ROOT Docker"
        REAL max_energy_gev "NULL until M3 ROOT Docker"
        REAL total_energy_gev "NULL until M3 ROOT Docker"
        FLOAT latency_ms "Pipeline-written Module 3"
        FLOAT data_loss_pct "Pipeline-written Module 5"
        VARCHAR20 quality_flag "Pipeline-written Module 5"
        INT8 anomaly_label "NULL until M7"
        FLOAT risk_score "NULL until M7"
        JSONB raw_payload "Optional — M2 decision"
    }

    fused_events {
        TIMESTAMPTZ time PK "Hypertable partition col"
        uuid fused_event_id PK
        uuid alice_event_id FK
        uuid sensor_event_id FK
        VARCHAR20 sensor_type
        INT fusion_window_ms "default 500"
        FLOAT latency_ms "Pipeline-written Module 5"
        FLOAT data_loss_pct "Pipeline-written Module 3"
        BIGINT timestamp_ms
        INT8 anomaly_label "NULL until M7"
        FLOAT risk_score "NULL until M7"
        FLOAT confidence "NULL until M7"
    }

    anomaly_alerts {
        TIMESTAMPTZ time PK "Hypertable partition col"
        uuid fused_event_id FK
        VARCHAR20 source_type
        INT8 anomaly_label
        FLOAT risk_score
        FLOAT confidence
        VARCHAR20 model_version
        VARCHAR20 status
        TIMESTAMPTZ status_updated_at
        TEXT explanation_summary
    }

    xai_explanations {
        uuid fused_event_id PK FK
        TIMESTAMPTZ time
        TEXT explanation_text
        JSONB shap_values
        JSONB top_features
        VARCHAR20 model_version
        TIMESTAMPTZ generated_at
    }

    system_performance_metrics {
        TIMESTAMPTZ time PK "Hypertable partition col"
        VARCHAR20 source_type
        FLOAT latency_p95_ms
        FLOAT latency_p50_ms
        INT throughput_evts
        FLOAT data_loss_pct
        FLOAT time_sync_delta_ms
        INT active_sensors
    }

    fusion_status {
        TIMESTAMPTZ time PK "Hypertable partition col"
        VARCHAR20 source_type
        INT quality_score
        FLOAT contribution_weight
        FLOAT data_loss
        FLOAT latency
        VARCHAR20 status
    }

    report_snapshots {
        uuid snapshot_id PK
        TIMESTAMPTZ created_at
        VARCHAR64 filter_hash
        TIMESTAMPTZ date_from
        TIMESTAMPTZ date_to
        VARCHAR20 source_type_filter
        FLOAT min_risk_filter
        JSONB summary_json
        JSONB top_events_json
        JSONB sensor_perf_json
        JSONB anomaly_trend_json
        TIMESTAMPTZ expires_at
    }

    events ||--o{ fused_events : "alice_event_id"
    events ||--o{ fused_events : "sensor_event_id"
    fused_events ||--o{ anomaly_alerts : "fused_event_id"
    fused_events ||--o| xai_explanations : "fused_event_id"
```

---

## Hypertable Summary

| Table | HT? | Partition Col | Chunk | Retention |
|---|---|---|---|---|
| `events` | ✅ **(HT)** | `time` | 1 day | 30 days |
| `fused_events` | ✅ **(HT)** | `time` | 1 day | 30 days |
| `anomaly_alerts` | ✅ **(HT)** | `time` | 1 day | 90 days |
| `xai_explanations` | ❌ | — | — | 90 days |
| `system_performance_metrics` | ✅ **(HT)** | `time` | 1 hour | 7 days |
| `fusion_status` | ✅ **(HT)** | `time` | 1 hour | 7 days |
| `report_snapshots` | ❌ | — | — | 24 hours |

> **Design note:** `fused_events` references two rows in `events` — one ALICE record (`alice_event_id`) and one sensor record (`sensor_event_id`). Both FK columns point to `events.event_id` (uuid). This replaces the v1 single `event_id` FK and eliminates the `source_types[]` workaround.

---

## Column Definitions

### `events` (HT)

| Column | Type | Null | Notes |
|---|---|---|---|
| `time` | TIMESTAMPTZ | NOT NULL | Hypertable partition column |
| `event_id` | uuid | NOT NULL | UUID v4, system-assigned at ingestion |
| `source_type` | VARCHAR(20) | NOT NULL | alice / radar / lidar / telemetry |
| `run_number` | INTEGER | NULL | ALICE only; NULL for sensor records |
| `timestamp_ms` | BIGINT | NOT NULL | Source timestamp ms |
| `ingestion_ts_ms` | BIGINT | NOT NULL | Module 3 ingestion timestamp ms |
| `track_count` | INTEGER | NULL | ALICE only |
| `net_momentum_x` | REAL | NULL | ALICE only — filled M3 ROOT Docker |
| `net_momentum_y` | REAL | NULL | ALICE only — filled M3 ROOT Docker |
| `net_momentum_z` | REAL | NULL | ALICE only — filled M3 ROOT Docker |
| `max_energy_gev` | REAL | NULL | ALICE only — filled M3 ROOT Docker |
| `total_energy_gev` | REAL | NULL | ALICE only — filled M3 ROOT Docker |
| `latency_ms` | FLOAT | NOT NULL | Pipeline-written by Module 3 |
| `data_loss_pct` | FLOAT | NOT NULL | Pipeline-written by Module 5 |
| `quality_flag` | VARCHAR(20) | NULL | Pipeline-written by Module 5; clean / incomplete / dropout |
| `anomaly_label` | INT8 | NULL | NULL until M7 |
| `risk_score` | FLOAT | NULL | NULL until M7 |
| `raw_payload` | JSONB | NULL | Optional — open question Q2 |

---

### `fused_events` (HT)

| Column | Type | Null | Notes |
|---|---|---|---|
| `time` | TIMESTAMPTZ | NOT NULL | Hypertable partition column |
| `fused_event_id` | uuid | NOT NULL | PK — UUID v4, system-assigned by Module 6 |
| `alice_event_id` | uuid | NOT NULL | FK → events.event_id (ALICE record) |
| `sensor_event_id` | uuid | NOT NULL | FK → events.event_id (sensor record) |
| `sensor_type` | VARCHAR(20) | NOT NULL | Carried from sensor record: radar / lidar / telemetry |
| `fusion_window_ms` | INT | NOT NULL | Default 500 — join window used by Module 6 |
| `timestamp_ms` | BIGINT | NOT NULL | Fusion timestamp ms, assigned by Module 6 |
| `latency_ms` | FLOAT | NOT NULL | Pipeline-written by Module 5 |
| `data_loss_pct` | FLOAT | NOT NULL | Pipeline-written by Module 3 |
| `anomaly_label` | INT8 | NULL | NULL until M7 |
| `risk_score` | FLOAT | NULL | NULL until M7 |
| `confidence` | FLOAT | NULL | NULL until M7 |

---

### `anomaly_alerts` (HT)

| Column | Type | Null | Notes |
|---|---|---|---|
| `time` | TIMESTAMPTZ | NOT NULL | Hypertable partition column |
| `fused_event_id` | uuid | NOT NULL | FK → fused_events.fused_event_id |
| `source_type` | VARCHAR(20) | NOT NULL | Denormalized from fused_events for query perf |
| `anomaly_label` | INT8 | NOT NULL | Always 1 in this table |
| `risk_score` | FLOAT | NOT NULL | 0.0–1.0 |
| `confidence` | FLOAT | NOT NULL | 0.0–1.0 |
| `model_version` | VARCHAR(20) | NOT NULL | e.g. v0.1.0-M7 |
| `status` | VARCHAR(20) | NOT NULL | active / reviewed / closed |
| `status_updated_at` | TIMESTAMPTZ | NULL | Set on PATCH |
| `explanation_summary` | TEXT | NULL | From Module 8 |

---

### `xai_explanations`

| Column | Type | Null | Notes |
|---|---|---|---|
| `fused_event_id` | uuid | NOT NULL | PK + FK → fused_events.fused_event_id |
| `time` | TIMESTAMPTZ | NOT NULL | Denormalized for retention policy |
| `explanation_text` | TEXT | NOT NULL | Plain-language explanation |
| `shap_values` | JSONB | NOT NULL | [{feature, shap_value, direction}] |
| `top_features` | JSONB | NOT NULL | Top 3 precomputed |
| `model_version` | VARCHAR(20) | NOT NULL | |
| `generated_at` | TIMESTAMPTZ | NOT NULL | |

---

### `system_performance_metrics` (HT)

| Column | Type | Null | Notes |
|---|---|---|---|
| `time` | TIMESTAMPTZ | NOT NULL | Hypertable partition column |
| `source_type` | VARCHAR(20) | NOT NULL | |
| `latency_p95_ms` | FLOAT | NOT NULL | Threshold ≤500ms |
| `latency_p50_ms` | FLOAT | NOT NULL | |
| `throughput_evts` | INT | NOT NULL | Events in 10s window |
| `data_loss_pct` | FLOAT | NOT NULL | Threshold ≤1% |
| `time_sync_delta_ms` | FLOAT | NOT NULL | Threshold ±1ms |
| `active_sensors` | INT | NOT NULL | |

---

### `fusion_status` (HT)

| Column | Type | Null | Notes |
|---|---|---|---|
| `time` | TIMESTAMPTZ | NOT NULL | Hypertable partition column |
| `source_type` | VARCHAR(20) | NOT NULL | |
| `quality_score` | INT | NOT NULL | 0–100 |
| `contribution_weight` | FLOAT | NOT NULL | 0.0–1.0 |
| `data_loss` | FLOAT | NOT NULL | Alert if >1% |
| `latency` | FLOAT | NOT NULL | |
| `status` | VARCHAR(20) | NOT NULL | online / degraded / offline |

---

### `report_snapshots`

| Column | Type | Null | Notes |
|---|---|---|---|
| `snapshot_id` | uuid | NOT NULL | PK |
| `created_at` | TIMESTAMPTZ | NOT NULL | |
| `filter_hash` | VARCHAR(64) | NOT NULL | SHA256 of filter params |
| `date_from` | TIMESTAMPTZ | NOT NULL | |
| `date_to` | TIMESTAMPTZ | NOT NULL | |
| `source_type_filter` | VARCHAR(20) | NULL | |
| `min_risk_filter` | FLOAT | NOT NULL | Default 0.0 |
| `summary_json` | JSONB | NOT NULL | |
| `top_events_json` | JSONB | NOT NULL | |
| `sensor_perf_json` | JSONB | NOT NULL | |
| `anomaly_trend_json` | JSONB | NOT NULL | |
| `expires_at` | TIMESTAMPTZ | NOT NULL | created_at + 24h |

---

## Composite Indexes

```sql
-- fused_events: dashboard queries filter by time + anomaly status
CREATE INDEX idx_fused_time_label
    ON fused_events (timestamp_ms, anomaly_label);

-- anomaly_alerts: AI Alerts page sorts by risk DESC within fused event
CREATE INDEX idx_alerts_fused_risk
    ON anomaly_alerts (fused_event_id, risk_score DESC);
```

---

## Continuous Aggregate Definitions

### `perf_1min` — over `events` (HT)

```sql
CREATE MATERIALIZED VIEW perf_1min
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 minute', time)                                        AS bucket,
    source_type,
    COUNT(*)                                                             AS event_count,
    percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms)            AS latency_p95,
    AVG(data_loss_pct)                                                   AS avg_data_loss
FROM events
GROUP BY bucket, source_type;

SELECT add_continuous_aggregate_policy('perf_1min',
    start_offset      => INTERVAL '10 minutes',
    end_offset        => INTERVAL '1 minute',
    schedule_interval => INTERVAL '1 minute');
```

**Serves:** `GET /api/v1/performance` — throughput + per-event latency fields

---

### `pipeline_health_1min` — over `system_performance_metrics` (HT)

```sql
CREATE MATERIALIZED VIEW pipeline_health_1min
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 minute', time)                                        AS bucket,
    source_type,
    AVG(time_sync_delta_ms)                                              AS avg_time_sync,
    AVG(data_loss_pct)                                                   AS avg_data_loss,
    AVG(latency_p95_ms)                                                  AS avg_pipeline_latency,
    MAX(latency_p95_ms)                                                  AS max_pipeline_latency
FROM system_performance_metrics
GROUP BY bucket, source_type;

SELECT add_continuous_aggregate_policy('pipeline_health_1min',
    start_offset      => INTERVAL '10 minutes',
    end_offset        => INTERVAL '1 minute',
    schedule_interval => INTERVAL '1 minute');
```

**Serves:** `GET /api/v1/performance` — time sync + data loss + pipeline latency fields

---

### `summary_5min` — over `fused_events` (HT)

```sql
CREATE MATERIALIZED VIEW summary_5min
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('5 minutes', time)                                       AS bucket,
    COUNT(*)                                                             AS total_fused_events,
    COUNT(*) FILTER (WHERE anomaly_label = 1)                           AS anomaly_count,
    AVG(risk_score) FILTER (WHERE risk_score IS NOT NULL)               AS avg_risk_score,
    MAX(risk_score)                                                      AS max_risk_score
FROM fused_events
GROUP BY bucket;

SELECT add_continuous_aggregate_policy('summary_5min',
    start_offset      => INTERVAL '15 minutes',
    end_offset        => INTERVAL '30 seconds',
    schedule_interval => INTERVAL '30 seconds');
```

**Serves:** `GET /api/v1/summary` — Home summary cards  
**Refresh:** 30 seconds — frontend must poll at ≥30s intervals

---

## CAGG Summary

| View | Source Table | Bucket | Refresh | Serves |
|---|---|---|---|---|
| `perf_1min` | `events` | 1 min | 1 min | `/api/v1/performance` — throughput + latency |
| `pipeline_health_1min` | `system_performance_metrics` | 1 min | 1 min | `/api/v1/performance` — time sync + data loss |
| `summary_5min` | `fused_events` | 5 min | **30s** | `/api/v1/summary` — Home cards |

> ⚠️ `perf_1min` uses `percentile_cont` — requires **timescaledb-toolkit** (Omer, M2W6T9)

---

## FK Relationships

| FK Column | Table | References | Type |
|---|---|---|---|
| `fused_events.alice_event_id` | `fused_events` | `events.event_id` | uuid |
| `fused_events.sensor_event_id` | `fused_events` | `events.event_id` | uuid |
| `anomaly_alerts.fused_event_id` | `anomaly_alerts` | `fused_events.fused_event_id` | uuid |
| `xai_explanations.fused_event_id` | `xai_explanations` | `fused_events.fused_event_id` | uuid |

---

## Cross-Check — Abdalla Schema Alignment

| ERD v2 Column | Abdalla Schema Field | Match? |
|---|---|---|
| `fused_events.fused_event_id` | `fused_event_schema_v0.fused_event_id` (string UUID v4) | ✅ |
| `fused_events.alice_event_id` | `fused_event_schema_v0.alice_event_id` (string UUID v4) | ✅ |
| `fused_events.sensor_event_id` | `fused_event_schema_v0.sensor_event_id` (string UUID v4) | ✅ |
| `anomaly_alerts.fused_event_id` | FK to `fused_event_id` confirmed | ✅ |
| `xai_explanations.fused_event_id` | FK to `fused_event_id` confirmed | ✅ |
