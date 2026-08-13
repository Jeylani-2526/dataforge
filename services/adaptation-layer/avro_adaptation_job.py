"""
DataForge — PySpark Adaptation Job Scaffold (Avro Serialization)
Task: M4W14T2
Owner: Abdullah

Reads filtered/corrected ALICE and sensor records from the TimescaleDB
staging tables (raw_alice_events_staging / raw_sensor_events_staging —
populated by scripts/ingestion/staging_ingestion_script.py, post the
M4W14T1 stream-type filtering fix) and serializes them to Avro per the
three locked v1 schemas:

    /schemas/alice_event_schema_v1.avsc
    /schemas/sensor_schema_v1.avsc
    /schemas/fused_event_schema_v1.avsc

Field reference: /docs/data/root_to_avro_mapping.md (ALICE fields),
/docs/data/sensor_field_spec.md (sensor fields).

── Design notes (read before modifying) ──────────────────────────────────
1. READ: JDBC batch read (spark.read.jdbc). Spark has no built-in
   streaming-JDBC source, so this is intentionally a batch job this
   week — the scaffold occupies the position Structured Streaming will
   occupy once Kafka topics exist (services/streaming/kafka is still
   empty as of M4W14). Transform functions below are written as pure
   DataFrame -> DataFrame functions so the read step is the only thing
   that changes when that migration happens.

2. SERIALIZE: fastavro, not Spark's native `.write.format("avro")`.
   Spark's avro writer needs the org.apache.spark:spark-avro package
   pulled from Maven at submit time; fastavro is already a project
   dependency (used in schemas/validate_schema.py) and keeps this
   scaffold dependency-free beyond what's already pinned. Serialization
   happens per-partition via mapPartitions so this scales past a
   single-driver bottleneck once Omer's execution environment (M4W14T5)
   is confirmed runnable and Week 15's full-volume run (68 ALICE +
   150,000 sensor records) exercises this path for real.

3. WRITE TARGET: local Avro files under data/adaptation/avro/, not a
   Kafka topic. Kafka topic creation isn't scoped to this task or to
   Week 14's deliverables. Omer's Parquet writer stage (M4W14T4) reads
   directly from this output directory.

4. FUSED EVENT — INTENTIONALLY NOT IMPLEMENTED THIS WEEK.
   fused_event_schema_v1.avsc requires a matched ALICE+sensor pair
   (Module 6 stream-stream join). services/fusion/ is still an empty
   scaffold (.gitkeep only) — there is no join logic anywhere in the
   repo to build this against. write_fused_events() below is a stub
   that documents the schema contract and raises NotImplementedError
   if called, so it fails loudly instead of silently producing empty
   or fabricated fused records. FLAG FOR M4W14T8 (Tuesday checkpoint):
   confirm this is out of scope for M4 and pushed to whichever week
   Module 6 fusion logic is actually built.

5. SCHEMA-VERSION ENFORCEMENT (M4W14T3) — IMPLEMENTED, see
   schema_versioning.py. Every batch is run through enforce() before
   being committed to an Avro file: schema_version is stamped from the
   CURRENT_SCHEMA_VERSIONS registry (not trusted verbatim from staging),
   and every record is round-tripped (serialize -> deserialize -> compare)
   against the actual locked .avsc schema before being written. Records
   that fail either check are excluded from the output file and counted
   in the returned data_loss_pct — they are not silently dropped.
────────────────────────────────────────────────────────────────────────
"""

import argparse
import json
import logging
from pathlib import Path

from pyspark.sql import SparkSession, DataFrame
from pyspark.sql import functions as F

# ── Logging ──────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
)
log = logging.getLogger(__name__)

# ── Config ───────────────────────────────────────────────────────────────
# Mirrors scripts/ingestion/staging_ingestion_script.py — same staging DB.
JDBC_URL = "jdbc:postgresql://localhost:5432/dataforge"
JDBC_PROPERTIES = {
    "user": "dataforge",
    "password": "dataforge_dev",
    "driver": "org.postgresql.Driver",
}

SCHEMA_DIR = Path("schemas")
OUTPUT_DIR = Path("data/adaptation/avro")

# Exact field order for each Avro schema — must match the .avsc files in
# /schemas/ positionally, since the schemaless fastavro writer encodes
# fields positionally per schema_evolution_policy.md Section 1
# ("Changing the field order... is always breaking").
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


# ── Spark session ────────────────────────────────────────────────────────

def get_spark_session(app_name: str = "dataforge-adaptation-layer") -> SparkSession:
    return (
        SparkSession.builder
        .appName(app_name)
        .config("spark.sql.session.timeZone", "UTC")
        .getOrCreate()
    )


# ── Read: staging tables (JDBC) ──────────────────────────────────────────

def read_alice_staging(spark: SparkSession) -> DataFrame:
    """
    Reads validated ALICE records from raw_alice_events_staging.
    Only load_status='validated' rows are read — staging_ingestion_script.py
    only ever inserts validated rows, but this filter is defensive in case
    that invariant changes upstream.
    """
    df = (
        spark.read.jdbc(
            url=JDBC_URL,
            table="raw_alice_events_staging",
            properties=JDBC_PROPERTIES,
        )
        .filter(F.col("load_status") == "validated")
    )
    return df.select(*ALICE_FIELDS)


def read_sensor_staging(spark: SparkSession) -> DataFrame:
    """Reads validated sensor records (RADAR/LIDAR/TELEMETRY) from staging."""
    df = (
        spark.read.jdbc(
            url=JDBC_URL,
            table="raw_sensor_events_staging",
            properties=JDBC_PROPERTIES,
        )
        .filter(F.col("load_status") == "validated")
    )
    return df.select(*SENSOR_FIELDS)


# ── Transform: staging row -> Avro-schema-shaped record ─────────────────
# Pure DataFrame -> DataFrame functions, independent of how the input
# DataFrame was produced (JDBC batch today; Kafka + readStream later).

def transform_to_alice_schema(df: DataFrame) -> DataFrame:
    """
    Staging table -> alice_event_schema_v1.avsc shape.
    Column names and types already match 1:1 (staging_ingestion_script.py
    was built against this same schema) — this function exists as the
    single seam where any future divergence between staging and the Avro
    schema gets reconciled, rather than letting write_avro() do double duty.
    """
    return df.select(*ALICE_FIELDS)


def transform_to_sensor_schema(df: DataFrame) -> DataFrame:
    """
    Staging table -> sensor_schema_v1.avsc shape. Notably drops `label`
    and `anomaly_type` — those are ML-training ground-truth columns used
    later by Module 8/9, but they are NOT part of the locked Avro wire
    schema and must not be serialized here.
    """
    return df.select(*SENSOR_FIELDS)


# ── Fused event — stub, not implemented this week (see design note 4) ───

def write_fused_events(*_args, **_kwargs):
    raise NotImplementedError(
        "fused_event serialization requires the Module 6 stream-stream "
        "join (services/fusion/ is still an empty scaffold as of M4W14). "
        "Raise scope at M4W14T8 (Tuesday checkpoint) before implementing."
    )


# ── Write: Avro via fastavro, per-partition ──────────────────────────────

def _load_avro_schema(schema_filename: str) -> dict:
    from fastavro import parse_schema
    schema_path = SCHEMA_DIR / schema_filename
    with open(schema_path, "r", encoding="utf-8") as f:
        raw_schema = json.load(f)
    return parse_schema(raw_schema)


def _write_partition_to_avro(rows_iter, schema: dict, out_path: str, stream_name: str):
    """
    Runs on each Spark executor. Enforces schema-versioning (M4W14T3 —
    version population + round-trip check) on the partition's records
    before writing, then writes only the records that passed both checks
    using fastavro's block writer (avro.datafile.writer handles the file
    header + block framing; schemaless_writer is used inside the
    enforcement round-trip check itself, not for the standalone file).
    """
    from fastavro import writer as avro_writer
    from schema_versioning import enforce

    records = [row.asDict() for row in rows_iter]
    if not records:
        return iter([])

    result = enforce(records, stream_name, schema)

    if result.valid_records:
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "wb") as out_f:
            avro_writer(out_f, schema, result.valid_records)

    return iter([{
        "file": out_path if result.valid_records else None,
        "record_count": result.passed,
        "rejected_version_drift": len(result.version_drift),
        "rejected_round_trip_failed": len(result.round_trip_failed),
        "data_loss_pct": result.data_loss_pct,
    }])


def write_avro(df: DataFrame, schema_filename: str, stream_name: str) -> list:
    """
    Serializes a DataFrame to Avro files under OUTPUT_DIR/<stream_name>/,
    one file per Spark partition, after schema-versioning enforcement
    (M4W14T3) rejects any version-drifted or round-trip-failed records.
    Returns a list of per-partition result summaries (collected back to
    the driver) for logging/manifest purposes.
    """
    schema = _load_avro_schema(schema_filename)
    stream_dir = OUTPUT_DIR / stream_name

    # zipWithIndex via mapPartitionsWithIndex so each partition gets a
    # distinct, deterministic output filename.
    def _partition_writer(index, rows_iter):
        out_path = str(stream_dir / f"part-{index:05d}.avro")
        return _write_partition_to_avro(rows_iter, schema, out_path, stream_name)

    results = df.rdd.mapPartitionsWithIndex(_partition_writer).collect()
    return results


# ── Main ──────────────────────────────────────────────────────────────

def run_adaptation_job(schema_dir: str = "schemas", output_dir: str = "data/adaptation/avro"):
    global SCHEMA_DIR, OUTPUT_DIR
    SCHEMA_DIR = Path(schema_dir)
    OUTPUT_DIR = Path(output_dir)

    spark = get_spark_session()

    log.info("Reading ALICE staging records...")
    alice_df = transform_to_alice_schema(read_alice_staging(spark))
    alice_count = alice_df.count()
    log.info("ALICE records to serialize: %d", alice_count)
    alice_results = write_avro(alice_df, "alice_event_schema_v1.avsc", "alice_event")

    log.info("Reading sensor staging records...")
    sensor_df = transform_to_sensor_schema(read_sensor_staging(spark))
    sensor_count = sensor_df.count()
    log.info("Sensor records to serialize: %d", sensor_count)
    sensor_results = write_avro(sensor_df, "sensor_schema_v1.avsc", "sensor_event")

    log.info(
        "fused_event: SKIPPED — Module 6 fusion join not yet implemented. "
        "See M4W14T8 for scope decision."
    )

    summary = {
        "alice_event": {"records": alice_count, "files": alice_results},
        "sensor_event": {"records": sensor_count, "files": sensor_results},
        "fused_event": {"status": "skipped — fusion not implemented (M4W14T8)"},
    }
    log.info("Adaptation job summary: %s", json.dumps(summary, indent=2))

    spark.stop()
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="DataForge PySpark Adaptation Job")
    parser.add_argument("--schema-dir", default="schemas")
    parser.add_argument("--output-dir", default="data/adaptation/avro")
    args = parser.parse_args()

    run_adaptation_job(args.schema_dir, args.output_dir)
