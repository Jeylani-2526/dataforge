"""
DataForge — Module 6 fusion engine (M6W22T1).

Implements docs/milestones/milestone6/fusion_join_design_note.md. Every join
parameter comes from that note; nothing here is re-decided.
"""

import logging
import os
import signal
import threading
import time

from pyspark.sql import SparkSession, DataFrame
from pyspark.sql.functions import abs as sabs, col, expr, lit, min as smin, struct

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s"
)
log = logging.getLogger(__name__)

# ── Config ───────────────────────────────────────────────────────────────
KAFKA_BOOTSTRAP_SERVERS = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC_ALICE = os.environ.get("KAFKA_TOPIC_ALICE", "alice-events")
KAFKA_TOPIC_RADAR = os.environ.get("KAFKA_TOPIC_RADAR", "sensor-radar")
KAFKA_TOPIC_LIDAR = os.environ.get("KAFKA_TOPIC_LIDAR", "sensor-lidar")
KAFKA_TOPIC_TELEMETRY = os.environ.get("KAFKA_TOPIC_TELEMETRY", "sensor-telemetry")

# Topic -> sensor_type. Uppercase to match the Avro enum (design note Section 7).
SENSOR_TOPICS = {
    KAFKA_TOPIC_RADAR: "RADAR",
    KAFKA_TOPIC_LIDAR: "LIDAR",
    KAFKA_TOPIC_TELEMETRY: "TELEMETRY",
}

WATERMARK_DELAY_SECONDS = int(os.environ.get("WATERMARK_DELAY_SECONDS", "5"))

# Half-window in ms (design note D1/Section 4). Written per fused row.
FUSION_WINDOW_MS = int(os.environ.get("FUSION_WINDOW_MS", "500"))

# Bucket width. 2 x the half-window, so a window spans at most two buckets.
BUCKET_MS = 2 * FUSION_WINDOW_MS

# Option A baseline (design note Section 8). Env var so B and C need no code change.
FUSION_TRIGGER_SECONDS = int(os.environ.get("FUSION_TRIGGER_SECONDS", "5"))

# Design note Section 11. Locked into the checkpoint on first write; changing it
# needs the documented reset, not an edit in place.
FUSION_SHUFFLE_PARTITIONS = int(os.environ.get("FUSION_SHUFFLE_PARTITIONS", "8"))

FUSION_CHECKPOINT_DIR = os.environ.get(
    "FUSION_CHECKPOINT_DIR", "/app/checkpoints"
).rstrip("/")
SPARK_STOP_TIMEOUT_MS = int(os.environ.get("SPARK_STOP_TIMEOUT_MS", "15000"))

QUERY_NAME = "fusion_join"

# No Avro decode in this service (design note Section 3) — only the Kafka
# connector is needed, not spark-avro.
SPARK_KAFKA_PACKAGE = "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.9"

_stop_requested = threading.Event()


# ── Lifecycle ────────────────────────────────────────────────────────────


def _handle_shutdown(signum, frame):
    # Flag only: calling Spark from the handler re-enters the py4j socket the
    # main thread is blocked on (the M5 Item 9 exit 137).
    _stop_requested.set()


def _stop_query(q):
    try:
        q.stop()
    except Exception as e:
        log.warning("Query %s did not stop cleanly: %s", q.name, e)


def _shutdown(spark: SparkSession, close_connections):
    t0 = time.perf_counter()
    log.info("Shutdown requested — stopping active streaming queries.")
    threads = [
        threading.Thread(target=_stop_query, args=(q,)) for q in spark.streams.active
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    close_connections()
    spark.stop()
    log.info("Clean shutdown complete in %.1f s.", time.perf_counter() - t0)


class DroppedRowListener:
    """Surfaces numRowsDroppedByWatermark per stateful operator (design note Section 7).

    Late-dropped join inputs are not counted by the fused writer's
    data_loss_pct, so without this they would be invisible.
    """

    def onQueryStarted(self, event):
        pass

    def onQueryProgress(self, event):
        p = event.progress
        dropped = sum(
            op.get("numRowsDroppedByWatermark", 0) for op in p.get("stateOperators", [])
        )
        if dropped:
            log.warning(
                "%s: %d row(s) dropped by watermark this batch", p.get("name"), dropped
            )

    def onQueryTerminated(self, event):
        pass

    class Java:
        implements = ["org.apache.spark.sql.streaming.StreamingQueryListener"]


# ── Spark session ────────────────────────────────────────────────────────


def get_spark_session(app_name: str = "dataforge-fusion-engine") -> SparkSession:
    spark = (
        SparkSession.builder.appName(app_name)
        .master("local[*]")
        .config("spark.jars.packages", SPARK_KAFKA_PACKAGE)
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.sql.shuffle.partitions", str(FUSION_SHUFFLE_PARTITIONS))
        .config("spark.sql.streaming.stopTimeout", str(SPARK_STOP_TIMEOUT_MS))
        # min keeps the global watermark at the slowest sensor topic, so a
        # lagging topic holds the watermark back instead of having its records
        # dropped as late (design note Section 5, the M5 Item 8 caveat 2 fix).
        .config("spark.sql.streaming.multipleWatermarkPolicy", "min")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("WARN")
    return spark


# ── Stream readers ───────────────────────────────────────────────────────


def _read_kafka(spark: SparkSession, topic: str) -> DataFrame:
    return (
        spark.readStream.format("kafka")
        .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP_SERVERS)
        .option("subscribe", topic)
        .option("startingOffsets", "latest")
        .load()
    )


def prepare_alice(raw: DataFrame) -> DataFrame:
    """alice-events keyed by event_id, bucketed across the window it touches.

    Copying each ALICE event into every bucket its window touches (one or two)
    means a pair is produced exactly once, and gives Spark the equality
    predicate it requires — a time-range-only stream-stream join is rejected
    outright (design note Section 4, confirmed in the Section 12 spike).

    Takes the raw Kafka frame so the spike can feed it a file source.
    """
    return (
        raw.select(
            col("key").cast("string").alias("alice_event_id"),
            col("timestamp").alias("a_time"),
        )
        .withColumn("a_ms", expr("unix_millis(a_time)"))
        .withWatermark("a_time", f"{WATERMARK_DELAY_SECONDS} seconds")
        .withColumn(
            "bucket",
            expr(
                f"explode(sequence("
                f"floor((a_ms - {FUSION_WINDOW_MS}) / {BUCKET_MS}), "
                f"floor((a_ms + {FUSION_WINDOW_MS}) / {BUCKET_MS})))"
            ),
        )
    )


def prepare_sensor(raw: DataFrame, sensor_type: str) -> DataFrame:
    """One sensor topic: keyed by event_id, watermarked, bucketed.

    sensor_type comes from the topic name, so no Avro decode is needed.
    """
    return (
        raw.select(
            col("key").cast("string").alias("sensor_event_id"),
            col("timestamp").alias("s_time"),
        )
        .withColumn("sensor_type", lit(sensor_type))
        .withColumn("s_ms", expr("unix_millis(s_time)"))
        .withWatermark("s_time", f"{WATERMARK_DELAY_SECONDS} seconds")
        .withColumn("s_bucket", expr(f"floor(s_ms / {BUCKET_MS})"))
    )


def union_sensors(streams: list) -> DataFrame:
    """Unions the three prepared sensor streams.

    Each is watermarked separately before this point. That is the whole point:
    one shared watermark would let the fastest topic drive it and drop a
    lagging topic's records (design note Section 5, the M5 Item 8 caveat 2 fix).
    """
    unioned = streams[0]
    for s in streams[1:]:
        unioned = unioned.unionByName(s)
    return unioned


def read_alice_stream(spark: SparkSession) -> DataFrame:
    return prepare_alice(_read_kafka(spark, KAFKA_TOPIC_ALICE))


def read_sensor_streams(spark: SparkSession) -> DataFrame:
    return union_sensors(
        [
            prepare_sensor(_read_kafka(spark, topic), sensor_type)
            for topic, sensor_type in SENSOR_TOPICS.items()
        ]
    )


# ── Join ─────────────────────────────────────────────────────────────────


def build_candidate_pairs(alice: DataFrame, sensor: DataFrame) -> DataFrame:
    """Stage 1 — interval join on the bucket key.

    Inner join, so an ALICE event with no sensor event in range produces no
    row. Those are not data loss; they are counted as a separate match rate
    (design note Section 4).
    """
    return alice.join(
        sensor,
        expr(
            f"bucket = s_bucket AND "
            f"s_time BETWEEN a_time - INTERVAL {FUSION_WINDOW_MS} MILLISECONDS "
            f"AND a_time + INTERVAL {FUSION_WINDOW_MS} MILLISECONDS"
        ),
    )


def select_nearest(pairs: DataFrame) -> DataFrame:
    """Stage 2 — one fused row per ALICE event, the nearest sensor event.

    A stateful aggregation, not a per-batch pick: candidates for one ALICE
    event can arrive across several micro-batches, so choosing inside
    foreachBatch could lock in a worse match before a closer one lands (R3).
    In append mode this emits once, after the watermark passes the window.

    min(struct(...)) compares fields in order, which is the D4 tie-break
    (smallest |dt|, then earlier sensor timestamp, then smallest id) in one step.
    """
    return (
        pairs.withColumn("abs_dt", sabs(col("s_ms") - col("a_ms")))
        .groupBy("alice_event_id", "a_time", "a_ms")
        .agg(
            smin(struct("abs_dt", "s_ms", "sensor_event_id", "sensor_type")).alias("m")
        )
        .select(
            col("alice_event_id"),
            col("a_ms").alias("timestamp_ms"),
            col("m.sensor_event_id").alias("sensor_event_id"),
            col("m.sensor_type").alias("sensor_type"),
            col("m.abs_dt").alias("abs_dt_ms"),
        )
    )


def run():
    # Imported here, not at module scope, so the join functions above can be
    # imported and tested without a database (spike_join_check.py).
    from fused_writer import close_connections, write_fused_events

    signal.signal(signal.SIGTERM, _handle_shutdown)
    signal.signal(signal.SIGINT, _handle_shutdown)

    spark = get_spark_session()
    spark.streams.addListener(DroppedRowListener())

    log.info(
        "Fusion engine starting — bootstrap=%s window=%dms bucket=%dms "
        "watermark=%ds trigger=%ds shuffle_partitions=%d",
        KAFKA_BOOTSTRAP_SERVERS,
        FUSION_WINDOW_MS,
        BUCKET_MS,
        WATERMARK_DELAY_SECONDS,
        FUSION_TRIGGER_SECONDS,
        FUSION_SHUFFLE_PARTITIONS,
    )

    fused = select_nearest(
        build_candidate_pairs(read_alice_stream(spark), read_sensor_streams(spark))
    )

    query = (
        fused.writeStream.queryName(QUERY_NAME)
        .outputMode("append")
        .foreachBatch(write_fused_events)
        .option("checkpointLocation", f"{FUSION_CHECKPOINT_DIR}/{QUERY_NAME}")
        .trigger(processingTime=f"{FUSION_TRIGGER_SECONDS} seconds")
        .start()
    )

    while query.isActive and not _stop_requested.is_set():
        try:
            query.awaitTermination(1)
        except Exception as e:
            log.error("Fusion query terminated with an exception: %s", e)
            break

    if _stop_requested.is_set():
        _shutdown(spark, close_connections)
    else:
        close_connections()
        spark.stop()
        log.info("Fusion query is no longer active — exiting.")


if __name__ == "__main__":
    run()
