# Streamed Record Validation Against ERD/API Contracts

---

## Validation Result

```
RADAR:     True  RADAR      range_m=4047.83
LIDAR:     True  LIDAR      point_count=4766
TELEMETRY: True  TELEMETRY  parameter_name=battery_pct
```

All three sensor types passed `validate_and_serialize()`. Kafka broker live verification confirmed (M5W19T9, commit fb26fc9).

---

## ERD Conformance

| Field            | ERD Type | Producer Output                                | Validation Method                                                                                                     | Status       |
| ---------------- | -------- | ---------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- | ------------ |
| `event_id`       | uuid     | UUID v4 via `uuid.uuid4()`                     | Avro round-trip                                                                                                       | ✅           |
| `sensor_type`    | enum     | RADAR / LIDAR / TELEMETRY                      | Avro round-trip                                                                                                       | ✅           |
| `timestamp_ms`   | bigint   | `int(time.time() * 1000)`                      | Avro round-trip                                                                                                       | ✅           |
| `schema_version` | varchar  | `"1.0"` hardcoded                              | Avro round-trip                                                                                                       | ✅           |
| `sensor_id`      | uuid     | UUID v4 per sensor instance, stable at startup | DB-level constraint — UUID v4 enforced by init-db.sql, not Avro. Gap caused live crash in M5W19T1 until same-day fix. | ✅ corrected |
| `label`          | varchar  | null — M7 AI/ML layer                          | —                                                                                                                     | ✅ deferred  |
| `anomaly_type`   | varchar  | null — M7 AI/ML layer                          | —                                                                                                                     | ✅ deferred  |

All 27 schema fields present per record. Subtype-specific fields null for non-matching sensor types.

---

## API Contract Conformance

| Endpoint                    | Status                       |
| --------------------------- | ---------------------------- |
| `GET /api/v1/events/live`   | ✅ field-level conformant    |
| `GET /api/v1/alerts/recent` | ✅ no contract violations    |
| `WebSocket /ws/events`      | ✅ schema-conformant payload |

`label` and `anomaly_type` null throughout M5 — per M5W17T3 design note.

---

## Open Items

- Multi-hour sustained load test not yet run — M5W20T9
