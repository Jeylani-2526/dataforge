"""
DataForge — Adaptation Layer Local Smoke Test
Task: M4W14T5

Runs avro_adaptation_job.py (M4W14T2/T3) then parquet_writer.py (M4W14T4)
in sequence and writes a combined result summary to
data/adaptation/smoke_test_summary.json — the evidence artifact for
"confirmed runnable" (record counts per stream, rejected records from
schema_versioning enforcement).
"""

import json
import logging
from pathlib import Path

from avro_adaptation_job import run_adaptation_job
from parquet_writer import run_parquet_writer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
)
log = logging.getLogger(__name__)

SUMMARY_PATH = Path("data/adaptation/smoke_test_summary.json")


def main() -> None:
    log.info("=== Smoke test: avro_adaptation_job ===")
    avro_summary = run_adaptation_job()

    log.info("=== Smoke test: parquet_writer ===")
    parquet_summary = run_parquet_writer()

    combined = {
        "avro_adaptation_job": avro_summary,
        "parquet_writer": parquet_summary,
    }

    SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(SUMMARY_PATH, "w", encoding="utf-8") as f:
        json.dump(combined, f, indent=2)

    log.info("Smoke test summary written to %s", SUMMARY_PATH)
    log.info(json.dumps(combined, indent=2))


if __name__ == "__main__":
    main()
