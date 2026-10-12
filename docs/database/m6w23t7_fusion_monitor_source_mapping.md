# M6W23T7 — summary_5min Aggregate + Fusion Monitor Endpoint Source Mapping

---

## 1. summary_5min Continuous Aggregate

Added to `infrastructure/scripts/init-db.sql` in this task.

```sql
CREATE MATERIALIZED VIEW IF NOT EXISTS summary_5min
WITH (timescaledb.continuous) AS
SELECT
    time_bucket(BIGINT '300000', timestamp_ms)  AS bucket,
    sensor_type,
    COUNT(*)                                     AS fused_count,
    AVG(data_loss_pct)                           AS avg_data_loss_pct,
    AVG(latency_ms)                              AS avg_latency_ms,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY latency_ms) AS p95_latency_ms,
    AVG(CASE WHEN anomaly_label IS NOT NULL THEN 1.0 ELSE 0.0 END) AS anomaly_rate
FROM fused_events
GROUP BY bucket, sensor_type
WITH NO DATA;

SELECT add_continuous_aggregate_policy('summary_5min',
    start_offset => BIGINT '600000',
    end_offset   => BIGINT '300000',
    schedule_interval => INTERVAL '5 minutes',
    if_not_exists => TRUE);
```

**Source table:** `fused_events` (hypertable, integer timestamp_ms)
**Bucket width:** 300,000 ms (5 minutes)
**Refresh policy:** every 5 minutes, lag 5 minutes
**Serves:** `GET /api/v1/summary`

**Live DB verification:** pending T1 (live fused rows required)

---

## 2. Fusion Monitor Endpoint Source Mapping

| Endpoint | Method | DB Source | Status | Notes |
|---|---|---|---|---|
| `GET /api/v1/summary` | REST | `summary_5min` | **READY** | Data populates once fused rows exist |
| `GET /api/v1/stream/info` | REST | `fusion_status` | **PARTIAL** | Two contract mismatches (see §3) |
| `WS /api/v1/ws/fusion` | WebSocket | `fused_events` + `fusion_status` | **PARTIAL** | Heartbeat mismatches limit fusion_status data |
| `GET /api/v1/fusion/sensors` | REST | `fusion_status` | **PARTIAL** | Per-sensor granularity not implemented |
| `GET /api/v1/fusion/events` | REST | `fused_events` | **READY** | Populated once T1 live run completes |

---

## 3. Heartbeat Contract Mismatches

**Mismatch 1 — status value set:**
- `heartbeat_writer.py` writes: `ok` / `degraded` / `critical`
- `api_contracts_final.md` Section 11 specifies: `online` / `degraded` / `offline`
- **Impact:** `GET /stream/info` and `GET /fusion/sensors` return non-contract status values

**Mismatch 2 — source_type granularity:**
- `heartbeat_writer.py` writes source_type `alice` and `sensor` (two rows per batch)
- `GET /fusion/sensors` expects latest row per sensor (RADAR / LIDAR / TELEMETRY individually)
- **Impact:** sensor grid cannot distinguish between sensor types

---

## 4. What M9 Builds Against

Can reliably serve (once fused rows exist):
- `GET /api/v1/summary`
- `GET /api/v1/fusion/events`
- `WS /api/v1/ws/fusion`

Cannot reliably serve without resolving §3:
- `GET /api/v1/stream/info`
- `GET /api/v1/fusion/sensors`
