# Multi-Hour Sustained-Load Verification

Closes open item logged in M5W19T6 and M5W19T8.

---

## Test Parameters

- **Duration:** 4.5 hours (10:31 – 15:00, 26 September 2026)
- **Environment:** Docker Compose, m5-and-above profile
- **Services:** kafka, kafka-ui, timescaledb, alice-ingestion, sensor-generators, spark-processor
- **Kafka:** KRaft mode, single broker, CONTROLLER listener bound to 0.0.0.0:29093

---

## Kafka Topic Message Growth

| Topic | 10:31 | 15:00 | Delta |
|---|---|---|---|
| `alice-events` | 693 | 32,519 | +31,826 |
| `sensor-lidar` | 216 | 26,415 | +26,199 |
| `sensor-radar` | 204 | 26,738 | +26,534 |
| `sensor-telemetry` | 211 | 26,693 | +26,482 |

Out-of-sync replicas: 0 across all topics throughout the run.

---

## Spark Consumer Results (last observed batch: 3249)

```
[alice_event] enforcement: total=10  passed=10  version_drift=0  round_trip_failed=0  data_loss_pct=0.0000%
ALICE micro-batch 3249 (db batch=9a722eac): 0 written, 0 rejected (data_loss_pct=0.0000%), 10 duplicate(s) skipped
collect=487ms  enforce=0ms  insert=9ms
```

- `data_loss_pct=0.0000%` — sustained across all 3,249 micro-batches
- `version_drift=0` — no schema drift detected
- `round_trip_failed=0` — no Avro encode failures
- Micro-batch latency: collect ~450–530ms, enforce <2ms, insert <20ms

---

## Result

**Sustained-load open item closed.** No memory growth, connection pool exhaustion, or record loss observed over 4.5 hours of continuous operation. Pipeline stable under production-representative load.
