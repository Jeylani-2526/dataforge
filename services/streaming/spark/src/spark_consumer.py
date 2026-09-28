"""
DataForge — Spark Structured Streaming consumer (M5W18T8/T9, M5W20T1).

Reads alice-events and the three sensor topics, applies the watermark/window
design (docs/milestones/milestone5/watermark_window_design_note.md), and
writes schema-enforced records to the staging tables.

- Producers publish raw schemaless Avro (no Confluent header), so from_avro()
  decodes with the .avsc directly.
- schema_versioning.py is not in this build context: docker-compose mounts it
  from services/adaptation-layer/ (hence the import ignores below).
- No checkpointLocation is set, so a container restart loses stream offsets
  (open item).
- Throughput (M5W20T1): shuffle partitions and the per-batch record cap are set
  explicitly, and staging writes use COPY. Root cause and measurements:
  docs/milestones/milestone5/m5w20t1_write_path_root_cause.md.
"""

import io
import json
import logging
import os
import signal
import sys
import time
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

# Spark's default of 200 shuffle partitions made every windowed trigger run 200
# tiny stateful tasks, starving the staging writes (M5W20T1). Keep it near the
# core count. Stateful queries lock this value into their checkpoint, so once
# checkpointing exists, changing it needs a fresh checkpoint.
SPARK_SHUFFLE_PARTITIONS = int(os.environ.get("SPARK_SHUFFLE_PARTITIONS", "8"))

# Max Kafka records per micro-batch, per query (0 = unlimited). 50,000 = the
# 10k events/sec bar x the 5 s trigger; bounds driver memory and batch latency.
SPARK_MAX_OFFSETS_PER_TRIGGER = int(os.environ.get("SPARK_MAX_OFFSETS_PER_TRIGGER", "50000"))

# Optional replay point (epoch ms): start every subscribed topic from this Kafka
# timestamp instead of "latest". Empty = latest. Used for backlog-drain tests;
# only applies when a query starts without a checkpoint.
SPARK_STARTING_TIMESTAMP_MS = os.environ.get("SPARK_STARTING_TIMESTAMP_MS", "").strip()

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

# ── Staging columns — same shape as scripts/ingestion/staging_ingestion_script.py ──
ALICE_STAGING_TABLE = "raw_alice_events_staging"
ALICE_STAGING_COLUMNS = ["load_timestamp", "batch_id", *ALICE_FIELDS, "load_status"]

SENSOR_STAGING_TABLE = "raw_sensor_events_staging"
SENSOR_STAGING_COLUMNS = [
    "load_timestamp", "batch_id", *SENSOR_FIELDS, "label", "anomaly_type", "load_status",
]

_spark_session = None  # module-level handle so the shutdown signal can stop it cleanly
_persistent_connections = []  # every PersistentConnection, so shutdown can close them (M5W20T1)


def _close_persistent_connections():
    for db in _persistent_connections:
        db.close()


def _handle_shutdown(signum, frame):
    log.info("Shutdown signal received (%s) — stopping active streaming queries.", signum)
    if _spark_session is not None:
        for q in _spark_session.streams.active:
            q.stop()
    _close_persistent_connections()
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
        .config("spark.sql.shuffle.partitions", str(SPARK_SHUFFLE_PARTITIONS))
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("WARN")
    return spark


# ── Stream readers ────────────────────────────────────────────────────────

def _read_kafka(spark: SparkSession, topics: str) -> DataFrame:
    reader = (
        spark.readStream
        .format("kafka")
        .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP_SERVERS)
        .option("subscribe", topics)
        .option("startingOffsets", "latest")
    )
    if SPARK_MAX_OFFSETS_PER_TRIGGER > 0:
        reader = reader.option("maxOffsetsPerTrigger", SPARK_MAX_OFFSETS_PER_TRIGGER)
    if SPARK_STARTING_TIMESTAMP_MS:
        # Takes precedence over startingOffsets; a topic with no message at/after the
        # timestamp falls back to latest instead of failing the query.
        reader = (
            reader.option("startingTimestamp", SPARK_STARTING_TIMESTAMP_MS)
            .option("startingOffsetsByTimestampStrategy", "latest")
        )
    return reader.load()


def read_alice_stream(spark: SparkSession, schema_json: str) -> DataFrame:
    """alice-events -> decoded AliceEvent fields + event_time + watermark."""
    raw = _read_kafka(spark, KAFKA_TOPIC_ALICE)

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
    raw = _read_kafka(spark, KAFKA_TOPICS_SENSOR)

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


class PersistentConnection:
    """One psycopg2 connection reused across micro-batches (M5W20T1). Each
    writer owns its own, so nothing is shared between query threads."""

    def __init__(self, name: str):
        self.name = name
        self._conn = None
        _persistent_connections.append(self)

    def get(self):
        if self._conn is None or self._conn.closed:
            self._conn = _get_db_connection()
            log.info("[%s] opened persistent DB connection.", self.name)
        return self._conn

    def discard(self):
        """Drop the current connection (broken, stale, or shutting down)."""
        conn, self._conn = self._conn, None
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass  # already broken — nothing more to clean up

    close = discard


def _csv_field(value) -> str:
    """One COPY CSV field. None -> unquoted empty (NULL); anything else is quoted,
    so '' stays an empty string and commas, quotes and newlines are safe."""
    if value is None:
        return ""
    return '"' + str(value).replace('"', '""') + '"'


def _copy_buffer(values: list, columns: list) -> io.StringIO:
    buf = io.StringIO()
    for rec in values:
        buf.write(",".join(_csv_field(rec[c]) for c in columns))
        buf.write("\n")
    return buf


def _copy_insert(db: PersistentConnection, table: str, columns: list, values: list) -> int:
    """COPY rows into a session temp table, then INSERT ... ON CONFLICT (event_id)
    DO NOTHING into the staging table: same dedup as before, far fewer round trips
    (M5W20T1). Returns rows actually inserted. On a connection-level error,
    reconnect and retry once (safe: ON CONFLICT)."""
    import psycopg2

    tmp = f"tmp_{table}"
    col_list = ", ".join(columns)
    buf = _copy_buffer(values, columns)

    for attempt in (1, 2):
        conn = db.get()
        try:
            with conn.cursor() as cur:
                # Column types only (no defaults/constraints); emptied on every commit.
                cur.execute(
                    f"CREATE TEMP TABLE IF NOT EXISTS {tmp} ON COMMIT DELETE ROWS "
                    f"AS SELECT {col_list} FROM {table} WITH NO DATA"
                )
                buf.seek(0)
                cur.copy_expert(f"COPY {tmp} ({col_list}) FROM STDIN WITH (FORMAT csv)", buf)
                cur.execute(
                    f"INSERT INTO {table} ({col_list}) SELECT {col_list} FROM {tmp} "
                    f"ON CONFLICT (event_id) DO NOTHING"
                )
                inserted = cur.rowcount
            conn.commit()
            return inserted
        except (psycopg2.OperationalError, psycopg2.InterfaceError) as exc:
            db.discard()
            if attempt == 2:
                raise
            log.warning(
                "[%s] DB connection failed (%s) — reconnecting and retrying once.",
                db.name, exc,
            )
        except Exception:
            try:
                conn.rollback()
            except Exception:
                db.discard()
            raise


def _make_batch_writer(label: str, stream_name: str, fields: list, table: str,
                       columns: list, parsed_schema, extra_columns: dict):
    db = PersistentConnection(f"{label.lower()}_staging_write")  # reused across micro-batches

    def _write(batch_df: DataFrame, spark_batch_id: int):
        from schema_versioning import enforce  # type: ignore  # mounted by docker-compose

        t0 = time.perf_counter()
        rows = [row.asDict() for row in batch_df.select(*fields).collect()]
        t1 = time.perf_counter()
        if not rows:
            log.info("%s micro-batch %d: empty, nothing to enforce/write.", label, spark_batch_id)
            return

        result = enforce(rows, stream_name, parsed_schema)
        t2 = time.perf_counter()
        if result.rejected:
            first = (result.round_trip_failed[0][1] if result.round_trip_failed
                     else f"version drift, event_id={result.version_drift[0].get('event_id')}")
            log.warning(
                "%s micro-batch %d: %d version drift, %d round-trip failures (first: %s).",
                label, spark_batch_id, len(result.version_drift),
                len(result.round_trip_failed), str(first)[:300],
            )
        if not result.valid_records:
            log.warning(
                "%s micro-batch %d: 0 of %d records passed enforcement — nothing written.",
                label, spark_batch_id, result.total,
            )
            return

        load_ts = datetime.now(timezone.utc)
        batch_uuid = str(uuid.uuid4())  # own UUID, independent of Spark's integer batch id
        values = [
            {"load_timestamp": load_ts, "batch_id": batch_uuid, "load_status": "validated",
             **extra_columns, **rec}
            for rec in result.valid_records
        ]
        inserted = _copy_insert(db, table, columns, values)
        t3 = time.perf_counter()

        # "written" = rows actually inserted; duplicates are redeliveries skipped by ON CONFLICT.
        log.info(
            "%s micro-batch %d (db batch=%s): %d written, %d rejected (data_loss_pct=%.4f%%), "
            "%d duplicate(s) skipped | collect=%dms enforce=%dms insert=%dms",
            label, spark_batch_id, batch_uuid[:8], inserted, result.rejected,
            result.data_loss_pct, len(values) - inserted,
            (t1 - t0) * 1000, (t2 - t1) * 1000, (t3 - t2) * 1000,
        )

    return _write


def make_alice_batch_writer(parsed_schema):
    return _make_batch_writer(
        "ALICE", "alice_event", ALICE_FIELDS,
        ALICE_STAGING_TABLE, ALICE_STAGING_COLUMNS, parsed_schema, extra_columns={},
    )


def make_sensor_batch_writer(parsed_schema):
    # label/anomaly_type are ML ground-truth columns, not part of the streamed
    # Avro payload (populated in Module 8/9), same as avro_adaptation_job.py.
    return _make_batch_writer(
        "SENSOR", "sensor_event", SENSOR_FIELDS,
        SENSOR_STAGING_TABLE, SENSOR_STAGING_COLUMNS, parsed_schema,
        extra_columns={"label": 0, "anomaly_type": None},
    )


# ── Main ──────────────────────────────────────────────────────────────────

def run():
    global _spark_session
    signal.signal(signal.SIGTERM, _handle_shutdown)
    signal.signal(signal.SIGINT, _handle_shutdown)

    log.info(
        "Starting Spark Structured Streaming consumer — alice_topic=%s sensor_topics=%s "
        "bootstrap=%s watermark_delay=%ds shuffle_partitions=%d max_offsets_per_trigger=%d "
        "starting_timestamp_ms=%s",
        KAFKA_TOPIC_ALICE, KAFKA_TOPICS_SENSOR, KAFKA_BOOTSTRAP_SERVERS, WATERMARK_DELAY_SECONDS,
        SPARK_SHUFFLE_PARTITIONS, SPARK_MAX_OFFSETS_PER_TRIGGER,
        SPARK_STARTING_TIMESTAMP_MS or "latest",
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

    _close_persistent_connections()
    log.info("No active streaming queries remain — exiting.")


if __name__ == "__main__":
    run()
