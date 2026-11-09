-- DataForge — TimescaleDB Init

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


CREATE TABLE IF NOT EXISTS events (
    event_id          UUID        NOT NULL,
    timestamp_ms      BIGINT      NOT NULL,
    source_type       VARCHAR(20) NOT NULL,
    run_number        INTEGER,
    track_count       INTEGER,
    net_momentum_x    REAL,
    net_momentum_y    REAL,
    net_momentum_z    REAL,
    max_energy_gev    REAL,
    total_energy_gev  REAL,
    sensor_type       VARCHAR(20),
    label             INTEGER     DEFAULT 0,
    anomaly_type      VARCHAR(50),
    latency_ms        REAL,
    anomaly_label     INTEGER,
    risk_score        REAL,
    schema_version    VARCHAR(10) NOT NULL DEFAULT '1.0',
    PRIMARY KEY (event_id, timestamp_ms)
);

SELECT create_hypertable('events', 'timestamp_ms',
    chunk_time_interval => 86400000,
    if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_events_source_type ON events (source_type, timestamp_ms);
CREATE INDEX IF NOT EXISTS idx_events_label       ON events (label, timestamp_ms);


CREATE TABLE IF NOT EXISTS fused_events (
    timestamp_ms      BIGINT      NOT NULL,
    fused_event_id    UUID        NOT NULL,
    alice_event_id    UUID        NOT NULL,
    sensor_event_id   UUID        NOT NULL,
    sensor_type       VARCHAR(20) NOT NULL,
    fusion_window_ms  INTEGER     NOT NULL DEFAULT 500,
    data_loss_pct     REAL        NOT NULL DEFAULT 0.0,
    latency_ms        BIGINT      NOT NULL DEFAULT 0,
    schema_version    VARCHAR(10) NOT NULL DEFAULT '1.0',
    anomaly_label     BIGINT,
    risk_score        REAL,
    confidence        REAL,
    PRIMARY KEY (fused_event_id, timestamp_ms)
);

SELECT create_hypertable('fused_events', 'timestamp_ms',
    chunk_time_interval => 86400000,
    if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_fused_time_label ON fused_events (timestamp_ms, anomaly_label);


CREATE UNIQUE INDEX IF NOT EXISTS uq_fused_events_replay
    ON fused_events (timestamp_ms, alice_event_id);

CREATE OR REPLACE FUNCTION fused_events_now() RETURNS BIGINT
    LANGUAGE SQL STABLE AS
$$ SELECT (EXTRACT(EPOCH FROM NOW()) * 1000)::BIGINT $$;

SELECT set_integer_now_func('fused_events', 'fused_events_now',
    replace_if_exists => TRUE);

SELECT add_retention_policy('fused_events', BIGINT '7776000000',
    if_not_exists => TRUE);


CREATE TABLE IF NOT EXISTS fusion_status (
    time                TIMESTAMPTZ NOT NULL,
    source_type         VARCHAR(20) NOT NULL,
    quality_score       INTEGER     NOT NULL,
    contribution_weight REAL        NOT NULL,
    data_loss           REAL        NOT NULL,
    latency             REAL        NOT NULL,
    status              VARCHAR(20) NOT NULL
);

SELECT create_hypertable('fusion_status', 'time',
    chunk_time_interval => INTERVAL '1 hour',
    if_not_exists => TRUE);

SELECT add_retention_policy('fusion_status', INTERVAL '7 days',
    if_not_exists => TRUE);

CREATE MATERIALIZED VIEW IF NOT EXISTS summary_5min
WITH (timescaledb.continuous) AS
SELECT
    time_bucket(BIGINT '300000', timestamp_ms)  AS bucket,
    sensor_type,
    COUNT(*)                                     AS fused_count,
    AVG(data_loss_pct)                           AS avg_data_loss_pct,
    AVG(latency_ms)                              AS avg_latency_ms,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY latency_ms) AS p95_latency_ms,
    AVG(CASE WHEN anomaly_label IS NOT NULL THEN 1.0 ELSE 0.0 END) AS anomaly_rate
FROM fused_events
GROUP BY bucket, sensor_type
WITH NO DATA;

SELECT add_continuous_aggregate_policy('summary_5min',
    start_offset => BIGINT '900000',  -- must cover >= 2 buckets past end_offset (M6W26T7)
    end_offset   => BIGINT '300000',
    schedule_interval => INTERVAL '5 minutes',
    if_not_exists => TRUE);
