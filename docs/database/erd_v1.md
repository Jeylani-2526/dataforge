# DataForge — TimescaleDB ERD v1

## ERD Diagram (Mermaid)

```mermaid
erDiagram

    events {
        TIMESTAMPTZ time PK "Hypertable partition col"
        UUID event_id
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
        FLOAT latency_ms
        FLOAT data_loss_pct
        INT8 anomaly_label "NULL until M7"
        FLOAT risk_score "NULL until M7"
        JSONB raw_payload "Optional"
    }

    fused_events {
        TIMESTAMPTZ time PK "Hypertable partition col"
        UUID fused_event_id
        UUID event_id FK
        TEXT_ARRAY source_types
        INT fusion_quality
        FLOAT latency_ms
        FLOAT data_loss_pct
        FLOAT time_delta_ms
        INT8 anomaly_label "NULL until M7"
        FLOAT risk_score "NULL until M7"
        FLOAT confidence "NULL until M7"
    }

    anomaly_alerts {
        TIMESTAMPTZ time PK "Hypertable partition col"
        UUID fused_event_id FK
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
        UUID event_id PK FK
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
        UUID snapshot_id PK
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

    events ||--o{ fused_events : "event_id"
    fused_events ||--o{ anomaly_alerts : "fused_event_id"
    anomaly_alerts ||--o| xai_explanations : "event_id"
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

> **Known design limitation — `fused_events` source tracking:** fused_events.event_id links to the ALICE source record in events. Contributing sensor records are identified by source_types[] but are not individually FK-linked. This is a prototype-scale simplification — full per-source FK tracking would require a fused_event_sources junction table, which is out of scope for the prototype.

---

## Column Definitions

### `events` (HT)

| Column | Type | Null | Notes |
|---|---|---|---|
| `time` | TIMESTAMPTZ | NOT NULL | Hypertable partition column |
| `event_id` | UUID | NOT NULL | UUID v4, system-assigned at ingestion for all source types |
| `source_type` | VARCHAR(20) | NOT NULL | alice / radar / lidar / telemetry |
| `run_number` | INTEGER | NULL | ALICE only; NULL for all sensor records |
| `timestamp_ms` | BIGINT | NOT NULL | Source timestamp ms |
| `ingestion_ts_ms` | BIGINT | NOT NULL | Module 3 ingestion timestamp ms |
| `track_count` | INTEGER | NULL | ALICE only |
| `net_momentum_x` | REAL | NULL | ALICE only — M3 ROOT Docker |
| `net_momentum_y` | REAL | NULL | ALICE only — M3 ROOT Docker |
| `net_momentum_z` | REAL | NULL | ALICE only — M3 ROOT Docker |
| `max_energy_gev` | REAL | NULL | ALICE only — M3 ROOT Docker |
| `total_energy_gev` | REAL | NULL | ALICE only — M3 ROOT Docker |
| `latency_ms` | FLOAT | NOT NULL | Pipeline latency ms |
| `data_loss_pct` | FLOAT | NOT NULL | Watermark drop rate % |
| `anomaly_label` | INT8 | NULL | NULL until M7 |
| `risk_score` | FLOAT | NULL | NULL until M7 |
| `raw_payload` | JSONB | NULL | Open question Q2 |

### `fused_events` (HT)

| Column | Type | Null | Notes |
|---|---|---|---|
| `time` | TIMESTAMPTZ | NOT NULL | Hypertable partition column |
| `fused_event_id` | UUID | NOT NULL | |
| `event_id` | UUID | NOT NULL | FK → events.event_id |
| `source_types` | TEXT[] | NOT NULL | e.g. ['alice', 'radar'] |
| `fusion_quality` | INT | NOT NULL | 0–100 |
| `latency_ms` | FLOAT | NOT NULL | |
| `data_loss_pct` | FLOAT | NOT NULL | |
| `time_delta_ms` | FLOAT | NOT NULL | Timestamp alignment delta |
| `anomaly_label` | INT8 | NULL | NULL until M7 |
| `risk_score` | FLOAT | NULL | NULL until M7 |
| `confidence` | FLOAT | NULL | NULL until M7 |

### `anomaly_alerts` (HT)

| Column | Type | Null | Notes |
|---|---|---|---|
| `time` | TIMESTAMPTZ | NOT NULL | Hypertable partition column |
| `fused_event_id` | UUID | NOT NULL | FK → fused_events.fused_event_id |
| `source_type` | VARCHAR(20) | NOT NULL | Denormalized for query perf |
| `anomaly_label` | INT8 | NOT NULL | Always 1 |
| `risk_score` | FLOAT | NOT NULL | 0.0–1.0 |
| `confidence` | FLOAT | NOT NULL | 0.0–1.0 |
| `model_version` | VARCHAR(20) | NOT NULL | |
| `status` | VARCHAR(20) | NOT NULL | active / reviewed / closed |
| `status_updated_at` | TIMESTAMPTZ | NULL | Set on PATCH |
| `explanation_summary` | TEXT | NULL | From Module 8 |

### `xai_explanations`

| Column | Type | Null | Notes |
|---|---|---|---|
| `event_id` | UUID | NOT NULL | PK + FK → anomaly_alerts.event_id |
| `time` | TIMESTAMPTZ | NOT NULL | Denormalized for retention |
| `explanation_text` | TEXT | NOT NULL | |
| `shap_values` | JSONB | NOT NULL | [{feature, shap_value, direction}] |
| `top_features` | JSONB | NOT NULL | Top 3 precomputed |
| `model_version` | VARCHAR(20) | NOT NULL | |
| `generated_at` | TIMESTAMPTZ | NOT NULL | |

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

### `report_snapshots`

| Column | Type | Null | Notes |
|---|---|---|---|
| `snapshot_id` | UUID | NOT NULL | PK |
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

## Continuous Aggregate Views

| View | Source | Bucket | Serves |
|---|---|---|---|
| `summary_5min` | `anomaly_alerts` | 5 min | `/api/v1/summary` |
| `perf_1min` | `system_performance_metrics` | 1 min | Performance (15-min range) |
| `perf_5min` | `perf_1min` | 5 min | Performance (1-hour range) |
| `perf_15min` | `perf_5min` | 15 min | Performance (24-hour range) |
| `alerts_daily` | `anomaly_alerts` | 1 day | Reports trend chart |

> Cascading CAGGs require TimescaleDB ≥ 2.9

---

## Open Questions for Week 6

| # | Question | Owner |
|---|---|---|
| Q1 | `anomaly_label` — 0/1 binary or multi-class? | Abdalla |
| Q2 | `raw_payload JSONB` — keep or drop? | Abdalla + Beyza |
| Q3 | ALICE `event_id` format — confirm `EVT-{run}-{idx}` vs UUID | Abdalla |
| Q4 | `anomaly_alerts` FK — links to `events` or `fused_events`? | Abdalla + Beyza |
