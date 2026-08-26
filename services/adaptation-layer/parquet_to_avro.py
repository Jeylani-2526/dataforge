"""
DataForge — Parquet-to-Avro Reverse Conversion
Task: M4W15T3
Owner: Abdullah

Adds the missing Parquet -> Avro leg (the reverse of
avro_adaptation_job.py -> parquet_writer.py), needed for the
Avro -> Parquet -> Avro round-trip test suite and for any future
consumer re-deriving Avro from Parquet storage.

Conventions mirror parquet_writer.py: Spark reads the Parquet dataset
(it was written via Spark), fastavro writes the Avro output (project's
one Avro library, already pinned in requirements.txt).

Note — enum re-encoding: sensor_type round-trips through Parquet as a
plain Spark string (Spark has no Avro-enum concept). fastavro validates
it against the schema's enum symbols at write time, so a bad value fails
loudly rather than being silently miswritten.
"""

import logging
from pathlib import Path
from typing import Any

from fastavro import writer as avro_writer
from pyspark.sql import DataFrame, SparkSession

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Parquet input discovery / read
# ---------------------------------------------------------------------------


def read_parquet_records(spark: SparkSession, input_dir: Path) -> list[dict[str, Any]]:
    """
    Reads a Parquet dataset (written by parquet_writer.py) back into a
    list of plain Python dicts, in the field order the DataFrame reports.

    Returns an empty list — not an error — when the directory doesn't
    exist or contains no data, matching parquet_writer.read_avro_records'
    empty-input convention so callers can treat "no records" uniformly
    across both conversion directions.
    """
    if not input_dir.exists():
        return []

    df: DataFrame = spark.read.parquet(str(input_dir))
    return [row.asDict(recursive=True) for row in df.collect()]


# ---------------------------------------------------------------------------
# Avro write (schema-ordered)
# ---------------------------------------------------------------------------


def _reorder_to_schema(record: dict[str, Any], field_order: list[str]) -> dict[str, Any]:
    """
    Parquet column order is not guaranteed to match the locked .avsc
    field order (Spark's schema inference from records_to_dataframe()
    follows dict-insertion / alphabetical behavior, not the Avro schema).
    fastavro's container writer needs a dict with the right keys/values —
    it does not require positional field order the way the *schemaless*
    writer used in schema_versioning.py's round_trip_check does — but
    re-keying explicitly here guards against a record silently missing a
    field (e.g. a column dropped during Parquet round-trip) rather than
    letting fastavro raise a less specific error deeper in the write.
    """
    return {field: record.get(field) for field in field_order}


def write_records_to_avro(
    records: list[dict[str, Any]],
    parsed_schema: dict,
    field_order: list[str],
    output_path: Path,
) -> int:
    """
    Serializes records back to a single Avro Object Container File at
    output_path, using fastavro's block writer — the same writer
    avro_adaptation_job.py's _write_partition_to_avro() uses for the
    original Avro output, so a file produced by this module is
    indistinguishable in format from one produced by the adaptation job
    itself.

    Returns the number of records written.
    """
    if not records:
        return 0

    ordered = [_reorder_to_schema(rec, field_order) for rec in records]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as out_f:
        avro_writer(out_f, parsed_schema, ordered)

    return len(ordered)


# ---------------------------------------------------------------------------
# Orchestration: Parquet directory -> Avro file
# ---------------------------------------------------------------------------


def convert_parquet_to_avro(
    spark: SparkSession,
    parquet_dir: Path,
    parsed_schema: dict,
    field_order: list[str],
    output_path: Path,
) -> int:
    """
    Full Parquet -> Avro leg for one stream: read the Parquet dataset,
    re-key each record to the schema's field order, and write a single
    Avro Object Container File. Returns the record count written.
    """
    records = read_parquet_records(spark, parquet_dir)

    if not records:
        log.warning("No Parquet records found in %s", parquet_dir)
        return 0

    count = write_records_to_avro(records, parsed_schema, field_order, output_path)

    log.info(
        "Parquet-to-Avro conversion complete: %d records written to %s",
        count,
        output_path,
    )

    return count
