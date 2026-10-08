"""
DataForge — PySpark Adaptation Job Scaffold (Avro Serialization)
Task: M4W14T2
Owner: Abdullah

"""

import argparse
import json
import logging
import os
from pathlib import Path

from pyspark.sql import SparkSession, DataFrame
from pyspark.sql import functions as F

# ── Logging ──────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
)
log = logging.getLogger(__name__)


DB_HOST = os.environ.get("DB_HOST", "localhost")

DB_PORT = os.environ.get("DB_PORT", "5433")
DB_NAME = os.environ.get("DB_NAME", "dataforge")
DB_USER = os.environ.get("DB_USER", "dataforge")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "dataforge_dev")

JDBC_URL = f"jdbc:postgresql://{DB_HOST}:{DB_PORT}/{DB_NAME}"
JDBC_PROPERTIES = {
    "user": DB_USER,
    "password": DB_PASSWORD,
    "driver": "org.postgresql.Driver",
}

SCHEMA_DIR = Path("schemas")
OUTPUT_DIR = Path("data/adaptation/avro")


ALICE_FIELDS = [
    "event_id",
    "run_number",
    "timestamp_ms",
    "track_count",
    "net_momentum_x",
    "net_momentum_y",
    "net_momentum_z",
    "max_energy_gev",
    "total_energy_gev",
    "schema_version",
]

SENSOR_FIELDS = [
    "event_id",
    "sensor_id",
    "sensor_type",
    "timestamp_ms",
    "target_id",
    "range_m",
    "bearing_deg",
    "elevation_deg",
    "velocity_ms",
    "signal_strength_db",
    "scan_id",
    "point_count",
    "centroid_x_m",
    "centroid_y_m",
    "centroid_z_m",
    "max_range_m",
    "avg_intensity",
    "min_intensity",
    "device_id",
    "parameter_name",
    "value",
    "unit",
    "sequence_number",
    "schema_version",
]


# ── Spark session ────────────────────────────────────────────────────────


def get_spark_session(app_name: str = "dataforge-adaptation-layer") -> SparkSession:
    spark = (
        SparkSession.builder.appName(app_name)
        # spark.read.jdbc() needs the actual Postgres JDBC driver on the
        # classpath — PySpark does not bundle one. Pulled from Maven at
        # session startup.
        .config("spark.jars.packages", "org.postgresql:postgresql:42.7.4")
        .config("spark.sql.session.timeZone", "UTC")
        .getOrCreate()
    )

    schema_versioning_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "schema_versioning.py"
    )
    spark.sparkContext.addPyFile(schema_versioning_path)

    spark.sparkContext.addPyFile(os.path.abspath(__file__))

    return spark


# ── Read: staging tables (JDBC) ──────────────────────────────────────────


def read_alice_staging(spark: SparkSession) -> DataFrame:
    """
    Reads validated ALICE records from raw_alice_events_staging.
    Only load_status='validated' rows are read — staging_ingestion_script.py
    only ever inserts validated rows, but this filter is defensive in case
    that invariant changes upstream.
    """
    df = spark.read.jdbc(
        url=JDBC_URL,
        table="raw_alice_events_staging",
        properties=JDBC_PROPERTIES,
    ).filter(F.col("load_status") == "validated")
    return df.select(*ALICE_FIELDS)


def read_sensor_staging(spark: SparkSession) -> DataFrame:
    """Reads validated sensor records (RADAR/LIDAR/TELEMETRY) from staging."""
    df = spark.read.jdbc(
        url=JDBC_URL,
        table="raw_sensor_events_staging",
        properties=JDBC_PROPERTIES,
    ).filter(F.col("load_status") == "validated")
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
        "Superseded by services/fusion/fused_writer.py (M6W22T2), which "
        "implements this against the real Module 6 join output. This stub "
        "stays here only as a pointer — M4 Item 4 is closed "
        "(docs/milestones/milestone4/open_items_m4.md)."
    )


# ── Write: Avro via fastavro, per-partition ──────────────────────────────


def _load_avro_schema(schema_filename: str) -> dict:
    from fastavro import parse_schema

    schema_path = SCHEMA_DIR / schema_filename
    with open(schema_path, "r", encoding="utf-8") as f:
        raw_schema = json.load(f)
    return parse_schema(raw_schema)


def _write_partition_to_avro(
    rows_iter,
    schema: dict,
    out_path: str,
    stream_name: str,
    collect_timings: bool = False,
):

    from fastavro import writer as avro_writer
    from schema_versioning import enforce

    records = [row.asDict() for row in rows_iter]
    if not records:
        return iter([])

    result = enforce(records, stream_name, schema, collect_timings=collect_timings)

    if result.valid_records:
        Path(out_path).parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "wb") as out_f:
            avro_writer(out_f, schema, result.valid_records)

    return iter(
        [
            {
                "file": out_path if result.valid_records else None,
                "record_count": result.passed,
                "rejected_version_drift": len(result.version_drift),
                "rejected_round_trip_failed": len(result.round_trip_failed),
                "data_loss_pct": result.data_loss_pct,
                "record_latencies_ms": (
                    result.record_latencies_ms if collect_timings else []
                ),
            }
        ]
    )


def write_avro(
    df: DataFrame, schema_filename: str, stream_name: str, collect_timings: bool = False
) -> list:

    schema = _load_avro_schema(schema_filename)
    stream_dir = OUTPUT_DIR / stream_name

    # zipWithIndex via mapPartitionsWithIndex so each partition gets a
    # distinct, deterministic output filename.
    def _partition_writer(index, rows_iter):
        out_path = str(stream_dir / f"part-{index:05d}.avro")
        return _write_partition_to_avro(
            rows_iter, schema, out_path, stream_name, collect_timings=collect_timings
        )

    results = df.rdd.mapPartitionsWithIndex(_partition_writer).collect()
    return results


# ── Main ──────────────────────────────────────────────────────────────


def run_adaptation_job(
    schema_dir: str = "schemas", output_dir: str = "data/adaptation/avro"
):
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
