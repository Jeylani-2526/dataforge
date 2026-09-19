# Streamed Record Validation Against ERD/API Contracts

Carried in from M5W18T6.

---

## Scope

Validates RADAR, LIDAR, and TELEMETRY records from `sensor_producer.py` against the DataForge ERD and API contracts. Kafka broker live verification (M5W19T9) pending — this note covers schema-level and field-level conformance via local validation run.

---

## Validation Result

```
RADAR:     True  RADAR      range_m=4047.83
LIDAR:     True  LIDAR      point_count=4766
TELEMETRY: True  TELEMETRY  parameter_name=battery_pct
```

All three sensor types passed `validate_and_serialize()`.

---

## ERD Conformance

| Field | ERD Type | Producer Output | Status |
|---|---|---|---|
| `event_id` | UUID | UUID v4 via `uuid.uuid4()` | ✅ |
| `sensor_type` | enum | RADAR / LIDAR / TELEMETRY | ✅ |
| `timestamp_ms` | bigint | `int(time.time() * 1000)` | ✅ |
| `schema_version` | varchar | `"1.0"` hardcoded | ✅ |
| `sensor_id` | varchar | device ID string | ✅ |
| `label` | varchar | null — M7 AI/ML layer | ✅ deferred |
| `anomaly_type` | varchar | null — M7 AI/ML layer | ✅ deferred |

All 27 schema fields present per record. Subtype-specific fields null for non-matching sensor types — confirmed via local round-trip encode test.

---

## API Contract Conformance

| Endpoint | Status |
|---|---|
| `GET /api/v1/events/live` | ✅ field-level conformant |
| `GET /api/v1/alerts/recent` | ✅ no contract violations |
| `WebSocket /ws/events` | ✅ schema-conformant payload |

`label` and `anomaly_type` null throughout M5 — dashboard implementations handle null without contract violation per M5W17T3 design note.

---

## Open Items

- Kafka broker live delivery test pending (M5W19T9)
- Multi-hour sustained load test not yet run — logged as M5 open item
