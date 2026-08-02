# API-Contract Query Test Results

## Test 1 — `GET /api/v1/events/live` (simulated)

**SQL:**
```sql
SELECT event_id, sensor_type AS source_type, timestamp_ms, label AS anomaly_label, anomaly_type
FROM raw_sensor_events_staging
ORDER BY timestamp_ms DESC
LIMIT 5;
```

**Result:** ✅ PASS

| Field | Expected | Actual | Match? |
|---|---|---|---|
| `event_id` | UUID v4 string | UUID v4 ✅ | ✅ |
| `source_type` | radar/lidar/telemetry | LIDAR/RADAR/TELEMETRY (lowercased M4'te) | ✅ |
| `timestamp_ms` | long (ms epoch) | 1784559873032 ✅ | ✅ |
| `anomaly_label` | int 0/1 | 0 (normal records) ✅ | ✅ |
| `anomaly_type` | string or null | null (normal records) ✅ | ✅ |

---

## Test 2 — `GET /api/v1/alerts/recent` (simulated)

**SQL:**
```sql
SELECT event_id, sensor_type AS source_type, timestamp_ms, label AS anomaly_label, anomaly_type
FROM raw_sensor_events_staging
WHERE label = 1
ORDER BY timestamp_ms DESC
LIMIT 5;
```

**Result:** ✅ PASS

| Field | Expected | Actual | Match? |
|---|---|---|---|
| `event_id` | UUID v4 string | UUID v4 ✅ | ✅ |
| `source_type` | radar/lidar/telemetry | TELEMETRY ✅ | ✅ |
| `timestamp_ms` | long (ms epoch) | 1784612551340 ✅ | ✅ |
| `anomaly_label` | int 1 | 1 ✅ | ✅ |
| `anomaly_type` | string | out_of_range_value / timestamp_stall ✅ | ✅ |

---

## Anomaly Type Distribution Check

```sql
SELECT sensor_type, anomaly_type, COUNT(*)
FROM raw_sensor_events_staging
WHERE label = 1
GROUP BY sensor_type, anomaly_type
ORDER BY sensor_type, anomaly_type;
```

| sensor_type | anomaly_type | count |
|---|---|---|
| LIDAR | ghost_point | 498 |
| LIDAR | noise_burst | 502 |
| LIDAR | point_cloud_dropout | 486 |
| RADAR | ghost_target | 513 |
| RADAR | sensor_dropout | 498 |
| RADAR | velocity_spike | 471 |
| TELEMETRY | missing_reading | 465 |
| TELEMETRY | out_of_range_value | 496 |
| TELEMETRY | timestamp_stall | 522 |

**sensor_freeze: NOT PRESENT ✅**

---

## Summary

| Test | Status | Notes |
|---|---|---|
| GET /api/v1/events/live | ✅ PASS | All fields resolve correctly |
| GET /api/v1/alerts/recent | ✅ PASS | Anomaly records return correctly |
| sensor_freeze check | ✅ PASS | Not present in any stream |
| timestamp_stall check | ✅ PASS | Present in TELEMETRY as expected |

**All API-contract fields resolve cleanly against staged data. Staging layer is M9-ready for these two endpoints.**
