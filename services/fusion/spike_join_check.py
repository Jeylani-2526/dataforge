"""
M6W22T1 join spike — verifies the Section 12 checks against the real functions.

File sources stand in for Kafka, same as the design note's own spike. Run with
WATERMARK_DELAY_SECONDS=2 for a short test cycle. Not part of the service.
"""

import json
import os
import shutil
import sys
import tempfile
import time

os.environ.setdefault("WATERMARK_DELAY_SECONDS", "2")
os.environ.setdefault("FUSION_TRIGGER_SECONDS", "1")

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, expr
from pyspark.sql.types import StringType, StructField, StructType, LongType

import fusion_engine as fe

SCHEMA = StructType(
    [
        StructField("key", StringType()),
        StructField("ms", LongType()),
    ]
)

BASE = 1_760_000_000_000  # fixed epoch ms so cases are deterministic

results = []


def _src(spark, path):
    """File source shaped like the Kafka frame: key + timestamp."""
    return (
        spark.readStream.schema(SCHEMA)
        .json(path)
        .withColumn("timestamp", expr("timestamp_millis(ms)"))
        .select("key", "timestamp")
    )


def _wait_idle(q, settle_checks=3, poll_interval=0.5, max_wait=30):
    """Waits until the query has no batch in flight and hasn't started a new
    one for a few consecutive polls, instead of guessing a fixed sleep.

    A fixed sleep tuned for one machine races on a slower one: stopping the
    query while foreachBatch's collect() is still running raises an
    InterruptedException and silently drops that batch's output. Polling
    q.status/q.lastProgress avoids that regardless of machine speed.
    """
    last_batch_id, stable, waited = None, 0, 0.0
    while waited < max_wait:
        time.sleep(poll_interval)
        waited += poll_interval
        if q.status.get("isTriggerActive"):
            stable = 0
            continue
        batch_id = (q.lastProgress or {}).get("batchId")
        if batch_id == last_batch_id:
            stable += 1
            if stable >= settle_checks:
                return
        else:
            stable = 0
            last_batch_id = batch_id


def _write(path, rows):
    os.makedirs(path, exist_ok=True)
    name = os.path.join(path, f"b{int(time.time()*1000)}_{len(os.listdir(path))}.json")
    with open(name, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


def run_case(name, alice_rows, sensor_batches, expect):
    """sensor_batches: list of batches, each written one trigger apart."""
    tmp = tempfile.mkdtemp()
    a_dir, r_dir, l_dir, t_dir = (os.path.join(tmp, d) for d in ("a", "r", "l", "t"))
    for d in (a_dir, r_dir, l_dir, t_dir):
        os.makedirs(d, exist_ok=True)

    spark = (
        SparkSession.builder.appName(f"spike-{name}")
        .master("local[2]")
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.sql.shuffle.partitions", "2")
        .config("spark.sql.streaming.multipleWatermarkPolicy", "min")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("ERROR")

    alice = fe.prepare_alice(_src(spark, a_dir))
    sensors = fe.union_sensors(
        [
            fe.prepare_sensor(_src(spark, r_dir), "RADAR"),
            fe.prepare_sensor(_src(spark, l_dir), "LIDAR"),
            fe.prepare_sensor(_src(spark, t_dir), "TELEMETRY"),
        ]
    )
    fused = fe.select_nearest(fe.build_candidate_pairs(alice, sensors))

    collected = []
    q = (
        fused.writeStream.outputMode("append")
        .foreachBatch(
            lambda df, _: collected.extend([r.asDict() for r in df.collect()])
        )
        .trigger(processingTime="1 second")
        .option("checkpointLocation", os.path.join(tmp, "ckpt"))
        .start()
    )

    _write(a_dir, alice_rows)
    _wait_idle(q)
    for batch in sensor_batches:
        for topic_dir, rows in batch:
            if rows:
                _write(topic_dir if isinstance(topic_dir, str) else r_dir, rows)
        _wait_idle(q)

    # Push the watermark past every window so the append-mode aggregation emits.
    # Both sides must advance: under the min policy the global watermark is the
    # minimum across inputs, so flushing only the sensor side leaves the ALICE
    # watermark frozen and nothing is ever emitted (design note Section 5).
    # Every input must advance, including LIDAR and TELEMETRY. A stream that has
    # never seen a record has no watermark, so under the min policy the global
    # watermark never moves and the aggregation never emits.
    for i, offset in enumerate((60_000, 120_000, 180_000)):
        for d in (a_dir, r_dir, l_dir, t_dir):
            _write(d, [{"key": f"flush_{i}", "ms": BASE + offset}])
        _wait_idle(q)

    # One more idle check immediately before stop, in case the last _wait_idle
    # caught the query between batches rather than truly done (q.stop() racing
    # a still-running foreachBatch raises InterruptedException and silently
    # drops that batch's output — this is what a fixed sleep() missed on a
    # slower machine).
    _wait_idle(q)
    q.stop()
    spark.stop()
    shutil.rmtree(tmp, ignore_errors=True)

    real = sorted(
        [c for c in collected if not c["sensor_event_id"].startswith("flush")],
        key=lambda c: (c["alice_event_id"], c["timestamp_ms"]),
    )
    got = [(c["alice_event_id"], c["sensor_event_id"], c["abs_dt_ms"]) for c in real]
    ok = got == expect
    results.append((name, ok, expect, got))
    print(
        f"{'PASS' if ok else 'FAIL'}  {name}\n      expected {expect}\n      got      {got}\n"
    )
    return ok


def main():
    tmpdirs = {}

    # 1. Nearest of two candidates: 300 ms vs 400 ms.
    run_case(
        "nearest of two candidates (d300 vs d400)",
        [{"key": "A1", "ms": BASE}],
        [
            [
                (
                    None,
                    [
                        {"key": "S_300", "ms": BASE + 300},
                        {"key": "S_400", "ms": BASE - 400},
                    ],
                )
            ]
        ],
        [("A1", "S_300", 300)],
    )

    # 2. Tie at 200 ms: D4 picks the earlier sensor timestamp.
    run_case(
        "tie at d200 picks earlier sensor",
        [{"key": "A2", "ms": BASE}],
        [
            [
                (
                    None,
                    [
                        {"key": "S_LATE", "ms": BASE + 200},
                        {"key": "S_EARLY", "ms": BASE - 200},
                    ],
                )
            ]
        ],
        [("A2", "S_EARLY", 200)],
    )

    # 3. D2: two ALICE events may select the same sensor event.
    run_case(
        "two alice events share one sensor (D2)",
        [{"key": "A3", "ms": BASE}, {"key": "A4", "ms": BASE + 400}],
        [[(None, [{"key": "S_SHARED", "ms": BASE + 200}])]],
        [("A3", "S_SHARED", 200), ("A4", "S_SHARED", 200)],
    )

    # 4. R3: a closer candidate arriving in a later micro-batch must still win.
    run_case(
        "closer candidate in a later batch wins (R3)",
        [{"key": "A5", "ms": BASE}],
        [
            [(None, [{"key": "S_FAR", "ms": BASE + 400}])],
            [(None, [{"key": "S_NEAR", "ms": BASE + 80}])],
        ],
        [("A5", "S_NEAR", 80)],
    )

    print("\n" + "=" * 60)
    for name, ok, _, _ in results:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    failed = [r for r in results if not r[1]]
    print("=" * 60)
    print(f"{len(results) - len(failed)}/{len(results)} passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
