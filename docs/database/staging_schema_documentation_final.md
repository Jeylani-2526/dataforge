# Staging Schema Documentation (Final)

## Tables

| Table                       | Source               | Promotes to                                  |
| --------------------------- | -------------------- | -------------------------------------------- |
| `raw_alice_events_staging`  | ALICE ESD extraction | `events` (source_type='alice')               |
| `raw_sensor_events_staging` | Synthetic generators | `events` (source_type=radar/lidar/telemetry) |

---

## `raw_alice_events_staging`

```sql
CREATE TABLE raw_alice_events_staging (
    load_id           BIGSERIAL       PRIMARY KEY,
    load_timestamp    TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    batch_id          UUID            NOT NULL,
    event_id          UUID            NOT NULL,
    run_number        INTEGER         NOT NULL,
    timestamp_ms      BIGINT          NOT NULL,
    track_count       INTEGER         NOT NULL,
    net_momentum_x    REAL            NOT NULL,
    net_momentum_y    REAL            NOT NULL,
    net_momentum_z    REAL            NOT NULL,
    max_energy_gev    REAL            NOT NULL,
    total_energy_gev  REAL            NOT NULL,
    schema_version    VARCHAR(10)     NOT NULL DEFAULT '1.0',
    load_status       VARCHAR(20)     NOT NULL DEFAULT 'pending'
);
```

**Records:** 68 validated · run 139465 · fEventType=7 filter applied · momentum/energy populated via PyROOT (M4W13T1)

---

## `raw_sensor_events_staging`

```sql
CREATE TABLE raw_sensor_events_staging (
    load_id            BIGSERIAL       PRIMARY KEY,
    load_timestamp     TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    batch_id           UUID            NOT NULL,
    event_id           UUID            NOT NULL,
    sensor_id          UUID            NOT NULL,
    sensor_type        VARCHAR(20)     NOT NULL,
    timestamp_ms       BIGINT          NOT NULL,
    target_id          VARCHAR(64)     DEFAULT NULL,
    range_m            REAL            DEFAULT NULL,
    bearing_deg        REAL            DEFAULT NULL,
    elevation_deg      REAL            DEFAULT NULL,
    velocity_ms        REAL            DEFAULT NULL,
    signal_strength_db REAL            DEFAULT NULL,
    scan_id            VARCHAR(64)     DEFAULT NULL,
    point_count        INTEGER         DEFAULT NULL,
    centroid_x_m       REAL            DEFAULT NULL,
    centroid_y_m       REAL            DEFAULT NULL,
    centroid_z_m       REAL            DEFAULT NULL,
    max_range_m        REAL            DEFAULT NULL,
    avg_intensity      REAL            DEFAULT NULL,
    min_intensity      REAL            DEFAULT NULL,
    device_id          VARCHAR(64)     DEFAULT NULL,
    parameter_name     VARCHAR(128)    DEFAULT NULL,
    value              REAL            DEFAULT NULL,
    unit               VARCHAR(32)     DEFAULT NULL,
    sequence_number    BIGINT          DEFAULT NULL,
    schema_version     VARCHAR(10)     NOT NULL DEFAULT '1.0',
    label              INTEGER         NOT NULL DEFAULT 0,
    anomaly_type       VARCHAR(50)     DEFAULT NULL,
    load_status        VARCHAR(20)     NOT NULL DEFAULT 'pending'
);
```

**Records:** 150,000 validated · ~3% anomaly rate · label and anomaly_type populated (M4W13T3)

---

## Anomaly Taxonomy (v1.1)

| Stream    | Types                                                  |
| --------- | ------------------------------------------------------ |
| RADAR     | ghost_target · velocity_spike · sensor_dropout         |
| LIDAR     | noise_burst · point_cloud_dropout · ghost_point        |
| TELEMETRY | out_of_range_value · timestamp_stall · missing_reading |

`sensor_freeze` retired — replaced by `timestamp_stall`

---

## API-Contract Alignment

| Endpoint                    | Status  |
| --------------------------- | ------- |
| `GET /api/v1/events/live`   | ✅ PASS |
| `GET /api/v1/alerts/recent` | ✅ PASS |

---

## M4 Closure

| # | Item | Status |
|---|---|---|
| 1 | momentum/energy → PyROOT | ✅ Completed — M4W13T1 |
| 2 | PHYSICS_EVENT filter (fEventType=7) | ✅ Completed — M4W13T2 |
| 3 | label + anomaly_type columns added | ✅ Completed — M4W13T3 |
| 4 | Promote staging → production `events` | ⏳ M4W15 |