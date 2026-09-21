# M5 Database Contribution — Beyza Ülkümen

Weeks 17–18 streaming work.

---

## Schema Conformance

Designed and documented the conformance contract between `sensor_schema_v1.avsc` (27 fields) and the three sensor producer streams.

Key decisions:

- All 27 fields present in every record — subtype-specific fields sent as `null`, never omitted
- `schema_version` hardcoded to `"1.0"` — drift detected at producer time before publish
- `label` and `anomaly_type` excluded — populated by M7 AI/ML layer, null throughout M5
- fastavro `schemaless_writer` — validation failure drops the record, never publishes invalid data

Design note: `docs/database/sensor_kafka_producer_schema_conformance.md`

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

Producer runs in an unbounded loop — always-on, no fixed batch ceiling.

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

## Open Items Entering Week 20

- Kafka broker live delivery verification pending (M5W19T9)
- Spark consumer end-to-end verification pending (M5W19T1)
- Multi-hour sustained load test not yet run
- M5 Database contribution full write-up due Week 20
