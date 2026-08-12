-- DataForge — TimescaleDB Staging Table Init
-- Source: docs/database/staging_table_design.md

CREATE TABLE IF NOT EXISTS raw_alice_events_staging (
    load_id           BIGSERIAL       PRIMARY KEY,
    load_timestamp    TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    batch_id          UUID            NOT NULL,
    event_id          UUID            NOT NULL UNIQUE,
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

CREATE INDEX IF NOT EXISTS idx_alice_staging_batch  ON raw_alice_events_staging (batch_id);
CREATE INDEX IF NOT EXISTS idx_alice_staging_status ON raw_alice_events_staging (load_status);

CREATE TABLE IF NOT EXISTS raw_sensor_events_staging (
    load_id            BIGSERIAL       PRIMARY KEY,
    load_timestamp     TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    batch_id           UUID            NOT NULL,
    event_id           UUID            NOT NULL UNIQUE,
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

CREATE INDEX IF NOT EXISTS idx_sensor_staging_batch  ON raw_sensor_events_staging (batch_id);
CREATE INDEX IF NOT EXISTS idx_sensor_staging_type   ON raw_sensor_events_staging (sensor_type);
CREATE INDEX IF NOT EXISTS idx_sensor_staging_status ON raw_sensor_events_staging (load_status);
CREATE INDEX IF NOT EXISTS idx_sensor_staging_label  ON raw_sensor_events_staging (label);