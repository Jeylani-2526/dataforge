# DataForge — Database Table Sketches v2

**Task:** M1W3T11 — Database Table Sketches — Revised & Expanded  
**Owner:** Beyza Ülkümen — Full-Stack Developer (Module 9)  
**Milestone:** 1 · Week 3 · May 2026  
**Output path:** `/docs/database/db_table_sketches_v2.md`  
**Supersedes:** `db_table_sketches.md` (M1W2T11)  
**Aligned with:** T10 API endpoints · T8 wireframes · T9 UI states · M1W2 CERN exploration notes  

---

## What Changed from v1

| Change | Reason |
|---|---|
| `source_type` replaces `sensor_type` | Reconciled with API endpoint list (T10) — field covers both ALICE and sensor sources |
| `anomaly_label` INT8 (not VARCHAR) | Abdalla's AI model outputs integer label (0=normal, 1=anomaly). VARCHAR was wrong. |
| `xai_explanations` moved to separate table | SHAP JSONB too large to store inline in `anomaly_alerts` at scale |
| `report_snapshots` table added | Reports page (T8 wireframe) implies cached report results for PDF/CSV export |
| Write volume estimates added | Based on prototype bar: ≥10K evt/s = 600K evt/min raw |
| Index strategy expanded | Covers all dashboard query patterns from T10 API endpoints |
| Continuous aggregate views added | Serves /api/v1/summary, /api/v1/performance, /api/v1/reports |

---

## Prototype Bar Throughput Reference

All write volume estimates below are based on:
- **Raw throughput:** ≥10,000 events/sec = **600,000 events/min**
- **Anomaly rate:** ~0.5% of events flagged → ~3,000 anomaly_alerts/min
- **Fusion output:** 1 fused record per raw event → 600,000 fused_events/min
- **Performance snapshot:** 1 row per 10s per sensor = 24 rows/min (4 sensors × 6 snapshots)
- **XAI explanations:** generated for every anomaly → ~3,000/min

---

## Table Overview

| # | Table | Type | Hypertable? | Write Volume/min |
|---|---|---|---|---|
| 1 | `events` | Raw ingestion | ✅ Yes | ~600,000 rows |
| 2 | `fused_events` | Fusion output | ✅ Yes | ~600,000 rows |
| 3 | `anomaly_alerts` | AI model output | ✅ Yes | ~3,000 rows |
| 4 | `xai_explanations` | SHAP output | ❌ No (joined to alerts) | ~3,000 rows |
| 5 | `system_performance_metrics` | Pipeline metrics | ✅ Yes | ~24 rows |
| 6 | `fusion_status` | Fusion engine heartbeat | ✅ Yes | ~24 rows (4 sensors × 6) |
| 7 | `report_snapshots` | Cached report results | ❌ No | On demand only |

---

## Table 1 — `events` (Raw Ingestion)

**Purpose:** Stores every raw event arriving from Module 3 (Data Adaptation Layer) via Kafka.  
**Hypertable:** ✅ Yes — partitioned by `time`, 1-day chunks  
**Write volume:** ~600,000 rows/min at prototype bar  
**Retention policy:** 30 days (raw events dropped after 30 days; aggregates kept indefinitely)

### Schema

```sql
CREATE TABLE events (
    time             TIMESTAMPTZ        NOT NULL,
    event_id         UUID               DEFAULT gen_random_uuid(),
    source_type      VARCHAR(20)        NOT NULL,  -- RADAR | LIDAR | IMU | TEL | ALICE
    anomaly_label    INT8               DEFAULT NULL,  -- NULL until Module 7 processes
    risk_score       FLOAT              DEFAULT NULL,  -- NULL until Module 7 processes
    latency          FLOAT              NOT NULL,      -- ms, pipeline latency from Kafka
    data_loss        FLOAT              NOT NULL,      -- %, watermark drop rate
    raw_payload      JSONB              DEFAULT NULL   -- original Avro fields (optional, M2 decision)
);

SELECT create_hypertable('events', 'time', chunk_time_interval => INTERVAL '1 day');
```

### Indexes

```sql
-- Primary dashboard queries
CREATE INDEX idx_events_time_source     ON events (time DESC, source_type);
CREATE INDEX idx_events_source_label    ON events (source_type, anomaly_label)
    WHERE anomaly_label IS NOT NULL;
CREATE INDEX idx_events_risk_score      ON events (risk_score DESC)
    WHERE risk_score IS NOT NULL;
CREATE INDEX idx_events_event_id        ON events (event_id);

-- Live Stream WS bridge (no DB read — direct Kafka consumer)
-- AI Alerts filter queries
CREATE INDEX idx_events_time_risk       ON events (time DESC, risk_score DESC)
    WHERE risk_score > 0.5;
```

### Index Rationale

| Index | Serves |
|---|---|
| `time DESC, source_type` | Fusion Monitor: /api/v1/fusion/events?source_type= |
| `source_type, anomaly_label` | Home + AI Alerts: filter by sensor and anomaly flag |
| `risk_score DESC` (partial) | AI Alerts: sort by risk, only non-null scores |
| `event_id` | XAI Panel: lookup by event_id |
| `time DESC, risk_score DESC` | Reports: top 10 riskiest events in date range |

### Compression

```sql
ALTER TABLE events SET (
    timescaledb.compress,
    timescaledb.compress_segmentby = 'source_type',
    timescaledb.compress_orderby   = 'time DESC'
);
SELECT add_compression_policy('events', INTERVAL '7 days');
```

---

## Table 2 — `fused_events`

**Purpose:** Stores output of Module 6 (Data Fusion). Each row is a matched/merged record from multiple sensor sources on a unified timeline.  
**Hypertable:** ✅ Yes — partitioned by `time`, 1-day chunks  
**Write volume:** ~600,000 rows/min  
**Retention policy:** 30 days

### Schema

```sql
CREATE TABLE fused_events (
    time                  TIMESTAMPTZ   NOT NULL,
    event_id              UUID          NOT NULL,   -- same event_id as events table
    source_types          TEXT[]        NOT NULL,   -- e.g. ['RADAR', 'LIDAR']
    fusion_quality        INT           NOT NULL,   -- 0–100
    latency               FLOAT         NOT NULL,   -- ms
    data_loss             FLOAT         NOT NULL,   -- %
    time_delta_ms         FLOAT         NOT NULL,   -- timestamp alignment delta
    anomaly_label         INT8          DEFAULT NULL,
    risk_score            FLOAT         DEFAULT NULL,
    confidence            FLOAT         DEFAULT NULL
);

SELECT create_hypertable('fused_events', 'time', chunk_time_interval => INTERVAL '1 day');
```

### Indexes

```sql
CREATE INDEX idx_fused_time            ON fused_events (time DESC);
CREATE INDEX idx_fused_event_id        ON fused_events (event_id);
CREATE INDEX idx_fused_quality         ON fused_events (fusion_quality)
    WHERE fusion_quality < 80;   -- partial: low quality events only
CREATE INDEX idx_fused_risk            ON fused_events (risk_score DESC)
    WHERE risk_score IS NOT NULL;
```

### Index Rationale

| Index | Serves |
|---|---|
| `time DESC` | Fusion Monitor: recent fused events feed |
| `event_id` | XAI Panel: correlate fused record to alert |
| `fusion_quality` (partial) | Fusion Monitor: data loss alert trigger |
| `risk_score DESC` | AI Alerts + Reports: sort by risk |

---

## Table 3 — `anomaly_alerts`

**Purpose:** Stores AI model (Module 7) anomaly detection output. One row per flagged event. This is the primary table for the AI Alerts page.  
**Hypertable:** ✅ Yes — partitioned by `time`, 1-day chunks  
**Write volume:** ~3,000 rows/min (0.5% anomaly rate)  
**Retention policy:** 90 days (alerts kept longer than raw events)

### Schema

```sql
CREATE TABLE anomaly_alerts (
    time                  TIMESTAMPTZ   NOT NULL,
    event_id              UUID          NOT NULL,
    source_type           VARCHAR(20)   NOT NULL,
    anomaly_label         INT8          NOT NULL,   -- 1=anomaly (always 1 in this table)
    risk_score            FLOAT         NOT NULL,   -- 0.0–1.0
    confidence            FLOAT         NOT NULL,   -- 0.0–1.0
    model_version         VARCHAR(20)   NOT NULL,   -- e.g. 'v0.1.0-M7'
    status                VARCHAR(20)   NOT NULL DEFAULT 'active',  -- active|reviewed|closed
    status_updated_at     TIMESTAMPTZ   DEFAULT NULL,
    explanation_summary   TEXT          DEFAULT NULL  -- short plain-language string from Module 8
);

SELECT create_hypertable('anomaly_alerts', 'time', chunk_time_interval => INTERVAL '1 day');
```

### Indexes

```sql
-- AI Alerts page primary queries
CREATE INDEX idx_alerts_risk_time      ON anomaly_alerts (risk_score DESC, time DESC);
CREATE INDEX idx_alerts_status_time    ON anomaly_alerts (status, time DESC);
CREATE INDEX idx_alerts_source_time    ON anomaly_alerts (source_type, time DESC);
CREATE INDEX idx_alerts_event_id       ON anomaly_alerts (event_id);

-- Home page: recent alerts
CREATE INDEX idx_alerts_time_desc      ON anomaly_alerts (time DESC);

-- Reports: date range + filter queries
CREATE INDEX idx_alerts_time_risk_src  ON anomaly_alerts (time DESC, risk_score DESC, source_type);
```

### Index Rationale

| Index | Serves |
|---|---|
| `risk_score DESC, time DESC` | AI Alerts: default sort (highest risk first) |
| `status, time DESC` | AI Alerts: filter by active/reviewed/closed |
| `source_type, time DESC` | AI Alerts + Reports: filter by sensor |
| `event_id` | XAI Panel: lookup by event_id |
| `time DESC` | Home: /api/v1/alerts/recent?limit=5 |
| `time DESC, risk_score, source_type` | Reports: multi-filter date-range queries |

### PATCH Operation (status update)

```sql
-- /api/v1/alerts/{id} PATCH — update status
UPDATE anomaly_alerts
SET status = $1, status_updated_at = NOW()
WHERE event_id = $2;
```

---

## Table 4 — `xai_explanations`

**Purpose:** Stores SHAP feature attribution output from Module 8 (XAI). Separate table because SHAP JSONB can be 2–5KB per record — too large to store inline in `anomaly_alerts` at 3,000 rows/min.  
**Hypertable:** ❌ No — joined to `anomaly_alerts` by `event_id`. Not time-partitioned (accessed by event_id lookup, not time range scan).  
**Write volume:** ~3,000 rows/min  
**Retention policy:** Same as `anomaly_alerts` (90 days)

### Schema

```sql
CREATE TABLE xai_explanations (
    event_id              UUID          PRIMARY KEY,
    time                  TIMESTAMPTZ   NOT NULL,   -- denormalized for retention policy
    explanation_text      TEXT          NOT NULL,   -- plain-language explanation
    shap_values           JSONB         NOT NULL,   -- array of {feature, shap_value, direction}
    top_features          JSONB         NOT NULL,   -- top 3 features (precomputed for Home banner)
    model_version         VARCHAR(20)   NOT NULL,
    generated_at          TIMESTAMPTZ   DEFAULT NOW()
);

-- GIN index for JSONB queries (feature attribution search)
CREATE INDEX idx_xai_shap_gin         ON xai_explanations USING GIN (shap_values);
CREATE INDEX idx_xai_event_id         ON xai_explanations (event_id);
CREATE INDEX idx_xai_time             ON xai_explanations (time DESC);
```

### SHAP JSONB Shape

```json
{
  "shap_values": [
    { "feature": "radar_latency",   "shap_value": 0.312,  "direction": "positive" },
    { "feature": "data_loss_rate",  "shap_value": 0.187,  "direction": "positive" },
    { "feature": "fusion_quality",  "shap_value": 0.142,  "direction": "positive" },
    { "feature": "event_count_1m",  "shap_value": -0.078, "direction": "negative" }
  ],
  "top_features": [
    { "feature": "radar_latency", "shap_value": 0.312 }
  ]
}
```

### Index Rationale

| Index | Serves |
|---|---|
| `event_id` (PK) | XAI Panel: /api/v1/alerts/{id}/xai lookup |
| `shap_values` GIN | Future: search alerts by feature attribution |
| `time DESC` | Retention policy scans + recent XAI reports |

---

## Table 5 — `system_performance_metrics`

**Purpose:** Stores pipeline performance snapshots written by Module 5 (Spark) every 10 seconds per sensor. Primary data source for Performance Metrics page.  
**Hypertable:** ✅ Yes — partitioned by `time`, 1-hour chunks (high write density)  
**Write volume:** ~24 rows/min (4 sensors × every 10s)  
**Retention policy:** 7 days raw; continuous aggregates kept indefinitely

### Schema

```sql
CREATE TABLE system_performance_metrics (
    time                  TIMESTAMPTZ   NOT NULL,
    source_type           VARCHAR(20)   NOT NULL,
    latency_p95_ms        FLOAT         NOT NULL,
    latency_p50_ms        FLOAT         NOT NULL,
    throughput_evts       INT           NOT NULL,   -- events in this 10s window
    data_loss_pct         FLOAT         NOT NULL,
    time_sync_delta_ms    FLOAT         NOT NULL,
    active_sensors        INT           NOT NULL
);

SELECT create_hypertable('system_performance_metrics', 'time',
    chunk_time_interval => INTERVAL '1 hour');
```

### Indexes

```sql
CREATE INDEX idx_perf_time_source     ON system_performance_metrics (time DESC, source_type);
CREATE INDEX idx_perf_latency         ON system_performance_metrics (latency_p95_ms DESC)
    WHERE latency_p95_ms > 400;   -- partial: near-threshold only
```

### Continuous Aggregates

```sql
-- 1-minute aggregate (serves /api/v1/performance?bucket=1m)
CREATE MATERIALIZED VIEW perf_1min
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 minute', time)                                          AS bucket,
    source_type,
    percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_p95_ms)          AS latency_p95,
    AVG(data_loss_pct)                                                     AS avg_data_loss,
    SUM(throughput_evts)                                                   AS total_evts,
    AVG(time_sync_delta_ms)                                                AS avg_sync_delta
FROM system_performance_metrics
GROUP BY bucket, source_type;

SELECT add_continuous_aggregate_policy('perf_1min',
    start_offset => INTERVAL '10 minutes',
    end_offset   => INTERVAL '1 minute',
    schedule_interval => INTERVAL '1 minute');
```

---

## Table 6 — `fusion_status`

**Purpose:** Stores Fusion Engine (Module 6) heartbeat — sensor quality, contribution weight, data loss per sensor every ~10s. Primary data source for Fusion Monitor page.  
**Hypertable:** ✅ Yes — partitioned by `time`, 1-hour chunks  
**Write volume:** ~24 rows/min (4 sensors × every 10s)  
**Retention policy:** 7 days

### Schema

```sql
CREATE TABLE fusion_status (
    time                  TIMESTAMPTZ   NOT NULL,
    source_type           VARCHAR(20)   NOT NULL,
    quality_score         INT           NOT NULL,   -- 0–100
    contribution_weight   FLOAT         NOT NULL,   -- 0.0–1.0
    data_loss             FLOAT         NOT NULL,   -- %
    latency               FLOAT         NOT NULL,   -- ms
    status                VARCHAR(20)   NOT NULL    -- online|degraded|offline
);

SELECT create_hypertable('fusion_status', 'time',
    chunk_time_interval => INTERVAL '1 hour');
```

### Indexes

```sql
CREATE INDEX idx_fusion_time_source    ON fusion_status (time DESC, source_type);
CREATE INDEX idx_fusion_data_loss      ON fusion_status (data_loss DESC)
    WHERE data_loss > 1.0;   -- partial: above threshold only
```

### Index Rationale

| Index | Serves |
|---|---|
| `time DESC, source_type` | Fusion Monitor: /api/v1/fusion/sensors latest per sensor |
| `data_loss > 1.0` (partial) | Fusion Monitor: DataLossAlert trigger |

---

## Table 7 — `report_snapshots`

**Purpose:** Caches computed report results for the Reports page. Avoids re-running expensive join queries on every PDF/CSV export request. Written on demand when operator requests a report.  
**Hypertable:** ❌ No — small table, accessed by snapshot_id or filter hash  
**Write volume:** On demand only (operator-triggered)  
**Retention policy:** 24 hours (auto-expire stale snapshots)

### Schema

```sql
CREATE TABLE report_snapshots (
    snapshot_id           UUID          PRIMARY KEY DEFAULT gen_random_uuid(),
    created_at            TIMESTAMPTZ   DEFAULT NOW(),
    filter_hash           VARCHAR(64)   NOT NULL,   -- SHA256 of filter params (for cache lookup)
    date_from             TIMESTAMPTZ   NOT NULL,
    date_to               TIMESTAMPTZ   NOT NULL,
    source_type_filter    VARCHAR(20)   DEFAULT NULL,
    min_risk_filter       FLOAT         DEFAULT 0.0,
    summary_json          JSONB         NOT NULL,   -- aggregated summary metrics
    top_events_json       JSONB         NOT NULL,   -- top 10 riskiest events
    sensor_perf_json      JSONB         NOT NULL,   -- per-sensor performance summary
    anomaly_trend_json    JSONB         NOT NULL,   -- daily anomaly counts
    expires_at            TIMESTAMPTZ   NOT NULL    -- created_at + 24h
);

CREATE INDEX idx_snapshot_filter_hash ON report_snapshots (filter_hash);
CREATE INDEX idx_snapshot_expires     ON report_snapshots (expires_at);
```

### Cache Logic

```python
# In reports_service.py
filter_hash = sha256(f"{date_from}{date_to}{source_type}{min_risk}".encode()).hexdigest()

# Check cache first
cached = await queries.reports.get_snapshot(conn, filter_hash)
if cached and cached['expires_at'] > datetime.now():
    return cached  # serve from cache

# Generate fresh report
report = await queries.reports.build_report(conn, ...)
await queries.reports.save_snapshot(conn, filter_hash, report)
return report
```

---

## Continuous Aggregates Summary

| View | Source Table | Bucket | Serves |
|---|---|---|---|
| `summary_1h` | `anomaly_alerts` | 1 hour | GET /api/v1/summary (Home page, 30s poll) |
| `perf_1min` | `system_performance_metrics` | 1 minute | GET /api/v1/performance?bucket=1m |
| `perf_5min` | `system_performance_metrics` | 5 minutes | GET /api/v1/performance?bucket=5m |
| `perf_15min` | `system_performance_metrics` | 15 minutes | GET /api/v1/performance?bucket=15m |
| `alerts_daily` | `anomaly_alerts` | 1 day | GET /api/v1/reports (anomaly trend chart) |

### `summary_1h` Definition

```sql
CREATE MATERIALIZED VIEW summary_1h
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', time)                         AS bucket,
    COUNT(*)                                            AS anomaly_count,
    AVG(risk_score)                                     AS avg_risk_score,
    COUNT(DISTINCT source_type)                         AS active_sensors,
    MAX(CASE WHEN risk_score > 0.9 THEN 1 ELSE 0 END)  AS has_critical
FROM anomaly_alerts
GROUP BY bucket;

SELECT add_continuous_aggregate_policy('summary_1h',
    start_offset     => INTERVAL '2 hours',
    end_offset       => INTERVAL '1 minute',
    schedule_interval => INTERVAL '1 minute');
```

### `alerts_daily` Definition

```sql
CREATE MATERIALIZED VIEW alerts_daily
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 day', time)   AS bucket,
    source_type,
    COUNT(*)                     AS anomaly_count,
    AVG(risk_score)              AS avg_risk_score,
    MAX(risk_score)              AS max_risk_score
FROM anomaly_alerts
GROUP BY bucket, source_type;

SELECT add_continuous_aggregate_policy('alerts_daily',
    start_offset     => INTERVAL '2 days',
    end_offset       => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour');
```

---

## Retention Policies Summary

```sql
-- Raw events: 30 days
SELECT add_retention_policy('events',        INTERVAL '30 days');
SELECT add_retention_policy('fused_events',  INTERVAL '30 days');

-- Alert history: 90 days (kept longer for operator review)
SELECT add_retention_policy('anomaly_alerts', INTERVAL '90 days');

-- Performance + fusion heartbeat: 7 days (aggregates serve long-term queries)
SELECT add_retention_policy('system_performance_metrics', INTERVAL '7 days');
SELECT add_retention_policy('fusion_status',              INTERVAL '7 days');

-- Report snapshots: 24 hours (auto-expire)
DELETE FROM report_snapshots WHERE expires_at < NOW();  -- scheduled job
```

---

## Table Relationships

```
events (raw)
  └─→ fused_events (event_id FK — M6 fusion output)
  └─→ anomaly_alerts (event_id FK — M7 model output)
         └─→ xai_explanations (event_id FK — M8 SHAP output)

system_performance_metrics
  └─→ perf_1min / perf_5min / perf_15min (continuous aggregates)

anomaly_alerts
  └─→ summary_1h (continuous aggregate)
  └─→ alerts_daily (continuous aggregate)

report_snapshots (standalone cache — no FK relationships)
fusion_status (standalone heartbeat — no FK relationships)
```

---

## Migration Order (Alembic)

```
001_initial_schema.sql          — CREATE TABLE events, fused_events, anomaly_alerts,
                                  xai_explanations, system_performance_metrics,
                                  fusion_status, report_snapshots
002_hypertables.sql             — SELECT create_hypertable() for 5 tables
003_indexes.sql                 — All indexes above
004_compression_policies.sql    — Compression on events + fused_events
005_retention_policies.sql      — Retention policies (30d / 90d / 7d)
006_continuous_aggregates.sql   — summary_1h, perf_1min/5min/15min, alerts_daily
007_seed_data.sql               — Test fixtures for integration tests
```

---

## Open Questions for M2

| # | Question | Owner | Target |
|---|---|---|---|
| Q1 | Confirm `anomaly_label` INT8 schema with Abdalla — does Module 7 output 0/1 or a multi-class label? | Abdalla | M2 Week 5 |
| Q2 | Confirm `raw_payload JSONB` in events — store original Avro fields or drop? Affects storage estimate. | Abdalla + Beyza | M2 Week 5 |
| Q3 | Confirm ALICE Run 1 field names map cleanly to events schema — coordinate with Omer's CERN notes. | Omer | M2 Week 5 |
| Q4 | SQLAlchemy Core vs raw asyncpg — confirm final DB access pattern before M9 coding starts. | Beyza | M2 Week 6 |
| Q5 | report_snapshots cache TTL — 24h appropriate or should operator-triggered exports skip cache? | Beyza + Abdalla | M2 Week 6 |

---

*Draft v2 prepared May 2026 by Beyza Ülkümen.*  
*Supersedes db_table_sketches.md (M1W2T11).*  
*To be committed to `/docs/database/db_table_sketches_v2.md` on GitHub (M1W3T15).*
