"""
DataForge — Parquet Writer Stage

Task: M4W14T4

Reads Avro output produced by the adaptation layer and converts it
to Parquet datasets for the storage layer.

Supported streams:
- ALICE
- RADAR
- LIDAR
- TELEMETRY

The Avro serialization stage remains responsible for schema validation
and schema-version enforcement. This module only converts validated
Avro output into Parquet storage datasets.
"""

import argparse
import logging
from pathlib import Path
from typing import Any, Optional

from fastavro import reader as avro_reader
from pyspark.sql import DataFrame, SparkSession
from pyspark.sql import functions as F

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
# Configure a simple logger so conversion progress and record counts
# are visible when the writer is executed from the command line.

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
)

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Default input and output locations
# ---------------------------------------------------------------------------
# The Avro adaptation job writes validated records under AVRO_INPUT_DIR.
# This writer converts those records into Parquet datasets under
# PARQUET_OUTPUT_DIR.

AVRO_INPUT_DIR = Path("data/adaptation/avro")
PARQUET_OUTPUT_DIR = Path("data/adaptation/parquet")


# ---------------------------------------------------------------------------
# Spark session
# ---------------------------------------------------------------------------


def get_spark_session(
    app_name: str = "dataforge-parquet-writer",
) -> SparkSession:
    """
    Create the Spark session used for Parquet generation.

    Spark is used only for DataFrame processing and Parquet output.
    Avro files are read with fastavro so this stage does not require
    the external spark-avro package.
    """

    return (
        SparkSession.builder.appName(app_name)
        .config("spark.sql.session.timeZone", "UTC")
        .getOrCreate()
    )


# ---------------------------------------------------------------------------
# Avro input discovery
# ---------------------------------------------------------------------------


def discover_avro_files(input_dir: Path) -> list[Path]:
    """
    Find all Avro files inside a stream-specific input directory.

    The adaptation job writes one Avro file per Spark partition using
    deterministic names such as part-00000.avro.
    """

    if not input_dir.exists():
        return []

    return sorted(input_dir.glob("*.avro"))


# ---------------------------------------------------------------------------
# Avro reader
# ---------------------------------------------------------------------------


def read_avro_records(input_dir: Path) -> list[dict[str, Any]]:
    """
    Read all Avro records from a stream directory.

    fastavro is used because it is already part of the adaptation-layer
    dependency set and avoids introducing a separate Spark Avro package.

    Each returned item is a normal Python dictionary that can later be
    converted into a Spark DataFrame.
    """

    records: list[dict[str, Any]] = []

    avro_files = discover_avro_files(input_dir)

    for avro_file in avro_files:
        log.info("Reading Avro file: %s", avro_file)

        with avro_file.open("rb") as input_file:
            records.extend(dict(record) for record in avro_reader(input_file))

    return records


# ---------------------------------------------------------------------------
# Spark DataFrame conversion
# ---------------------------------------------------------------------------


def records_to_dataframe(
    spark: SparkSession,
    records: list[dict[str, Any]],
) -> Optional[DataFrame]:
    """
    Convert Avro records into a Spark DataFrame.

    None is returned when the input contains no records. This prevents
    Spark from attempting to infer a schema from an empty collection.
    """

    if not records:
        return None

    return spark.createDataFrame(records)


# ---------------------------------------------------------------------------
# Generic Parquet output
# ---------------------------------------------------------------------------


def write_dataframe_to_parquet(
    df: DataFrame,
    output_dir: Path,
) -> int:
    """
    Write a Spark DataFrame as a Parquet dataset.

    Overwrite mode keeps repeated local verification runs deterministic
    and prevents previous test output from being mixed with a new run.

    The function returns the number of records written so the caller can
    include it in the final conversion summary.
    """

    record_count = df.count()

    output_dir.parent.mkdir(parents=True, exist_ok=True)

    df.write.mode("overwrite").parquet(str(output_dir))

    return record_count


# ---------------------------------------------------------------------------
# ALICE conversion
# ---------------------------------------------------------------------------


def convert_alice_to_parquet(
    spark: SparkSession,
    avro_root: Path,
    parquet_root: Path,
) -> int:
    """
    Convert validated ALICE Avro records into an ALICE Parquet dataset.
    """

    input_dir = avro_root / "alice_event"
    output_dir = parquet_root / "alice_event"

    records = read_avro_records(input_dir)

    if not records:
        log.warning("No ALICE Avro records found in %s", input_dir)
        return 0

    df = records_to_dataframe(spark, records)

    if df is None:
        return 0

    count = write_dataframe_to_parquet(df, output_dir)

    log.info(
        "ALICE Parquet conversion complete: %d records written to %s",
        count,
        output_dir,
    )

    return count


# ---------------------------------------------------------------------------
# Sensor conversion
# ---------------------------------------------------------------------------


def convert_sensor_streams_to_parquet(
    spark: SparkSession,
    avro_root: Path,
    parquet_root: Path,
) -> dict[str, int]:
    """
    Convert the unified sensor Avro stream into separate Parquet datasets.

    The locked sensor schema stores RADAR, LIDAR, and TELEMETRY records in
    one unified record structure. The sensor_type field identifies which
    sensor stream each record belongs to.

    This stage separates the unified Avro input into three storage datasets:
    radar, lidar, and telemetry.
    """

    input_dir = avro_root / "sensor_event"

    records = read_avro_records(input_dir)

    if not records:
        log.warning("No sensor Avro records found in %s", input_dir)
        return {
            "radar": 0,
            "lidar": 0,
            "telemetry": 0,
        }

    df = records_to_dataframe(spark, records)

    if df is None:
        return {
            "radar": 0,
            "lidar": 0,
            "telemetry": 0,
        }

    results: dict[str, int] = {}

    # Map the schema-level sensor discriminator to the directory name
    # used by the Parquet storage layer.
    sensor_streams = {
        "RADAR": "radar",
        "LIDAR": "lidar",
        "TELEMETRY": "telemetry",
    }

    for sensor_type, output_name in sensor_streams.items():
        # Keep only records belonging to the current sensor stream.
        stream_df = df.filter(F.col("sensor_type") == sensor_type)

        # Store each sensor stream in its own Parquet dataset.
        output_dir = parquet_root / output_name

        count = write_dataframe_to_parquet(
            stream_df,
            output_dir,
        )

        results[output_name] = count

        log.info(
            "%s Parquet conversion complete: %d records written to %s",
            sensor_type,
            count,
            output_dir,
        )

    return results


# ---------------------------------------------------------------------------
# Parquet writer orchestration
# ---------------------------------------------------------------------------


def run_parquet_writer(
    avro_input_dir: str = "data/adaptation/avro",
    parquet_output_dir: str = "data/adaptation/parquet",
) -> dict[str, Any]:
    """
    Run the complete Avro-to-Parquet conversion stage.

    ALICE records are written to one Parquet dataset.

    Sensor records are read from the unified sensor Avro stream and split
    into RADAR, LIDAR, and TELEMETRY Parquet datasets.

    A summary dictionary is returned for logging, verification, and future
    pipeline integration.
    """

    avro_root = Path(avro_input_dir)
    parquet_root = Path(parquet_output_dir)

    spark = get_spark_session()

    try:
        log.info("Starting ALICE Avro-to-Parquet conversion.")

        alice_count = convert_alice_to_parquet(
            spark,
            avro_root,
            parquet_root,
        )

        log.info("Starting sensor Avro-to-Parquet conversion.")

        sensor_counts = convert_sensor_streams_to_parquet(
            spark,
            avro_root,
            parquet_root,
        )

        summary = {
            "alice_event": alice_count,
            "radar": sensor_counts["radar"],
            "lidar": sensor_counts["lidar"],
            "telemetry": sensor_counts["telemetry"],
        }

        log.info("Parquet writer summary: %s", summary)

        return summary

    finally:
        # Always stop Spark, including when a conversion raises an error.
        spark.stop()


# ---------------------------------------------------------------------------
# Command-line entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """
    Parse command-line arguments and execute the Parquet writer stage.
    """

    parser = argparse.ArgumentParser(
        description="Convert DataForge adaptation-layer Avro output to Parquet."
    )

    parser.add_argument(
        "--avro-input-dir",
        default=str(AVRO_INPUT_DIR),
        help="Root directory containing adaptation-layer Avro output.",
    )

    parser.add_argument(
        "--parquet-output-dir",
        default=str(PARQUET_OUTPUT_DIR),
        help="Root directory where Parquet datasets will be written.",
    )

    args = parser.parse_args()

    run_parquet_writer(
        avro_input_dir=args.avro_input_dir,
        parquet_output_dir=args.parquet_output_dir,
    )


if __name__ == "__main__":
    main()
