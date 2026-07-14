# DataForge — TimescaleDB Staging Table Design

## Table 1 — `raw_alice_events_staging`

Plain staging table — **not a hypertable**. Receives ALICE Run 1 records from Omer's generator before M4 adaptation layer promotes them into `events`.

```sql
CREATE TABLE raw_alice_events_staging (
    load_id           BIGSERIAL       PRIMARY KEY,
    load_timestamp    TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    batch_id          UUID            NOT NULL,

    event_id          UUID            NOT NULL,
    run_number        INTEGER         NOT NULL,
    timestamp_ms      BIGINT          NOT NULL,
    track_count       INTEGER         NOT NULL,
    net_momentum_x    REAL            NOT NULL DEFAULT 0.0,
    net_momentum_y    REAL            NOT NULL DEFAULT 0.0,
    net_momentum_z    REAL            NOT NULL DEFAULT 0.0,
    max_energy_gev    REAL            NOT NULL DEFAULT 0.0,
    total_energy_gev  REAL            NOT NULL DEFAULT 0.0,
    schema_version    VARCHAR(10)     NOT NULL DEFAULT '1.0',
    load_status       VARCHAR(20)     NOT NULL DEFAULT 'pending'
);

CREATE INDEX idx_alice_staging_batch  ON raw_alice_events_staging (batch_id);
CREATE INDEX idx_alice_staging_status ON raw_alice_events_staging (load_status);
```

| Column | Type | Source Field | Notes |
|---|---|---|---|
| `load_id` | BIGSERIAL | — | Staging PK — not promoted to events |
| `load_timestamp` | TIMESTAMPTZ | — | Arrival time — distinct from `timestamp_ms` |
| `batch_id` | UUID | — | Groups records from the same generator batch |
| `event_id` | UUID | `event_id` (string) | Cast string → uuid on load |
| `run_number` | INTEGER | `run_number` (int) | Direct map |
| `timestamp_ms` | BIGINT | `timestamp_ms` (long) | Direct map |
| `track_count` | INTEGER | `track_count` (int) | Direct map |
| `net_momentum_x/y/z` | REAL | `net_momentum_x/y/z` (float) | Default 0.0 until ROOT Docker (M3) |
| `max_energy_gev` | REAL | `max_energy_gev` (float) | Default 0.0 until ROOT Docker (M3) |
| `total_energy_gev` | REAL | `total_energy_gev` (float) | Default 0.0 until ROOT Docker (M3) |
| `schema_version` | VARCHAR(10) | `schema_version` (string) | Must be `"1.0"` — reject if different |
| `load_status` | VARCHAR(20) | — | pending → validated → promoted → failed |

---

## Table 2 — `raw_sensor_events_staging`

Plain staging table — **not a hypertable**. Receives radar, LIDAR, and telemetry records from Omer's generators before M4 adaptation.

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
    load_status        VARCHAR(20)     NOT NULL DEFAULT 'pending'
);

CREATE INDEX idx_sensor_staging_batch  ON raw_sensor_events_staging (batch_id);
CREATE INDEX idx_sensor_staging_type   ON raw_sensor_events_staging (sensor_type);
CREATE INDEX idx_sensor_staging_status ON raw_sensor_events_staging (load_status);
```

| Column | Type | Source Field | Notes |
|---|---|---|---|
| `load_id` | BIGSERIAL | — | Staging PK — not promoted to events |
| `load_timestamp` | TIMESTAMPTZ | — | Arrival time — distinct from `timestamp_ms` |
| `batch_id` | UUID | — | Groups records from the same generator run |
| `event_id` | UUID | `event_id` (string) | Cast string → uuid on load |
| `sensor_id` | UUID | `sensor_id` (string) | Cast string → uuid on load |
| `sensor_type` | VARCHAR(20) | `sensor_type` (enum) | RADAR / LIDAR / TELEMETRY |
| `timestamp_ms` | BIGINT | `timestamp_ms` (long) | Direct map |
| `target_id … signal_strength_db` | REAL/VARCHAR | RADAR fields | NULL for non-RADAR records |
| `scan_id … min_intensity` | REAL/VARCHAR/INT | LIDAR fields | NULL for non-LIDAR records |
| `device_id … sequence_number` | VARCHAR/REAL/BIGINT | TELEMETRY fields | NULL for non-TELEMETRY records |
| `schema_version` | VARCHAR(10) | `schema_version` (string) | Must be `"1.0"` — reject if different |
| `load_status` | VARCHAR(20) | — | pending → validated → promoted → failed |

---

## Cross-Check — `erd_final.md` Alignment

| Staging Column | `events` Target Column | Match? |
|---|---|---|
| `event_id` (uuid) | `events.event_id` (uuid) | ✅ |
| `timestamp_ms` (bigint) | `events.timestamp_ms` (bigint) | ✅ |
| `load_timestamp` | `events.ingestion_ts_ms` (bigint) | ✅ converted: epoch ms |
| `sensor_type` (varchar) | `events.source_type` (varchar) | ✅ lowercased on promote |
| `run_number` (int) | `events.run_number` (int) | ✅ ALICE only |
| `track_count` (int) | `events.track_count` (int) | ✅ ALICE only |
| `net_momentum_*` (real) | `events.net_momentum_*` (real) | ✅ |
| `max/total_energy_gev` (real) | `events.max/total_energy_gev` (real) | ✅ |

`latency_ms`, `data_loss_pct`, `quality_flag`, `anomaly_label`, `risk_score` — pipeline-written in M4/M5/M7, not present in staging.
