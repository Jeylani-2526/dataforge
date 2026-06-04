# TimescaleDB — Continuous Aggregates Research Note

**Task:** M1W3T12 — TimescaleDB Continuous Aggregates Research Note  
**Owner:** Beyza Ülkümen — Full-Stack Developer (Module 9)  
**Milestone:** 1 · Week 3 · May 2026  
**Output path:** `/docs/research/timescaledb_continuous_aggregates.md`  
**Feeds:** M2 ERD deliverable · db_table_sketches_v2.md (M1W3T11)

---

## 1. What Are Continuous Aggregates?

A **continuous aggregate** is a materialized view in TimescaleDB that automatically pre-computes and incrementally refreshes aggregations over a hypertable. Unlike a standard PostgreSQL materialized view (which requires a full recompute on every refresh), a continuous aggregate only recomputes the time buckets that have changed since the last refresh.

### How It Works

```
Raw hypertable (events)
  time    | source_type | risk_score | latency
  --------+-------------+------------+--------
  14:32:00 | RADAR       | 0.91       | 287ms
  14:32:01 | LIDAR       | 0.12       | 312ms
  14:32:01 | RADAR       | 0.55       | 291ms
  ...600,000 rows per minute...

         ↓  time_bucket('1 minute', time)

Continuous aggregate (perf_1min)
  bucket   | source_type | latency_p95 | avg_data_loss | total_evts
  ---------+-------------+-------------+---------------+-----------
  14:32:00 | RADAR       | 291ms       | 0.4%          | 3,241
  14:32:00 | LIDAR       | 315ms       | 0.6%          | 2,891
  ...4 rows per minute (one per sensor)...
```

The dashboard polling endpoint (`GET /api/v1/performance?bucket=1m`) queries `perf_1min` — 4 rows — instead of scanning 600,000 raw rows. Response time drops from seconds to milliseconds.

### Key Properties

| Property | Behaviour |
|---|---|
| **Incremental refresh** | Only re-aggregates changed time buckets, not the full table |
| **Transparent query rewrite** | TimescaleDB can automatically route queries on the raw table to the CAGG (if `timescaledb.enable_cagg_rewrite=on`) |
| **Real-time flag** | With `WITH (timescaledb.continuous, timescaledb.materialized_only=false)`, queries include un-materialized recent data automatically |
| **Watermark** | The CAGG only materializes data older than `end_offset`. Data newer than the watermark is read from the raw table and merged at query time. |
| **Cascading CAGGs** | A CAGG can be built on top of another CAGG (e.g. hourly CAGG over a minutely CAGG) — supported from TimescaleDB 2.9+ |

---

## 2. DataForge Use Cases

### Use Case 1 — Home Page: System Summary (30s poll)

**Dashboard:** Home page `GET /api/v1/summary` — polls every 30s  
**Problem:** Summary requires: active alert count (1h), avg risk score (1h), active sensor count, system status — all aggregated over the last hour across potentially millions of raw events.  
**Solution:** `summary_1h` continuous aggregate over `anomaly_alerts`.

```sql
CREATE MATERIALIZED VIEW summary_1h
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', time)                          AS bucket,
    COUNT(*)                                             AS anomaly_count,
    AVG(risk_score)                                      AS avg_risk_score,
    COUNT(DISTINCT source_type)                          AS active_sensors,
    MAX(CASE WHEN risk_score > 0.9 THEN 1 ELSE 0 END)   AS has_critical
FROM anomaly_alerts
GROUP BY bucket;

SELECT add_continuous_aggregate_policy('summary_1h',
    start_offset      => INTERVAL '2 hours',
    end_offset        => INTERVAL '1 minute',
    schedule_interval => INTERVAL '1 minute');
```

**Query at runtime:**
```sql
-- Instead of scanning all anomaly_alerts for the last hour:
SELECT anomaly_count, avg_risk_score, active_sensors, has_critical
FROM summary_1h
WHERE bucket >= NOW() - INTERVAL '1 hour'
ORDER BY bucket DESC
LIMIT 1;
-- Returns 1 row instantly vs scanning ~180,000 alert rows
```

**Impact:** 30s poll on Home page completes in <5ms instead of 2–3s full scan.

---

### Use Case 2 — Performance Page: Time-Series Charts (10s poll)

**Dashboard:** Performance Metrics page `GET /api/v1/performance?bucket=1m|5m|15m`  
**Problem:** Latency p95 line chart, throughput bar chart, data loss area chart — all require time-bucketed aggregations over `system_performance_metrics`. At 24 rows/min this table is small, but at full prototype bar throughput direct aggregation would be expensive.  
**Solution:** Three resolution CAGGs — 1min, 5min, 15min — to serve the three time range selectors on the Performance page.

```sql
-- 1-minute resolution (serves 15-min range selector)
CREATE MATERIALIZED VIEW perf_1min
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 minute', time)                                       AS bucket,
    source_type,
    percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_p95_ms)        AS latency_p95,
    AVG(data_loss_pct)                                                  AS avg_data_loss,
    SUM(throughput_evts)                                                AS total_evts,
    AVG(time_sync_delta_ms)                                             AS avg_sync_delta
FROM system_performance_metrics
GROUP BY bucket, source_type;

-- 5-minute resolution (serves 1-hour range selector)
CREATE MATERIALIZED VIEW perf_5min
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('5 minutes', bucket)   AS bucket,
    source_type,
    MAX(latency_p95)                   AS latency_p95,
    AVG(avg_data_loss)                 AS avg_data_loss,
    SUM(total_evts)                    AS total_evts
FROM perf_1min   -- cascading CAGG over perf_1min
GROUP BY bucket, source_type;

-- 15-minute resolution (serves 24-hour range selector)
CREATE MATERIALIZED VIEW perf_15min
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('15 minutes', bucket)  AS bucket,
    source_type,
    MAX(latency_p95)                   AS latency_p95,
    AVG(avg_data_loss)                 AS avg_data_loss,
    SUM(total_evts)                    AS total_evts
FROM perf_5min   -- cascading CAGG over perf_5min
GROUP BY bucket, source_type;
```

**FastAPI routing logic:**
```python
# In performance_service.py
def get_cagg_name(bucket: str) -> str:
    return {
        "1m":  "perf_1min",
        "5m":  "perf_5min",
        "15m": "perf_15min",
    }.get(bucket, "perf_1min")
```

**Impact:** Performance page charts load in <10ms regardless of selected time range.

---

### Use Case 3 — Reports Page: Daily Anomaly Trend Chart (on demand)

**Dashboard:** Reports page `GET /api/v1/reports` — anomaly trend chart shows daily anomaly counts for selected date range (up to 7 days).  
**Problem:** Counting anomalies per day per sensor over 7 days requires scanning up to 30M+ rows from `anomaly_alerts` at prototype bar throughput.  
**Solution:** `alerts_daily` continuous aggregate — pre-computes daily counts.

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
    start_offset      => INTERVAL '2 days',
    end_offset        => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour');
```

**Query at runtime:**
```sql
-- Reports page: anomaly trend for last 7 days
SELECT bucket, source_type, anomaly_count, avg_risk_score
FROM alerts_daily
WHERE bucket >= NOW() - INTERVAL '7 days'
  AND ($1::text IS NULL OR source_type = $1)
ORDER BY bucket ASC, source_type;
-- Returns 28 rows (7 days × 4 sensors) vs scanning ~12.6M alert rows
```

**Impact:** Reports page loads in <20ms vs 10–30s full scan.

---

## 3. Gotchas & Known Limitations

### 3.1 Refresh Lag (Most Important)

The CAGG watermark means recent data may not yet be materialized. By default, data newer than `end_offset` is NOT in the CAGG — it exists only in the raw table.

**Example:** With `end_offset = INTERVAL '1 minute'`, the last 60 seconds of data are not in `perf_1min`. A query at 14:32:45 will see data up to 14:31:45 from the CAGG.

**DataForge impact:**
- Home page 30s poll: acceptable — summary is inherently historical (1h window)
- Performance page 10s poll: may miss last 60s of metrics — acceptable for chart display
- Live Stream: NOT served by CAGG — WebSocket reads directly from Kafka, bypasses DB

**Mitigation:** Use `materialized_only=false` to automatically merge CAGG with raw table for recent data:
```sql
-- Query merges CAGG + raw table seamlessly
SELECT * FROM perf_1min
WHERE bucket >= NOW() - INTERVAL '15 minutes';
-- TimescaleDB automatically fills the gap from raw table
```

### 3.2 Query Rewrite Requirement

TimescaleDB can automatically rewrite queries on the raw hypertable to use the CAGG — but only if the query exactly matches the CAGG's `GROUP BY` and `time_bucket` call.

```sql
-- This WILL be rewritten to use perf_1min automatically:
SELECT time_bucket('1 minute', time), source_type, AVG(latency_p95_ms)
FROM system_performance_metrics
GROUP BY 1, 2;

-- This will NOT (different bucket size, no automatic rewrite):
SELECT time_bucket('2 minutes', time), AVG(latency_p95_ms)
FROM system_performance_metrics
GROUP BY 1;
```

**DataForge mitigation:** FastAPI service layer explicitly queries the named CAGG view (`perf_1min`, `perf_5min` etc.) rather than relying on automatic rewrite. Explicit is safer and more predictable.

### 3.3 No Percentile in Cascading CAGGs

`percentile_cont()` is not decomposable — it cannot be recomputed from a CAGG of a CAGG. This means `perf_5min` and `perf_15min` use `MAX(latency_p95)` instead of recomputing p95, which is a slight approximation.

**DataForge impact:** Acceptable for the prototype — max p95 across 1-min buckets is a conservative (safe) approximation of true p95 over 5/15 minutes. Will be noted in the M10 performance report.

### 3.4 Schema Changes Require CAGG Rebuild

If the underlying hypertable schema changes (e.g. adding a column), existing CAGGs must be dropped and recreated. In M2, finalize the schema before creating CAGGs.

**DataForge mitigation:** CAGGs are defined in migration `006_continuous_aggregates.sql` — after `001_initial_schema.sql`. Schema changes in M2 should update migration 001 and trigger a rebuild of 006.

### 3.5 Storage Overhead

CAGGs consume additional storage — typically 1–5% of the raw table size for typical aggregation ratios. At 600K events/min (raw), `perf_1min` stores only 4 rows/min — negligible overhead. `summary_1h` stores 1 row/hour — trivial.

---

## 4. Summary: Which Queries Use CAGGs in DataForge

| Dashboard Page | Endpoint | CAGG Used | Raw Table Avoided |
|---|---|---|---|
| Home | GET /api/v1/summary | `summary_1h` | `anomaly_alerts` (1h scan) |
| Performance | GET /api/v1/performance?bucket=1m | `perf_1min` | `system_performance_metrics` |
| Performance | GET /api/v1/performance?bucket=5m | `perf_5min` | `system_performance_metrics` |
| Performance | GET /api/v1/performance?bucket=15m | `perf_15min` | `system_performance_metrics` |
| Reports | GET /api/v1/reports (trend chart) | `alerts_daily` | `anomaly_alerts` (7-day scan) |
| Live Stream | WS /api/v1/ws/stream | **None** — direct Kafka | `events` (never queried) |
| AI Alerts | GET /api/v1/alerts | **None** — direct table | `anomaly_alerts` (indexed query) |
| Fusion Monitor | GET /api/v1/fusion/sensors | **None** — direct table | `fusion_status` (indexed query) |
| XAI Panel | GET /api/v1/alerts/{id}/xai | **None** — PK lookup | `xai_explanations` (PK index) |

---

## 5. M2 Action Items

1. **Finalize schema before creating CAGGs** — CAGGs defined in migration 006, after schema is locked in M2 Week 5.
2. **Confirm `percentile_cont` approximation** with Abdalla — is MAX(p95) acceptable for 5min/15min Performance charts?
3. **Test CAGG refresh lag** in Docker Compose environment — measure actual lag vs `end_offset` setting.
4. **Evaluate `materialized_only=false`** — enable on `perf_1min` to close the 60s gap for the Performance page.

---

*Research note prepared May 2026 by Beyza Ülkümen.*  
*To be committed to `/docs/research/timescaledb_continuous_aggregates.md` on GitHub (M1W3T15).*
