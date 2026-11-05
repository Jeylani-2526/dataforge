"""
check_fused_conformance.py
M6W22T6 — Fused-record conformance check against fused_event_schema_v1.avsc field contract.

Usage:
    python check_fused_conformance.py

Exit codes:
    0 — PASS (all checks passed)
    1 — FAIL (one or more checks failed)
"""

import sys
import os
import uuid
import psycopg2

DB_DSN = os.getenv("TIMESCALE_DSN", "postgresql://dataforge:dataforge_dev@localhost:5434/dataforge")
SAMPLE_SIZE = 1000

REQUIRED_FIELDS = [
    "fused_event_id",
    "alice_event_id",
    "sensor_event_id",
    "timestamp_ms",
    "fusion_window_ms",
    "sensor_type",
    "data_loss_pct",
    "latency_ms",
    "schema_version",
]

M7_NULLABLE = ["anomaly_label", "risk_score", "confidence"]

VALID_SENSOR_TYPES = {"RADAR", "LIDAR", "TELEMETRY"}


def is_valid_uuid(val):
    """Accept both str and uuid.UUID — psycopg2 returns uuid.UUID for UUID columns."""
    if isinstance(val, uuid.UUID):
        return True
    if isinstance(val, str):
        try:
            uuid.UUID(val)
            return True
        except ValueError:
            return False
    return False


def run_checks():
    try:
        conn = psycopg2.connect(DB_DSN)
    except Exception as e:
        print(f"[ERROR] DB connection failed: {e}")
        sys.exit(1)

    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM fused_events;")
    total = cur.fetchone()[0]
    print(f"[INFO] fused_events row count: {total}")

    if total == 0:
        print("[SKIP] No rows to check — fusion engine has not produced output yet.")
        cur.close()
        conn.close()
        sys.exit(0)

    # Select columns by name explicitly — column order in table may differ from schema
    all_cols = REQUIRED_FIELDS + M7_NULLABLE
    col_list = ", ".join(all_cols)
    cur.execute(f"SELECT {col_list} FROM fused_events LIMIT {SAMPLE_SIZE};")
    raw_rows = cur.fetchall()
    col_names = [desc[0] for desc in cur.description]

    # Convert rows to dicts
    rows = [dict(zip(col_names, row)) for row in raw_rows]
    sample_size = len(rows)

    print(f"[INFO] Columns fetched: {col_names}")
    print(f"[INFO] Sample size: {sample_size}")

    failures = []
    passed = True

    # --- Check 1: UUID fields ---
    uuid_fields = ["fused_event_id", "alice_event_id", "sensor_event_id"]
    for field in uuid_fields:
        bad = [i for i, r in enumerate(rows) if not is_valid_uuid(r[field])]
        if bad:
            print(f"[FAIL] {field}: {len(bad)}/{sample_size} rows have invalid UUID")
            passed = False
        else:
            print(f"[PASS] {field}: all {sample_size} rows valid UUID")

    # --- Check 2: timestamp_ms > 0 ---
    bad = [i for i, r in enumerate(rows) if not (r["timestamp_ms"] is not None and r["timestamp_ms"] > 0)]
    if bad:
        print(f"[FAIL] timestamp_ms: {len(bad)}/{sample_size} rows not > 0")
        passed = False
    else:
        print(f"[PASS] timestamp_ms: all {sample_size} rows > 0")

    # --- Check 3: fusion_window_ms == 500 ---
    bad = [i for i, r in enumerate(rows) if r["fusion_window_ms"] != 500]
    if bad:
        print(f"[FAIL] fusion_window_ms: {len(bad)}/{sample_size} rows != 500")
        passed = False
    else:
        print(f"[PASS] fusion_window_ms: all {sample_size} rows == 500")

    # --- Check 4: sensor_type in valid set ---
    bad = [i for i, r in enumerate(rows) if r["sensor_type"] not in VALID_SENSOR_TYPES]
    if bad:
        bad_vals = set(rows[i]["sensor_type"] for i in bad)
        print(f"[FAIL] sensor_type: {len(bad)}/{sample_size} rows invalid — found {bad_vals}")
        passed = False
    else:
        print(f"[PASS] sensor_type: all {sample_size} rows in {{RADAR, LIDAR, TELEMETRY}}")

    # --- Check 5: data_loss_pct in [0, 100] ---
    bad = [i for i, r in enumerate(rows)
           if r["data_loss_pct"] is None or not (0 <= r["data_loss_pct"] <= 100)]
    if bad:
        print(f"[FAIL] data_loss_pct: {len(bad)}/{sample_size} rows out of [0, 100]")
        passed = False
    else:
        print(f"[PASS] data_loss_pct: all {sample_size} rows in [0, 100]")

    # --- Check 6: latency_ms >= 0 ---
    bad = [i for i, r in enumerate(rows)
           if r["latency_ms"] is None or r["latency_ms"] < 0]
    if bad:
        print(f"[FAIL] latency_ms: {len(bad)}/{sample_size} rows < 0")
        passed = False
    else:
        print(f"[PASS] latency_ms: all {sample_size} rows >= 0")

    # --- Check 7: schema_version == "1.0" ---
    bad = [i for i, r in enumerate(rows) if str(r["schema_version"]) != "1.0"]
    if bad:
        bad_vals = set(str(rows[i]["schema_version"]) for i in bad)
        print(f"[FAIL] schema_version: {len(bad)}/{sample_size} rows != '1.0' — found {bad_vals}")
        passed = False
    else:
        print(f"[PASS] schema_version: all {sample_size} rows == '1.0'")

    # --- Check 8: M7 nullable columns MUST be NULL (model not yet run) ---
    for field in M7_NULLABLE:
        non_null = [i for i, r in enumerate(rows) if r[field] is not None]
        if non_null:
            print(f"[FAIL] {field}: {len(non_null)}/{sample_size} rows are NOT NULL (model not yet run)")
            passed = False
        else:
            print(f"[PASS] {field}: all {sample_size} rows NULL (correct — M7 not yet run)")

    # --- Check 9: duplicate fused_event_id ---
    cur.execute(
        "SELECT COUNT(*) - COUNT(DISTINCT fused_event_id) FROM fused_events;"
    )
    dup_count = cur.fetchone()[0]
    if dup_count > 0:
        print(f"[FAIL] fused_event_id: {dup_count} duplicate(s) across full table")
        passed = False
    else:
        print(f"[PASS] fused_event_id: no duplicates across full table ({total} rows)")

    cur.close()
    conn.close()

    print()
    if passed:
        print(f"[RESULT] PASS — {sample_size} rows sampled, all checks passed.")
        sys.exit(0)
    else:
        print(f"[RESULT] FAIL — one or more checks failed.")
        sys.exit(1)


if __name__ == "__main__":
    run_checks()
