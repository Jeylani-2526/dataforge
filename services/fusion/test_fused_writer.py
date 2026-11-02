"""
M6W22T2 standalone check — runs write_fused_events() against a real
PostgreSQL instance (TimescaleDB calls aren't exercised; see
m6w21t6_fused_tables_ddl.md's own stubbed-function note for why that's fine
for DDL/row-level checks). Not part of the service; a manual verification
script.

Requires: a Postgres reachable at the DB_* env vars, with fused_events
already created (infrastructure/scripts/init-db.sql).
"""

import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "adaptation-layer"))

os.environ.setdefault(
    "FUSED_SCHEMA_PATH",
    os.path.join(
        os.path.dirname(__file__), "..", "..", "schemas", "fused_event_schema_v1.avsc"
    ),
)

from pyspark.sql import SparkSession

import fused_writer as fw

spark = (
    SparkSession.builder.master("local[2]").appName("test-fused-writer").getOrCreate()
)
spark.sparkContext.setLogLevel("ERROR")


def _df(rows):
    return spark.createDataFrame(
        rows,
        "alice_event_id string, timestamp_ms long, sensor_event_id string, sensor_type string",
    )


def row_count():
    conn = fw.get_connection().get()
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM fused_events")
        return cur.fetchone()[0]


def fetch_one(alice_id, ts):
    conn = fw.get_connection().get()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT data_loss_pct, latency_ms, schema_version, sensor_type "
            "FROM fused_events WHERE alice_event_id=%s AND timestamp_ms=%s",
            (alice_id, ts),
        )
        return cur.fetchone()


def main():
    before = row_count()
    print(f"rows before: {before}")

    a1, a2 = str(uuid.uuid4()), str(uuid.uuid4())
    s1 = str(uuid.uuid4())
    ts = 1_760_100_000_000  # fresh timestamp, not used by earlier manual tests

    # 1. Normal batch: two distinct fused rows.
    fw.write_fused_events(
        _df(
            [
                (a1, ts, s1, "RADAR"),
                (a2, ts + 500, s1, "LIDAR"),
            ]
        ),
        0,
    )
    after_1 = row_count()
    print(f"after batch 1: {after_1} (expected {before + 2})")
    assert after_1 == before + 2, "batch 1 insert count wrong"

    row = fetch_one(a1, ts)
    print(
        f"fetched row: data_loss_pct={row[0]} latency_ms={row[1]} schema_version={row[2]} sensor_type={row[3]}"
    )
    assert row[2] == "1.0", "schema_version not stamped"
    assert row[3] == "RADAR", "sensor_type not uppercase enum value"
    assert row[1] >= 0, "latency_ms should be non-negative for a past timestamp"
    assert row[0] == 0.0, "data_loss_pct should be 0.0 when nothing was rejected"

    # 2. Checkpoint replay of the same batch — different fused_event_id, same
    # (timestamp_ms, alice_event_id). Must NOT increase the row count.
    fw.write_fused_events(
        _df(
            [
                (a1, ts, s1, "RADAR"),
                (a2, ts + 500, s1, "LIDAR"),
            ]
        ),
        1,
    )
    after_2 = row_count()
    print(f"after replay of batch 1: {after_2} (expected {after_1}, unchanged)")
    assert after_2 == after_1, "replay was not de-duplicated"

    # 3. Empty batch — must not error or touch the connection.
    fw.write_fused_events(
        _df([]).select(
            "alice_event_id", "timestamp_ms", "sensor_event_id", "sensor_type"
        ),
        2,
    )
    after_3 = row_count()
    assert after_3 == after_1, "empty batch changed row count"
    print("empty batch handled cleanly")

    # 4. A record missing a required field: round-trip check must reject it,
    # not crash the batch, and the valid sibling in the same batch must still write.
    a3 = str(uuid.uuid4())
    bad_rows = _df(
        [(a3, ts + 1000, None, "RADAR")]
    )  # sensor_event_id NULL -> fails round-trip
    good_a = str(uuid.uuid4())
    mixed = bad_rows.union(_df([(good_a, ts + 2000, str(uuid.uuid4()), "TELEMETRY")]))
    fw.write_fused_events(mixed, 3)
    after_4 = row_count()
    print(
        f"after mixed good/bad batch: {after_4} (expected {after_3 + 1}, bad one rejected)"
    )
    assert after_4 == after_3 + 1, "mixed batch did not reject exactly the bad record"

    fw.close_connections()
    print("\nALL CHECKS PASSED")


if __name__ == "__main__":
    main()
