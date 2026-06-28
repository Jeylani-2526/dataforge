TimescaleDB CAGG Validation Results
Validation Summary
Continuous Aggregate	Validation Focus	Result
perf_1min	percentile_agg(latency_ms) and approx_percentile(0.95, ...)	PASS
pipeline_health_1min	avg(data_loss_pct) and count(*) grouped by sensor_type	PASS
Test Setup

The validation was performed on a TimescaleDB hypertable named events.

Table Creation
CREATE TABLE events (
    event_time TIMESTAMPTZ NOT NULL,
    latency_ms DOUBLE PRECISION,
    sensor_type TEXT,
    data_loss_pct DOUBLE PRECISION
);

SELECT create_hypertable('events', 'event_time');
Test Data

The following sample records were inserted to simulate incoming sensor events.

INSERT INTO events (event_time, latency_ms, sensor_type, data_loss_pct)
VALUES
(now() - interval '2 minutes', 45.0, 'RADAR', 0.05),
(now() - interval '1 minute', 60.0, 'RADAR', 0.10),
(now(), 35.0, 'LIDAR', 0.00),
(now(), 50.0, 'TELEMETRY', 0.02),
(now(), 70.0, 'RADAR', 0.15);
Continuous Aggregate Validation
1. perf_1min
SQL
CREATE MATERIALIZED VIEW perf_1min
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 minute', event_time) AS bucket,
    percentile_agg(latency_ms) AS latency_percentiles
FROM events
GROUP BY bucket;
CALL refresh_continuous_aggregate(
    'perf_1min',
    NULL,
    NULL
);
SELECT
    bucket,
    approx_percentile(0.95, latency_percentiles) AS p95_latency
FROM perf_1min
ORDER BY bucket;
Output
         bucket         |    p95_latency
------------------------+--------------------
 2026-06-28 17:42:00+00 | 45.015225140383954
 2026-06-28 17:43:00+00 | 60.03939109153004
 2026-06-28 17:44:00+00 | 70.0354061511491
(3 rows)
Result

perf_1min successfully aggregated latency values into one-minute time buckets and returned p95 latency values using percentile_agg and approx_percentile.

Result: PASS

Interpretation

The output demonstrates that the Continuous Aggregate correctly grouped the inserted events into one-minute time buckets and successfully calculated the 95th percentile latency for each interval. The returned p95 values are consistent with the inserted latency measurements, confirming that the aggregate processes time-series data correctly.

The results indicate that perf_1min can efficiently summarize latency metrics while reducing the need to repeatedly scan the raw event table. This makes the Continuous Aggregate suitable for real-time performance monitoring and historical latency analysis within the DataForge pipeline.

2. pipeline_health_1min
SQL
CREATE MATERIALIZED VIEW pipeline_health_1min
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 minute', event_time) AS bucket,
    sensor_type,
    avg(data_loss_pct) AS avg_data_loss_pct,
    count(*) AS event_count
FROM events
GROUP BY bucket, sensor_type;
CALL refresh_continuous_aggregate(
    'pipeline_health_1min',
    NULL,
    NULL
);
SELECT
    bucket,
    sensor_type,
    avg_data_loss_pct,
    event_count
FROM pipeline_health_1min
ORDER BY bucket, sensor_type;
Output
         bucket         | sensor_type | avg_data_loss_pct | event_count
------------------------+-------------+-------------------+-------------
 2026-06-28 17:42:00+00 | RADAR       |              0.05 |           1
 2026-06-28 17:43:00+00 | RADAR       |              0.10 |           1
 2026-06-28 17:44:00+00 | LIDAR       |              0.00 |           1
 2026-06-28 17:44:00+00 | RADAR       |              0.15 |           1
 2026-06-28 17:44:00+00 | TELEMETRY   |              0.02 |           1
(5 rows)
Result

pipeline_health_1min successfully aggregated pipeline health metrics into one-minute buckets grouped by sensor_type. The average data loss percentage and event count were returned as expected.

Result: PASS

Interpretation

The output confirms that the Continuous Aggregate correctly grouped events by both one-minute time intervals and sensor type. The calculated average data loss percentages match the inserted sample data, while the event counts accurately represent the number of events for each sensor category.

These results demonstrate that pipeline_health_1min provides reliable operational metrics for monitoring pipeline health. The aggregate enables efficient tracking of data quality, sensor activity, and event distribution over time without repeatedly querying the underlying hypertable.

Final Result

Both required TimescaleDB Continuous Aggregate validations completed successfully.

The validation confirms that the configured Continuous Aggregates correctly perform time-based aggregation, percentile calculations, statistical averaging, and grouping operations. The generated results match the inserted test data and demonstrate that both Continuous Aggregates behave as expected.

Overall, the validation verifies that the TimescaleDB Continuous Aggregate functionality is correctly configured and ready to support performance monitoring and pipeline health analysis within the DataForge project.

Overall Result: PASS