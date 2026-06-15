# DataForge — Continuous Aggregate Design Note (M2)

## 1. Performance Metrics — 1-Minute Event Count Rolling Window

**Source table:** `events` (HT)  
**Dashboard page:** Performance Metrics  
**Serves:** `/api/v1/performance?bucket=1m`

```sql
CREATE MATERIALIZED VIEW perf_1min
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 minute', time)                                        AS bucket,
    source_type,
    COUNT(*)                                                             AS event_count,
    percentile_cont(0.95) WITHIN GROUP (ORDER BY latency_ms)            AS latency_p95,
    AVG(data_loss_pct)                                                   AS avg_data_loss,
    AVG(time_sync_delta_ms)                                              AS avg_time_sync
FROM events
GROUP BY bucket, source_type;

SELECT add_continuous_aggregate_policy('perf_1min',
    start_offset      => INTERVAL '10 minutes',
    end_offset        => INTERVAL '1 minute',
    schedule_interval => INTERVAL '1 minute');
```

**Cascading aggregates for wider time ranges:**

```sql
-- 5-minute (serves ?bucket=5m — 1-hour range selector)
CREATE MATERIALIZED VIEW perf_5min
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('5 minutes', bucket)  AS bucket,
    source_type,
    SUM(event_count)                  AS event_count,
    MAX(latency_p95)                  AS latency_p95,
    AVG(avg_data_loss)                AS avg_data_loss
FROM perf_1min
GROUP BY bucket, source_type;

-- 15-minute (serves ?bucket=15m — 24-hour range selector)
CREATE MATERIALIZED VIEW perf_15min
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('15 minutes', bucket) AS bucket,
    source_type,
    SUM(event_count)                  AS event_count,
    MAX(latency_p95)                  AS latency_p95,
    AVG(avg_data_loss)                AS avg_data_loss
FROM perf_5min
GROUP BY bucket, source_type;
```

> ⚠️ Cascading CAGGs (`perf_5min` over `perf_1min`) require **TimescaleDB ≥ 2.9**.  
> `percentile_cont` is not decomposable — cascading uses `MAX(latency_p95)` as approximation.

| Property | Value |
|---|---|
| Refresh interval | 1 minute |
| End offset | 1 minute |
| Cascading | Yes — perf_5min, perf_15min |

---

## 2. AI Alerts — Hourly Anomaly Count by Source Type

**Source table:** `anomaly_alerts` (HT)  
**Dashboard page:** AI Alerts · Home summary cards  
**Serves:** `/api/v1/summary` + `/api/v1/alerts/summary`

```sql
CREATE MATERIALIZED VIEW alerts_hourly
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', time)                                          AS bucket,
    source_type,
    COUNT(*)                                                             AS anomaly_count,
    AVG(risk_score)                                                      AS avg_risk_score,
    MAX(risk_score)                                                      AS max_risk_score,
    COUNT(*) FILTER (WHERE risk_score > 0.7)                            AS critical_count,
    COUNT(*) FILTER (WHERE status = 'active')                           AS active_count
FROM anomaly_alerts
GROUP BY bucket, source_type;

SELECT add_continuous_aggregate_policy('alerts_hourly',
    start_offset      => INTERVAL '2 hours',
    end_offset        => INTERVAL '1 minute',
    schedule_interval => INTERVAL '1 minute');
```

| Property | Value |
|---|---|
| Refresh interval | 1 minute |
| End offset | 1 minute |
| Cascading | No |

---

## 3. Home Summary Cards — Daily Totals over Fused Events

**Source table:** `fused_events` (HT)  
**Dashboard page:** Home  
**Serves:** `/api/v1/summary` (daily totals section)

```sql
CREATE MATERIALIZED VIEW fused_daily
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 day', time)                                           AS bucket,
    COUNT(*)                                                             AS total_fused_events,
    AVG(fusion_quality)                                                  AS avg_fusion_quality,
    AVG(data_loss_pct)                                                   AS avg_data_loss,
    COUNT(DISTINCT source_types)                                         AS unique_source_combos
FROM fused_events
GROUP BY bucket;

SELECT add_continuous_aggregate_policy('fused_daily',
    start_offset      => INTERVAL '2 days',
    end_offset        => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour');
```

| Property | Value |
|---|---|
| Refresh interval | 1 hour |
| End offset | 1 hour |
| Cascading | No |

---

## Summary

| View | Source | Bucket | Refresh | Cascading | Serves |
|---|---|---|---|---|---|
| `perf_1min` | `events` | 1 min | 1 min | No | Performance (15-min range) |
| `perf_5min` | `perf_1min` | 5 min | 1 min | Yes ≥2.9 | Performance (1-hour range) |
| `perf_15min` | `perf_5min` | 15 min | 1 min | Yes ≥2.9 | Performance (24-hour range) |
| `alerts_hourly` | `anomaly_alerts` | 1 hour | 1 min | No | AI Alerts · Home summary |
| `fused_daily` | `fused_events` | 1 day | 1 hour | No | Home daily totals |

---

## Refresh Lag Note

All CAGGs have an `end_offset` — data newer than this offset is not yet materialized. Queries must use `materialized_only=false` to automatically merge CAGG with raw table for recent data:

```sql
-- Returns CAGG + raw table merged (fills the lag gap automatically)
SELECT * FROM perf_1min
WHERE bucket >= NOW() - INTERVAL '15 minutes';
```
