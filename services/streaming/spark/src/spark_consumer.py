"""
DataForge — Spark Structured Streaming Consumer
Tasks: M5W18T8 (ALICE consumer) + M5W18T9 (sensor-topic extension + staging write)
Owner: Abdullah

Spark Structured Streaming job covering all four topics: alice-events
plus the three sensor topics (sensor-radar, sensor-lidar,
sensor-telemetry). Applies the M5W17T2 watermark/window design to both:
/docs/milestones/milestone5/watermark_window_design_note.md.

── Design notes ─────────────────────────────────────────────────────────
1. WIRE FORMAT: all producers publish raw, schemaless Avro binary
   (fastavro.schemaless_writer — no Confluent wire-format header, no
   container/sync-marker framing). from_avro() is given the .avsc JSON
   schema directly and decodes the Kafka message value against it with
   no envelope assumptions, matching the producer side exactly.
2. EVENT TIME / WATERMARK / WINDOW: identical treatment for both
   streams — to_timestamp(timestamp_ms / 1000), the shared
   WATERMARK_DELAY_SECONDS value, and a 5-second tumbling window for
   throughput monitoring (console sink), per the design note.
3. SENSOR TOPICS AS ONE STREAM: RADAR/LIDAR/TELEMETRY all conform to
   the single sensor_schema_v1.avsc (sensor_type is a discriminator
   field within one unified record shape), so they're read as ONE
   Kafka source subscribing to all three topic names (comma-separated),
   not three separate readStreams. The real Kafka `topic` column (not
   a literal) is carried through so the windowed count still breaks
   down throughput per actual topic.
4. STAGING WRITE (T9 — new): the non-windowed per-record path required
   by the design note §5. Each micro-batch is collected on the driver,
   run through schema_versioning.enforce() (version-drift check +
   Avro round-trip check — the same module the batch adaptation layer
   uses, imported here rather than reimplemented, per design note §5's
   "no need to reimplement that logic for streaming"), and only
   `valid_records` are inserted into the staging tables. Insert SQL and
   the batch_id / load_status='validated' convention mirror
   scripts/ingestion/staging_ingestion_script.py exactly, so this
   stream-based path and the existing file-based path populate staging
   in a consistent shape. ON CONFLICT (event_id) DO NOTHING makes the
   insert idempotent against Structured Streaming's at-least-once
   redelivery on retry.
5. schema_versioning.py IS NOT part of this build context
   (services/streaming/spark/) — it lives in services/adaptation-layer/
   and is mounted in read-only via docker-compose.yml volumes:, same
   treatment as the ./schemas mount. Reused, not duplicated.
6. CHECKPOINTING: no explicit checkpointLocation is set for any of the
   four queries below, so Spark uses an ephemeral temp directory inside
   the container. Fine for this milestone's local verification, but
   logged here explicitly as an open item: a container restart currently
   loses stream offsets rather than resuming, which is a real gap for
   anything beyond dev/verification use.
──────────────────────────────────────────────────────────────────────
"""

import json
import logging
import os
import signal
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from pyspark.sql import SparkSession, DataFrame
from pyspark.sql.avro.functions import from_avro
from pyspark.sql.functions import col, to_timestamp, window

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
)
log = logging.getLogger(__name__)

# ── Config ───────────────────────────────────────────────────────────────
KAFKA_BOOTSTRAP_SERVERS = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC_ALICE = os.environ.get("KAFKA_TOPIC_ALICE", "alice-events")
KAFKA_TOPIC_RADAR = os.environ.get("KAFKA_TOPIC_RADAR", "sensor-radar")
KAFKA_TOPIC_LIDAR = os.environ.get("KAFKA_TOPIC_LIDAR", "sensor-lidar")
KAFKA_TOPIC_TELEMETRY = os.environ.get("KAFKA_TOPIC_TELEMETRY", "sensor-telemetry")
KAFKA_TOPICS_SENSOR = f"{KAFKA_TOPIC_RADAR},{KAFKA_TOPIC_LIDAR},{KAFKA_TOPIC_TELEMETRY}"

# Reuses the existing config value — no new mechanism, per design note §5.
WATERMARK_DELAY_SECONDS = int(os.environ.get("WATERMARK_DELAY_SECONDS", "5"))

# Same volume-mount pattern as alice-ingestion (./schemas:/app/schemas).
ALICE_SCHEMA_PATH = Path(
    os.environ.get("ALICE_SCHEMA_PATH", "/app/schemas/alice_event_schema_v1.avsc")
)
SENSOR_SCHEMA_PATH = Path(
    os.environ.get("SENSOR_SCHEMA_PATH", "/app/schemas/sensor_schema_v1.avsc")
)

# Same DB env-var pattern as alice_producer.py / avro_adaptation_job.py —
# works both inside Docker (DB_HOST=timescaledb, port 5432 internal) and
# run locally outside Docker (published host port 5433).
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = os.environ.get("DB_PORT", "5433")
DB_NAME = os.environ.get("DB_NAME", "dataforge")
DB_USER = os.environ.get("DB_USER", "dataforge")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "dataforge_dev")

# Spark + Scala versions must line up with pyspark==3.5.9 (requirements.txt).
SPARK_KAFKA_PACKAGE = "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.9"
SPARK_AVRO_PACKAGE = "org.apache.spark:spark-avro_2.12:3.5.9"

# Exact field order for each Avro schema — must match the .avsc files in
# /schemas/ positionally, same convention avro_adaptation_job.py uses,
# since the schemaless fastavro writer inside schema_versioning.enforce()
# encodes fields positionally per schema_evolution_policy.md Section 1.
ALICE_FIELDS = [
    "event_id", "run_number", "timestamp_ms", "track_count",
    "net_momentum_x", "net_momentum_y", "net_momentum_z",
    "max_energy_gev", "total_energy_gev", "schema_version",
]

SENSOR_FIELDS = [
    "event_id", "sensor_id", "sensor_type", "timestamp_ms",
    "target_id", "range_m", "bearing_deg", "elevation_deg",
    "velocity_ms", "signal_strength_db",
    "scan_id", "point_count", "centroid_x_m", "centroid_y_m", "centroid_z_m",
    "max_range_m", "avg_intensity", "min_intensity",
    "device_id", "parameter_name", "value", "unit", "sequence_number",
    "schema_version",
]

# ── Staging insert SQL — mirrors scripts/ingestion/staging_ingestion_script.py ──
ALICE_INSERT = """
    INSERT INTO raw_alice_events_staging (
        load_timestamp, batch_id,
        event_id, run_number, timestamp_ms, track_count,
        net_momentum_x, net_momentum_y, net_momentum_z,
        max_energy_gev, total_energy_gev,
        schema_version, load_status
    ) VALUES (
        %(load_timestamp)s, %(batch_id)s,
        %(event_id)s, %(run_number)s, %(timestamp_ms)s, %(track_count)s,
        %(net_momentum_x)s, %(net_momentum_y)s, %(net_momentum_z)s,
        %(max_energy_gev)s, %(total_energy_gev)s,
        %(schema_version)s, %(load_status)s
    )
    ON CONFLICT (event_id) DO NOTHING
"""

SENSOR_INSERT = """
    INSERT INTO raw_sensor_events_staging (
        load_timestamp, batch_id,
        event_id, sensor_id, sensor_type, timestamp_ms,
        target_id, range_m, bearing_deg, elevation_deg,
        velocity_ms, signal_strength_db,
        scan_id, point_count, centroid_x_m, centroid_y_m, centroid_z_m,
        max_range_m, avg_intensity, min_intensity,
        device_id, parameter_name, value, unit, sequence_number,
        schema_version, label, anomaly_type, load_status
    ) VALUES (
        %(load_timestamp)s, %(batch_id)s,
        %(event_id)s, %(sensor_id)s, %(sensor_type)s, %(timestamp_ms)s,
        %(target_id)s, %(range_m)s, %(bearing_deg)s, %(elevation_deg)s,
        %(velocity_ms)s, %(signal_strength_db)s,
        %(scan_id)s, %(point_count)s, %(centroid_x_m)s, %(centroid_y_m)s,
        %(centroid_z_m)s, %(max_range_m)s, %(avg_intensity)s, %(min_intensity)s,
        %(device_id)s, %(parameter_name)s, %(value)s, %(unit)s, %(sequence_number)s,
        %(schema_version)s, %(label)s, %(anomaly_type)s, %(load_status)s
    )
    ON CONFLICT (event_id) DO NOTHING
"""

_spark_session = None  # module-level handle so the shutdown signal can stop it cleanly


def _handle_shutdown(signum, frame):
    log.info("Shutdown signal received (%s) — stopping active streaming queries.", signum)
    if _spark_session is not None:
        for q in _spark_session.streams.active:
            q.stop()
    sys.exit(0)


# ── Schema loading ────────────────────────────────────────────────────────

def load_schema_json(path: Path) -> str:
    """Raw .avsc file contents as a JSON string — the format from_avro()'s
    jsonFormatSchema parameter expects."""
    if not path.exists():
        raise FileNotFoundError(
            f"Schema file not found at {path}. Mount /app/schemas into the "
            f"container (see docker-compose.yml volumes:) or set the "
            f"corresponding *_SCHEMA_PATH env var."
        )
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def load_parsed_avro_schema(path: Path):
    """fastavro.parse_schema()'d form — what schema_versioning.enforce()
    expects for its round-trip check (a different calling convention from
    from_avro()'s raw JSON string, used for a different library)."""
    from fastavro import parse_schema
    with open(path, "r", encoding="utf-8") as f:
        return parse_schema(json.load(f))


# ── Spark session ────────────────────────────────────────────────────────

def get_spark_session(app_name: str = "dataforge-spark-consumer") -> SparkSession:
    spark = (
        SparkSession.builder
        .appName(app_name)
        .master("local[*]")  # single-node combined container, same posture as the KRaft migration
        .config("spark.jars.packages", f"{SPARK_KAFKA_PACKAGE},{SPARK_AVRO_PACKAGE}")
        .config("spark.sql.session.timeZone", "UTC")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("WARN")
    return spark


# ── Stream readers ────────────────────────────────────────────────────────

def read_alice_stream(spark: SparkSession, schema_json: str) -> DataFrame:
    """alice-events -> decoded AliceEvent fields + event_time + watermark."""
    raw = (
        spark.readStream
        .format("kafka")
        .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP_SERVERS)
        .option("subscribe", KAFKA_TOPIC_ALICE)
        .option("startingOffsets", "latest")
        .load()
    )

    decoded = raw.select(
        col("topic"),
        from_avro(col("value"), schema_json).alias("record"),
    ).select(col("topic"), "record.*")

    with_event_time = decoded.withColumn(
        "event_time", to_timestamp(col("timestamp_ms") / 1000)
    )

    return with_event_time.withWatermark("event_time", f"{WATERMARK_DELAY_SECONDS} seconds")


def read_sensor_stream(spark: SparkSession, schema_json: str) -> DataFrame:
    """
    RADAR/LIDAR/TELEMETRY -> decoded SensorEvent fields + event_time +
    watermark. One Kafka source, comma-separated topic subscription —
    see design note §3 for why this is one stream, not three.
    """
    raw = (
        spark.readStream
        .format("kafka")
        .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP_SERVERS)
        .option("subscribe", KAFKA_TOPICS_SENSOR)
        .option("startingOffsets", "latest")
        .load()
    )

    decoded = raw.select(
        col("topic"),
        from_avro(col("value"), schema_json).alias("record"),
    ).select(col("topic"), "record.*")

    with_event_time = decoded.withColumn(
        "event_time", to_timestamp(col("timestamp_ms") / 1000)
    )

    return with_event_time.withWatermark("event_time", f"{WATERMARK_DELAY_SECONDS} seconds")


# ── Windowed throughput queries (console sink) ───────────────────────────

def build_windowed_throughput_query(df: DataFrame, query_name: str):
    """
    5-second tumbling window, grouped by the REAL Kafka topic column —
    the running events/sec figure Week 19's benchmark needs, and the
    design note's mechanism for surfacing late-data drops. Console sink;
    nothing downstream depends on this sink's output.
    """
    windowed_counts = (
        df.groupBy(
            window(col("event_time"), "5 seconds"),
            col("topic"),
        )
        .count()
    )

    return (
        windowed_counts.writeStream
        .queryName(query_name)
        .outputMode("update")
        .format("console")
        .option("truncate", False)
        .trigger(processingTime="5 seconds")
        .start()
    )


# ── Non-windowed staging writes (foreachBatch) — M5W18T9 ─────────────────

def _get_db_connection():
    import psycopg2
    return psycopg2.connect(
        host=DB_HOST, port=DB_PORT, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD
    )


def make_alice_batch_writer(parsed_schema):
    """
    Returns a foreachBatch(batch_df, batch_id) function closing over the
    already-loaded parsed Avro schema, so it isn't re-parsed from disk on
    every micro-batch.
    """
    def _write(batch_df: DataFrame, spark_batch_id: int):
        from psycopg2.extras import execute_batch
        from schema_versioning import enforce

        rows = [row.asDict() for row in batch_df.select(*ALICE_FIELDS).collect()]
        if not rows:
            log.info("ALICE micro-batch %d: empty, nothing to enforce/write.", spark_batch_id)
            return

        result = enforce(rows, "alice_event", parsed_schema)

        if not result.valid_records:
            log.warning(
                "ALICE micro-batch %d: 0 of %d records passed enforcement — nothing written.",
                spark_batch_id, result.total,
            )
            return

        load_ts = datetime.now(timezone.utc)
        batch_uuid = str(uuid.uuid4())  # own UUID, independent of Spark's integer batch id
        values = [
            {
                "load_timestamp": load_ts,
                "batch_id": batch_uuid,
                "load_status": "validated",
                **rec,
            }
            for rec in result.valid_records
        ]

        conn = _get_db_connection()
        try:
            with conn.cursor() as cur:
                execute_batch(cur, ALICE_INSERT, values, page_size=500)
            conn.commit()
        finally:
            conn.close()

        log.info(
            "ALICE micro-batch %d (db batch=%s): %d written, %d rejected (data_loss_pct=%.4f%%).",
            spark_batch_id, batch_uuid[:8], result.passed, result.rejected, result.data_loss_pct,
        )

    return _write


def make_sensor_batch_writer(parsed_schema):
    def _write(batch_df: DataFrame, spark_batch_id: int):
        from psycopg2.extras import execute_batch
        from schema_versioning import enforce

        rows = [row.asDict() for row in batch_df.select(*SENSOR_FIELDS).collect()]
        if not rows:
            log.info("SENSOR micro-batch %d: empty, nothing to enforce/write.", spark_batch_id)
            return

        result = enforce(rows, "sensor_event", parsed_schema)

        if not result.valid_records:
            log.warning(
                "SENSOR micro-batch %d: 0 of %d records passed enforcement — nothing written.",
                spark_batch_id, result.total,
            )
            return

        load_ts = datetime.now(timezone.utc)
        batch_uuid = str(uuid.uuid4())
        values = [
            {
                "load_timestamp": load_ts,
                "batch_id": batch_uuid,
                "load_status": "validated",
                # Not part of the streamed Avro payload — these are
                # ML-training ground-truth columns populated elsewhere
                # (Module 8/9), same exclusion avro_adaptation_job.py's
                # transform_to_sensor_schema() documents.
                "label": 0,
                "anomaly_type": None,
                **rec,
            }
            for rec in result.valid_records
        ]

        conn = _get_db_connection()
        try:
            with conn.cursor() as cur:
                execute_batch(cur, SENSOR_INSERT, values, page_size=500)
            conn.commit()
        finally:
            conn.close()

        log.info(
            "SENSOR micro-batch %d (db batch=%s): %d written, %d rejected (data_loss_pct=%.4f%%).",
            spark_batch_id, batch_uuid[:8], result.passed, result.rejected, result.data_loss_pct,
        )

    return _write


# ── Main ──────────────────────────────────────────────────────────────────

def run():
    global _spark_session
    signal.signal(signal.SIGTERM, _handle_shutdown)
    signal.signal(signal.SIGINT, _handle_shutdown)

    log.info(
        "Starting Spark Structured Streaming consumer — alice_topic=%s sensor_topics=%s "
        "bootstrap=%s watermark_delay=%ds",
        KAFKA_TOPIC_ALICE, KAFKA_TOPICS_SENSOR, KAFKA_BOOTSTRAP_SERVERS, WATERMARK_DELAY_SECONDS,
    )

    alice_schema_json = load_schema_json(ALICE_SCHEMA_PATH)
    sensor_schema_json = load_schema_json(SENSOR_SCHEMA_PATH)
    alice_parsed_schema = load_parsed_avro_schema(ALICE_SCHEMA_PATH)
    sensor_parsed_schema = load_parsed_avro_schema(SENSOR_SCHEMA_PATH)

    spark = get_spark_session()
    _spark_session = spark

    alice_df = read_alice_stream(spark, alice_schema_json)
    sensor_df = read_sensor_stream(spark, sensor_schema_json)

    # Windowed throughput monitoring (console) — one query per stream.
    build_windowed_throughput_query(alice_df, "alice_throughput")
    build_windowed_throughput_query(sensor_df, "sensor_throughput")

    # Non-windowed TimescaleDB staging write (M5W18T9).
    (
        alice_df.writeStream
        .queryName("alice_staging_write")
        .outputMode("append")
        .foreachBatch(make_alice_batch_writer(alice_parsed_schema))
        .trigger(processingTime="5 seconds")
        .start()
    )
    (
        sensor_df.writeStream
        .queryName("sensor_staging_write")
        .outputMode("append")
        .foreachBatch(make_sensor_batch_writer(sensor_parsed_schema))
        .trigger(processingTime="5 seconds")
        .start()
    )

    # Resilient run loop — NOT a plain spark.streams.awaitAnyTermination().
    # That single call raises the failing query's exception straight out of
    # run(), which would crash every other query too (e.g. a sensor topic
    # not existing yet because sensor-generators hasn't started should not
    # take down the already-healthy alice-events queries). Instead: catch
    # the exception, log which query died and why, call resetTerminated()
    # (required — without it, awaitAnyTermination() immediately re-raises
    # the SAME already-reported termination in a tight crash loop rather
    # than waiting on what's still running), and keep awaiting whatever
    # queries remain active.
    while spark.streams.active:
        try:
            spark.streams.awaitAnyTermination()
        except Exception as e:
            log.error("A streaming query terminated with an exception: %s", e)
            spark.streams.resetTerminated()

    log.info("No active streaming queries remain — exiting.")


if __name__ == "__main__":
    run()