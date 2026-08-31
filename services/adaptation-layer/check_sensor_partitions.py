"""
DataForge — M4W16T3 Diagnostic: Sensor DataFrame Partition Check

Confirms the actual Spark partition count used for the sensor DataFrame
during the M4W15T4 full-volume run, to verify the single-task hypothesis
logged in open_items_m4.md Item 5.

Reuses parquet_writer.py's own read_avro_records() and
records_to_dataframe() functions unmodified, so this checks the exact
same DataFrame construction path that produced the 1,665.56 events/sec
result — not a re-implementation that might partition differently.

Run this from the services/adaptation-layer/ directory (or adjust
sys.path below) against the M4W15T4 run's existing Avro output at
data/adaptation/avro/sensor_event/.

Usage:
    cd services/adaptation-layer
    python check_sensor_partitions.py
"""

import logging
from pathlib import Path

from parquet_writer import get_spark_session, read_avro_records, records_to_dataframe

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s")
log = logging.getLogger(__name__)

AVRO_SENSOR_DIR = Path("data/adaptation/avro/sensor_event")


def main() -> None:
    spark = get_spark_session()

    try:
        log.info("Reading sensor Avro records from %s", AVRO_SENSOR_DIR)
        records = read_avro_records(AVRO_SENSOR_DIR)
        log.info("Records read: %d", len(records))

        df = records_to_dataframe(spark, records)

        if df is None:
            log.warning("No records found — cannot check partition count.")
            return

        # getNumPartitions() is metadata only — no Spark job is triggered,
        # so this is safe even if a later, heavier check fails.
        num_partitions = df.rdd.getNumPartitions()
        default_parallelism = spark.sparkContext.defaultParallelism

        log.info("=== M4W16T3 Partition Check Result (primary) ===")
        log.info("df.rdd.getNumPartitions(): %d", num_partitions)
        log.info("spark.sparkContext.defaultParallelism: %d", default_parallelism)
        log.info("Total records read from Avro: %d", len(records))

        # Per-partition record counts are informative but require pulling
        # full partition contents back to the driver (glom + collect),
        # which is a heavier, more failure-prone operation on this data
        # volume. Wrapped separately so a crash here doesn't cost us the
        # primary numbers already logged above.
        try:
            partition_counts = df.rdd.glom().map(len).collect()
            log.info("=== Per-partition record counts (secondary) ===")
            log.info("Per-partition record counts: %s", partition_counts)
        except Exception as exc:
            log.warning(
                "Per-partition breakdown failed (primary numbers above are "
                "still valid): %s",
                exc,
            )

    finally:
        spark.stop()


if __name__ == "__main__":
    main()
