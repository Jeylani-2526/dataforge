# Sensor Kafka Producer Schema Conformance

## Common Fields (All Streams)

| Field | Type | Constraint |
|---|---|---|
| `event_id` | string | UUID v4 |
| `sensor_id` | string | UUID v4 |
| `sensor_type` | enum | `RADAR` / `LIDAR` / `TELEMETRY` |
| `timestamp_ms` | long | ms epoch, positive |
| `schema_version` | string | `"1.0"` |

---

## RADAR → `sensor-radar`

| Field | Type |
|---|---|
| `target_id` | string or null |
| `range_m` | float or null |
| `bearing_deg` | float or null |
| `elevation_deg` | float or null |
| `velocity_ms` | float or null |
| `signal_strength_db` | float or null |

---

## LIDAR → `sensor-lidar`

| Field | Type |
|---|---|
| `scan_id` | string or null |
| `point_count` | int or null |
| `centroid_x_m` | float or null |
| `centroid_y_m` | float or null |
| `centroid_z_m` | float or null |
| `max_range_m` | float or null |
| `avg_intensity` | float or null |
| `min_intensity` | float or null |

---

## TELEMETRY → `sensor-telemetry`

| Field | Type |
|---|---|
| `device_id` | string or null |
| `parameter_name` | string or null |
| `value` | float or null |
| `unit` | string or null |
| `sequence_number` | long or null |

---

## Validation

```python
from fastavro import parse_schema, schemaless_writer
import io, json

schema = parse_schema(json.load(open("schemas/sensor_schema_v1.avsc")))

def validate_and_serialize(record: dict) -> bytes | None:
    try:
        buf = io.BytesIO()
        schemaless_writer(buf, schema, record)
        return buf.getvalue()
    except Exception as e:
        log.warning("Schema validation failed: %s", e)
        return None
```

---

## Dashboard / API Implications

| Endpoint | Değişiklik |
|---|---|
| `GET /api/v1/events/live` | Streaming ile daha sık güncellenir |
| `GET /api/v1/alerts/recent` | Streaming ile latency düşer |
| WebSocket `/ws/events` | M5'te ilk kez gerçek streaming verisi alacak |
