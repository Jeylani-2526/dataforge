# M5 Database Contribution

---

## Schema Conformance

Designed and documented the conformance contract between `sensor_schema_v1.avsc` (27 fields) and the three sensor producer streams.

Key decisions:

- All 27 fields present in every record — subtype-specific fields sent as `null`, never omitted
- `schema_version` hardcoded to `"1.0"` — drift detected at producer time before publish
- `sensor_id` type is `uuid`, enforced at DB level by `init-db.sql` — Avro string type has no format constraint; this gap caused a live crash in M5W19T1 until same-day fix
- `label` and `anomaly_type` excluded — populated by M7 AI/ML layer, null throughout M5
- fastavro `schemaless_writer` — validation failure drops the record, never publishes invalid data

Design note: `docs/database/sensor_kafka_producer_schema_conformance.md`
Conformance validation: `docs/database/sensor_streamed_record_erd_api_conformance.md`

---

## Sensor Kafka Producer

| Topic | Sensor Type | Devices | Key Fields |
|---|---|---|---|
| `sensor-radar` | RADAR | 3 | range_m, bearing_deg, velocity_ms, signal_strength_db |
| `sensor-lidar` | LIDAR | 3 | scan_id, point_count, centroid_x/y/z_m, avg/min_intensity |
| `sensor-telemetry` | TELEMETRY | 5 | device_id, parameter_name, value, unit, sequence_number |

Local validation (commit `329fb02`):

```
RADAR:     True  RADAR      range_m=4047.83
LIDAR:     True  LIDAR      point_count=4766
TELEMETRY: True  TELEMETRY  parameter_name=battery_pct
```

Producer runs in an unbounded loop — always-on, no fixed batch ceiling. Device diversity matches M4W13T8 scoping document exactly.

---

## ERD Implications

Write path: `sensor_producer.py` → Kafka topic → Spark consumer (`foreachBatch`) → `events` hypertable

No schema changes required for M5 — hypertable accommodates all 27 fields via nullable columns. `label` and `anomaly_type` remain null until M7.

---

## API Implications

| Endpoint | M4 | M5 |
|---|---|---|
| `GET /api/v1/events/live` | Hours-old batch data | Seconds-old streaming data |
| `GET /api/v1/alerts/recent` | Batch latency | Streaming latency |
| `WebSocket /ws/events` | Unused | Active |

---

## Sustained-Load Verification

4.5-hour soak test, 26 September 2026:

| Topic | Start | End | Delta |
|---|---|---|---|
| `alice-events` | 693 | 32,519 | +31,826 |
| `sensor-lidar` | 216 | 26,415 | +26,199 |
| `sensor-radar` | 204 | 26,738 | +26,534 |
| `sensor-telemetry` | 211 | 26,693 | +26,482 |

Spark consumer (batch 3249): `data_loss_pct=0.0000%`, `version_drift=0`, `round_trip_failed=0`. No memory growth, connection pool exhaustion, or record loss observed. Full results: `docs/data/m5w20t9_soak_test.md`

---

## All M5 Open Items Closed

- Kafka broker live delivery: confirmed M5W19T9 (commit fb26fc9)
- Spark consumer end-to-end: confirmed M5W19T1 (commit 10cf013)
- sensor_id uuid conformance: corrected M5W20T8
- Multi-hour sustained-load: verified M5W20T9
