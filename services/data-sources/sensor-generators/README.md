# Module 2 — Synthetic Sensor Data Generators

**Milestone:** M3 (implementation), extended in M6W23T3
**Status:** ✅ Running — `src/sensor_producer.py`

## Purpose

Generates synthetic RADAR, LIDAR and TELEMETRY records, serializes them against
`sensor_schema_v1.avsc` and publishes them to Kafka. One process publishes all
three types, choosing a type at random per record.

## Sensor Types

| Sensor | Kafka Topic | Type-specific fields |
|---|---|---|
| RADAR | `sensor-radar` | `target_id`, `range_m`, `bearing_deg`, `elevation_deg`, `velocity_ms`, `signal_strength_db` |
| LIDAR | `sensor-lidar` | `scan_id`, `point_count`, `centroid_x_m`, `centroid_y_m`, `centroid_z_m`, `max_range_m`, `avg_intensity`, `min_intensity` |
| TELEMETRY | `sensor-telemetry` | `device_id`, `parameter_name`, `value`, `unit`, `sequence_number` |

Shared by every record: `event_id`, `sensor_id`, `sensor_type`, `timestamp_ms`,
`schema_version`. Fields belonging to other subtypes are written as null rather
than omitted, as the Avro union requires.

## Configuration

### Base

| Variable | Default | Meaning |
|---|---|---|
| `KAFKA_BOOTSTRAP_SERVERS` | `localhost:9092` | Broker address (`kafka:29092` in Compose) |
| `KAFKA_TOPIC_RADAR` | `sensor-radar` | RADAR topic |
| `KAFKA_TOPIC_LIDAR` | `sensor-lidar` | LIDAR topic |
| `KAFKA_TOPIC_TELEMETRY` | `sensor-telemetry` | TELEMETRY topic |
| `SENSOR_PUBLISH_INTERVAL_MS` | `200` | Sleep between records. This is the real rate control |
| `SENSOR_SCHEMA_PATH` | `/app/schemas/sensor_schema_v1.avsc` | Avro schema location |

### Late & out-of-order injection (M6W23T3)

Off by default. Every variable below defaults to `0`, and with injection off the
producer publishes exactly as it did before this mode existed — no Kafka
timestamp is supplied, so the broker assigns the current time as usual.

| Variable | Default | Meaning |
|---|---|---|
| `SENSOR_LATE_FRACTION` | `0.0` | Share of records (0.0–1.0) whose event time is shifted backwards |
| `SENSOR_LATE_MIN_MS` | `0` | Lower bound of the backward shift |
| `SENSOR_LATE_MAX_MS` | `0` | Upper bound of the backward shift |
| `SENSOR_DISORDER_FRACTION` | `0.0` | Share of records (0.0–1.0) diverted to a reorder buffer |
| `SENSOR_DISORDER_BUFFER` | `0` | Buffer size; released shuffled once full. Minimum 2 when disorder is on |
| `SENSOR_INJECTION_SEED` | unset | Seeds the injection RNG for reproducible runs |

### What "late" means here

The fusion engine watermarks on the **Kafka message timestamp**, not on the
`timestamp_ms` field inside the Avro payload. Injection therefore shifts both
together and passes the shifted value as the Kafka message timestamp, so the
watermark actually sees the lateness. The broker runs with the default
`CreateTime` policy, so producer-supplied timestamps are honoured.

`WATERMARK_DELAY_SECONDS` is read here with the same default (`5`) as
`fusion_engine.py`, so both sides share one definition of the line.

**Lateness is spread, not offset** (M6W23T4 finding). A watermark tracks the
newest event time seen in its own stream, not wall clock. Shifting *every*
record by the same amount moves the whole stream and the watermark with it, and
nothing is ever late. A record is late only when it falls 5000 ms or more behind
the newest event time already published on its own topic:

| Record vs its topic's newest event time | Classification | Expected in the join |
|---|---|---|
| Newer | On time | Advances the watermark |
| **< 5000 ms behind** | Tolerated disorder | Still joins; arrives out of order |
| **≥ 5000 ms behind** | Beyond the watermark | Dropped, counted by `numRowsDroppedByWatermark` |

Two configurations produce real drops, and a fraction of `1.0` with a narrow
shift range produces none:

| Condition | Why it works |
|---|---|
| `SENSOR_LATE_FRACTION` below 1.0, shift above 5000 ms | On-time records hold the watermark current; the shifted minority falls behind |
| Shift spread wider than 5000 ms | The stream's newest records outrun its oldest |

A fraction of `1.0` with a spread narrower than the watermark is warned about at
startup, because it looks configured and drops nothing.

The producer scores each record against a local model of its topic's watermark
and logs the split it actually produced:

```
Injection stats — total=3000 shifted=297 reordered=0 | vs topic watermark:
on_time=2703 late_tolerated=0 late_beyond_watermark=297
```

Note also that the join window is **±500 ms**, far tighter than the watermark. A
shift between 500 ms and 5 s survives the watermark but moves the record outside
its contemporaneous ALICE event's window, so it matches an older one instead.
That produces no dropped rows at all.

### Example configurations

```bash
# Default — injection off, behaviour unchanged
docker compose up -d sensor-generators

# Tolerated disorder — survives the watermark, no drops expected
SENSOR_LATE_FRACTION=0.10 SENSOR_LATE_MIN_MS=1000 SENSOR_LATE_MAX_MS=3000

# Crosses the watermark — drops expected. The fraction must stay below 1.0 so
# the other 90% of records hold the watermark current.
SENSOR_LATE_FRACTION=0.10 SENSOR_LATE_MIN_MS=7000 SENSOR_LATE_MAX_MS=9000

# Straddles the line — for a boundary sweep
SENSOR_LATE_FRACTION=0.20 SENSOR_LATE_MIN_MS=0 SENSOR_LATE_MAX_MS=10000 SENSOR_INJECTION_SEED=42

# Drops nothing despite looking aggressive — the whole stream shifts together.
# Warned about at startup. This was the M6W23T4 Phase C mistake.
SENSOR_LATE_FRACTION=1.0 SENSOR_LATE_MIN_MS=7000 SENSOR_LATE_MAX_MS=9000

# Pure out-of-order arrival, no lateness
SENSOR_DISORDER_FRACTION=0.30 SENSOR_DISORDER_BUFFER=8
```

Misconfigurations that would silently inject nothing are rejected at startup
rather than producing a run that looks configured but is not: a fraction set
with a zero magnitude, a fraction outside 0.0–1.0, `MIN_MS` above `MAX_MS`, and
a disorder buffer below 2.

## Setup

```bash
pip install -r requirements.txt
python src/sensor_producer.py
```

In Compose the service is `sensor-generators`, profile `m3-and-above`. The
Dockerfile copies the whole `src/` directory, so `injection.py` needs no build
change.

## Notes

- `EVENTS_PER_SECOND` is passed by `docker-compose.yml` but is **not read** by
  `sensor_producer.py`. Rate is controlled by `SENSOR_PUBLISH_INTERVAL_MS`.
- Injection uses its own random number generator, seeded independently. Enabling
  it does not alter the generated sensor values, so an injected run stays
  comparable with an ordinary one.