-- M8W29 — anomaly_alerts hypertable, alerts_daily CAGG, xai_explanations hypertable
-- Applies to: dataforge DB (TimescaleDB on pg16)
-- Applied: 26 November 2026

CREATE TABLE IF NOT EXISTS anomaly_alerts (
    time                TIMESTAMPTZ  NOT NULL,
    fused_event_id      UUID         NOT NULL,
    source_type         VARCHAR(20)  NOT NULL,
    anomaly_label       BIGINT       NOT NULL,
    risk_score          REAL         NOT NULL,
    confidence          REAL         NOT NULL,
    model_version       VARCHAR(20)  NOT NULL,
    status              VARCHAR(20)  NOT NULL DEFAULT 'active',
    status_updated_at   TIMESTAMPTZ  NULL,
    explanation_summary TEXT         NULL,

    CONSTRAINT pk_anomaly_alerts        PRIMARY KEY (time, fused_event_id),
    CONSTRAINT chk_alerts_risk_score    CHECK (risk_score    BETWEEN 0.0 AND 1.0),
    CONSTRAINT chk_alerts_confidence    CHECK (confidence    BETWEEN 0.0 AND 1.0),
    CONSTRAINT chk_alerts_anomaly_label CHECK (anomaly_label = 1),
    CONSTRAINT chk_alerts_status        CHECK (status IN ('active', 'reviewed', 'closed'))
);

SELECT create_hypertable('anomaly_alerts', 'time',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists       => TRUE);

SELECT add_retention_policy('anomaly_alerts', INTERVAL '365 days',
    if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_alerts_fused_risk
    ON anomaly_alerts (fused_event_id, risk_score DESC);

CREATE MATERIALIZED VIEW IF NOT EXISTS alerts_daily
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 day', time) AS bucket,
    COUNT(*)                   AS anomaly_count
FROM anomaly_alerts
GROUP BY bucket
WITH NO DATA;

SELECT add_continuous_aggregate_policy('alerts_daily',
    start_offset      => INTERVAL '3 days',
    end_offset        => INTERVAL '1 hour',
    schedule_interval => INTERVAL '1 hour',
    if_not_exists     => TRUE);

CREATE TABLE IF NOT EXISTS xai_explanations (
    time             TIMESTAMPTZ  NOT NULL,
    fused_event_id   UUID         NOT NULL,
    explanation_text TEXT         NOT NULL,
    shap_values      JSONB        NOT NULL,
    top_features     JSONB        NOT NULL,
    model_version    VARCHAR(20)  NOT NULL,
    generated_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    CONSTRAINT pk_xai_explanations       PRIMARY KEY (time, fused_event_id),
    CONSTRAINT chk_xai_shap_values_array CHECK (jsonb_typeof(shap_values) = 'array'),
    CONSTRAINT chk_xai_top_features      CHECK (
        CASE WHEN jsonb_typeof(top_features) = 'array'
             THEN jsonb_array_length(top_features) BETWEEN 1 AND 3
             ELSE FALSE END)
);

SELECT create_hypertable('xai_explanations', 'time',
    chunk_time_interval => INTERVAL '1 day',
    if_not_exists       => TRUE);

SELECT add_retention_policy('xai_explanations', INTERVAL '365 days',
    if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_xai_fused
    ON xai_explanations (fused_event_id);
