"""
DataForge — Full-Volume Pipeline Run & Throughput Report
Task: M4W15T4
Owner: Abdullah

Runs the adaptation pipeline (avro_adaptation_job -> parquet_writer) at
the full committed volume — 68 ALICE + 150,000 sensor records, using
Omer's M4W15T1 trimmed staging data — and reports throughput, p95
latency, and data-loss percentage against the locked prototype bar:

    Throughput  >= 10,000 events/sec
    Latency p95 <= 500 ms
    Data loss   <= 1%

(source: docs/requirements/prototype_performance_bar_final.docx,
"Prototype Bar" column)

── What "latency" means here (read before interpreting results) ────────
There is no live event stream yet — Kafka + Structured Streaming is
M5's deliverable, not M4's. So there is no true per-event
ingest-to-output latency to measure this milestone. What IS measurable,
and what this script measures, is the per-record processing time inside
the adaptation layer's actual unit of work: schema_versioning.py's
serialize -> deserialize -> compare round-trip check (M4W14T3), timed
individually per record via the collect_timings option added for this
task (see schema_versioning.enforce()/round_trip_check()). This is
reported as "per-record round-trip processing latency," not relabeled
as network or streaming latency — an honest proxy for this milestone,
not the M5 metric.

── What "throughput" means here ─────────────────────────────────────────
Total valid (passed) records across both streams, divided by total
wall-clock seconds for the whole run: staging read -> transform ->
schema enforcement -> Avro write -> Parquet write. This is an
end-to-end batch throughput figure, not a steady-state streaming rate.

Usage:
    python full_volume_run.py

Writes results to:
    data/adaptation/full_volume_run_summary.json (raw numbers)
    docs/data/full_volume_run_m4w15t4.md         (report, human-readable)
"""

import json
import logging
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path

from avro_adaptation_job import (
    get_spark_session,
    read_alice_staging,
    read_sensor_staging,
    transform_to_alice_schema,
    transform_to_sensor_schema,
    write_avro,
)
from parquet_writer import convert_alice_to_parquet, convert_sensor_streams_to_parquet

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
)
log = logging.getLogger(__name__)

# ── Prototype bar (locked, M1 — do not edit without a scope change) ─────
THROUGHPUT_BAR_EVENTS_PER_SEC = 10_000
LATENCY_P95_BAR_MS = 500
DATA_LOSS_BAR_PCT = 1.0

# ── Expected volumes (locked M4 spec, post M4W15T1 trim) ────────────────
EXPECTED_ALICE_COUNT = 68
EXPECTED_SENSOR_COUNT = 150_000

AVRO_OUTPUT_DIR = Path("data/adaptation/avro")
PARQUET_OUTPUT_DIR = Path("data/adaptation/parquet")
JSON_SUMMARY_PATH = Path("data/adaptation/full_volume_run_summary.json")
REPORT_PATH = Path("docs/data/full_volume_run_m4w15t4.md")


def _percentile(values: list, pct: float) -> float:
    """
    Nearest-rank percentile over a plain Python list — no numpy
    dependency needed for a single report script. statistics.quantiles
    (n=100) gives the same result for pct in [1, 99] and is stdlib.
    """
    if not values:
        return 0.0
    if len(values) == 1:
        return values[0]
    quantiles = statistics.quantiles(values, n=100, method="inclusive")
    # quantiles[i] is the (i+1)-th percentile, e.g. quantiles[94] = p95
    idx = min(max(int(round(pct)) - 1, 0), 98)
    return quantiles[idx]


def _aggregate_partition_results(results: list) -> dict:
    """
    Aggregates the list of per-partition summary dicts write_avro()
    returns (one dict per Spark partition) into stream-level totals:
    records passed, records rejected by each check, and every
    per-record latency collected across all partitions of the stream.
    """
    total_passed = sum(r["record_count"] for r in results)
    total_version_drift = sum(r["rejected_version_drift"] for r in results)
    total_round_trip_failed = sum(r["rejected_round_trip_failed"] for r in results)
    latencies = [ms for r in results for ms in r.get("record_latencies_ms", [])]
    return {
        "passed": total_passed,
        "rejected_version_drift": total_version_drift,
        "rejected_round_trip_failed": total_round_trip_failed,
        "latencies_ms": latencies,
    }


def run_full_volume_pipeline() -> dict:
    run_started_at = datetime.now(timezone.utc).isoformat()
    wall_clock_start = time.perf_counter()

    spark = get_spark_session()

    log.info("=== M4W15T4: Full-volume pipeline run starting ===")

    # ── ALICE stream ──────────────────────────────────────────────────
    log.info("Reading ALICE staging records...")
    alice_df = transform_to_alice_schema(read_alice_staging(spark))
    alice_staging_count = alice_df.count()
    log.info("ALICE records read from staging: %d", alice_staging_count)

    alice_results = write_avro(
        alice_df, "alice_event_schema_v1.avsc", "alice_event", collect_timings=True
    )

    # ── Sensor stream ─────────────────────────────────────────────────
    log.info("Reading sensor staging records...")
    sensor_df = transform_to_sensor_schema(read_sensor_staging(spark))
    sensor_staging_count = sensor_df.count()
    log.info("Sensor records read from staging: %d", sensor_staging_count)

    sensor_results = write_avro(
        sensor_df, "sensor_schema_v1.avsc", "sensor_event", collect_timings=True
    )

    # ── Parquet conversion (existing M4W14T4 writer, unmodified) ───────
    log.info("Converting Avro output to Parquet...")
    alice_parquet_count = convert_alice_to_parquet(spark, AVRO_OUTPUT_DIR, PARQUET_OUTPUT_DIR)
    sensor_parquet_counts = convert_sensor_streams_to_parquet(
        spark, AVRO_OUTPUT_DIR, PARQUET_OUTPUT_DIR
    )

    wall_clock_seconds = time.perf_counter() - wall_clock_start
    spark.stop()

    # ── Aggregate metrics across both streams ───────────────────────────
    alice_agg = _aggregate_partition_results(alice_results)
    sensor_agg = _aggregate_partition_results(sensor_results)

    total_input = alice_staging_count + sensor_staging_count
    total_passed = alice_agg["passed"] + sensor_agg["passed"]
    total_rejected = (
        alice_agg["rejected_version_drift"]
        + alice_agg["rejected_round_trip_failed"]
        + sensor_agg["rejected_version_drift"]
        + sensor_agg["rejected_round_trip_failed"]
    )
    all_latencies_ms = alice_agg["latencies_ms"] + sensor_agg["latencies_ms"]

    data_loss_pct = round(100.0 * total_rejected / total_input, 4) if total_input else 0.0
    throughput_events_per_sec = (
        round(total_passed / wall_clock_seconds, 2) if wall_clock_seconds else 0.0
    )
    p95_latency_ms = round(_percentile(all_latencies_ms, 95), 4)
    p50_latency_ms = round(_percentile(all_latencies_ms, 50), 4)
    p99_latency_ms = round(_percentile(all_latencies_ms, 99), 4)

    volume_check = {
        "alice_matches_spec": alice_staging_count == EXPECTED_ALICE_COUNT,
        "sensor_matches_spec": sensor_staging_count == EXPECTED_SENSOR_COUNT,
        "expected_alice": EXPECTED_ALICE_COUNT,
        "expected_sensor": EXPECTED_SENSOR_COUNT,
        "actual_alice": alice_staging_count,
        "actual_sensor": sensor_staging_count,
    }

    bar_check = {
        "throughput_pass": throughput_events_per_sec >= THROUGHPUT_BAR_EVENTS_PER_SEC,
        "latency_p95_pass": p95_latency_ms <= LATENCY_P95_BAR_MS,
        "data_loss_pass": data_loss_pct <= DATA_LOSS_BAR_PCT,
    }

    summary = {
        "run_started_at_utc": run_started_at,
        "wall_clock_seconds": round(wall_clock_seconds, 3),
        "volume_check": volume_check,
        "streams": {
            "alice_event": {
                "staging_count": alice_staging_count,
                "passed": alice_agg["passed"],
                "rejected_version_drift": alice_agg["rejected_version_drift"],
                "rejected_round_trip_failed": alice_agg["rejected_round_trip_failed"],
                "parquet_written": alice_parquet_count,
            },
            "sensor_event": {
                "staging_count": sensor_staging_count,
                "passed": sensor_agg["passed"],
                "rejected_version_drift": sensor_agg["rejected_version_drift"],
                "rejected_round_trip_failed": sensor_agg["rejected_round_trip_failed"],
                "parquet_written_by_type": sensor_parquet_counts,
            },
        },
        "totals": {
            "total_input_records": total_input,
            "total_passed_records": total_passed,
            "total_rejected_records": total_rejected,
        },
        "metrics": {
            "throughput_events_per_sec": throughput_events_per_sec,
            "latency_p50_ms": p50_latency_ms,
            "latency_p95_ms": p95_latency_ms,
            "latency_p99_ms": p99_latency_ms,
            "data_loss_pct": data_loss_pct,
            "latency_sample_size": len(all_latencies_ms),
        },
        "prototype_bar": {
            "throughput_bar_events_per_sec": THROUGHPUT_BAR_EVENTS_PER_SEC,
            "latency_p95_bar_ms": LATENCY_P95_BAR_MS,
            "data_loss_bar_pct": DATA_LOSS_BAR_PCT,
        },
        "bar_check": bar_check,
        "bar_check_all_pass": all(bar_check.values()),
    }

    log.info("=== Full-volume run summary ===")
    log.info(json.dumps(summary, indent=2))

    JSON_SUMMARY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(JSON_SUMMARY_PATH, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    log.info("Raw summary written to %s", JSON_SUMMARY_PATH)

    _write_markdown_report(summary)

    return summary


def _write_markdown_report(summary: dict) -> None:
    v = summary["volume_check"]
    m = summary["metrics"]
    b = summary["bar_check"]
    p = summary["prototype_bar"]

    def check_mark(passed: bool) -> str:
        return "PASS" if passed else "FAIL"

    lines = [
        "# DataForge — Full-Volume Pipeline Run Report",
        "",
        "**Task:** M4W15T4",
        "**Owner:** Abdullah",
        f"**Run timestamp (UTC):** {summary['run_started_at_utc']}",
        f"**Wall-clock duration:** {summary['wall_clock_seconds']} s",
        "",
        "---",
        "",
        "## Volume check (against M4W15T1's trimmed spec)",
        "",
        "| Stream | Expected | Actual | Match |",
        "|---|---|---|---|",
        f"| ALICE | {v['expected_alice']} | {v['actual_alice']} | "
        f"{check_mark(v['alice_matches_spec'])} |",
        f"| Sensor (RADAR+LIDAR+TELEMETRY) | {v['expected_sensor']} | "
        f"{v['actual_sensor']} | {check_mark(v['sensor_matches_spec'])} |",
        "",
        "---",
        "",
        "## Results vs. locked prototype bar",
        "",
        "| Metric | Bar | Result | Status |",
        "|---|---|---|---|",
        f"| Throughput | >= {p['throughput_bar_events_per_sec']:,} events/sec | "
        f"{m['throughput_events_per_sec']:,} events/sec | "
        f"{check_mark(b['throughput_pass'])} |",
        f"| Latency (p95) | <= {p['latency_p95_bar_ms']} ms | "
        f"{m['latency_p95_ms']} ms | {check_mark(b['latency_p95_pass'])} |",
        f"| Data loss | <= {p['data_loss_bar_pct']}% | "
        f"{m['data_loss_pct']}% | {check_mark(b['data_loss_pass'])} |",
        "",
    ]

    overall_status = "ALL BARS MET" if summary["bar_check_all_pass"] else (
        "ONE OR MORE BARS NOT MET — see Week 16 open item"
    )
    lines.append(f"**Overall: {overall_status}**")
    lines += [
        "",
        "---",
        "",
        "## Latency methodology (read before citing these numbers elsewhere)",
        "",
        "There is no live event stream in M4 — Kafka + Structured Streaming "
        "is M5's deliverable. \"Latency\" here is the per-record processing "
        "time inside the adaptation layer's actual unit of work: "
        "`schema_versioning.py`'s serialize -> deserialize -> compare "
        "round-trip check (M4W14T3), timed individually per record. This is "
        "an honest proxy for this milestone's batch pipeline, not the "
        "streaming-latency metric M5 will measure end-to-end.",
        "",
        f"- p50: {m['latency_p50_ms']} ms",
        f"- p95: {m['latency_p95_ms']} ms",
        f"- p99: {m['latency_p99_ms']} ms",
        f"- Sample size: {m['latency_sample_size']:,} per-record timings "
        f"(all passed + failed round-trip attempts across both streams)",
        "",
        "---",
        "",
        "## Per-stream breakdown",
        "",
        "| Stream | Staging count | Passed | Rejected (version drift) | "
        "Rejected (round-trip) | Parquet written |",
        "|---|---|---|---|---|---|",
    ]

    alice = summary["streams"]["alice_event"]
    sensor = summary["streams"]["sensor_event"]
    lines.append(
        f"| ALICE | {alice['staging_count']} | {alice['passed']} | "
        f"{alice['rejected_version_drift']} | {alice['rejected_round_trip_failed']} | "
        f"{alice['parquet_written']} |"
    )
    lines.append(
        f"| Sensor | {sensor['staging_count']} | {sensor['passed']} | "
        f"{sensor['rejected_version_drift']} | {sensor['rejected_round_trip_failed']} | "
        f"{sensor['parquet_written_by_type']} |"
    )

    lines += [
        "",
        "---",
        "",
        "## Raw data",
        "",
        f"Full machine-readable summary: `{JSON_SUMMARY_PATH}`",
        "",
    ]

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    log.info("Markdown report written to %s", REPORT_PATH)


if __name__ == "__main__":
    run_full_volume_pipeline()
