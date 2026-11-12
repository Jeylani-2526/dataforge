-- M7W27: summary_5min.anomaly_rate counted "has a label" instead of "label = 1".
-- For databases created before the fix in init-db.sql. The view is rebuilt from
-- fused_events, so nothing is lost. Safe to run more than once.

DROP MATERIALIZED VIEW IF EXISTS summary_5min CASCADE;

CREATE MATERIALIZED VIEW IF NOT EXISTS summary_5min
WITH (timescaledb.continuous) AS
SELECT
    time_bucket(BIGINT '300000', timestamp_ms)  AS bucket,
    sensor_type,
    COUNT(*)                                     AS fused_count,
    AVG(data_loss_pct)                           AS avg_data_loss_pct,
    AVG(latency_ms)                              AS avg_latency_ms,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY latency_ms) AS p95_latency_ms,
    -- Share of SCORED rows labelled anomalous; NULL while a bucket is unscored.
    -- (Was "share of rows with any label", which reads 100% once scoring starts.)
    AVG(CASE WHEN anomaly_label = 1 THEN 1.0
             WHEN anomaly_label = 0 THEN 0.0 END)    AS anomaly_rate
FROM fused_events
GROUP BY bucket, sensor_type
WITH NO DATA;

SELECT add_continuous_aggregate_policy('summary_5min',
    start_offset => BIGINT '900000',  -- must cover >= 2 buckets past end_offset (M6W26T7)
    end_offset   => BIGINT '300000',
    schedule_interval => INTERVAL '5 minutes',
    if_not_exists => TRUE);

-- Fill the rebuilt view from existing fused rows.
CALL refresh_continuous_aggregate('summary_5min', NULL, NULL);

SELECT COUNT(*) AS buckets, MAX(anomaly_rate) AS max_anomaly_rate FROM summary_5min;
