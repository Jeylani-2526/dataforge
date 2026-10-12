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
import psycopg2

DB_DSN = os.getenv("TIMESCALE_DSN", "postgresql://postgres:postgres@localhost:5432/dataforge")
SAMPLE_SIZE = 1000

REQUIRED_FIELDS = [
    "event_id",
    "run_number",
    "timestamp_ms",
    "track_count",
    "net_momentum_x",
    "net_momentum_y",
    "net_momentum_z",
    "max_energy_gev",
    "total_energy_gev",
]

NULLABLE_M7 = {"sensor_batch_id"}


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

    cur.execute(f"SELECT * FROM fused_events LIMIT {SAMPLE_SIZE};")
    rows = cur.fetchall()
    col_names = [desc[0] for desc in cur.description]

    print(f"[INFO] Columns found: {col_names}")

    failures = []

    # Check 1: required fields present
    for field in REQUIRED_FIELDS:
        if field not in col_names:
            failures.append(f"MISSING COLUMN: {field}")

    if failures:
        for f in failures:
            print(f"[FAIL] {f}")
        cur.close()
        conn.close()
        sys.exit(1)

    # Check 2: field-level value checks
    field_idx = {name: i for i, name in enumerate(col_names)}

    null_counts = {f: 0 for f in REQUIRED_FIELDS}
    type_failures = []

    for row in rows:
        for field in REQUIRED_FIELDS:
            val = row[field_idx[field]]
            if val is None:
                null_counts[field] += 1
            else:
                # Type checks
                if field == "event_id" and not isinstance(val, str):
                    type_failures.append(f"event_id not str: {type(val)}")
                if field == "run_number" and not isinstance(val, int):
                    type_failures.append(f"run_number not int: {type(val)}")
                if field == "timestamp_ms" and not isinstance(val, int):
                    type_failures.append(f"timestamp_ms not int: {type(val)}")
                if field == "track_count" and not isinstance(val, int):
                    type_failures.append(f"track_count not int: {type(val)}")
                if field in ("net_momentum_x", "net_momentum_y", "net_momentum_z",
                             "max_energy_gev", "total_energy_gev"):
                    if not isinstance(val, (int, float)):
                        type_failures.append(f"{field} not numeric: {type(val)}")

    passed = True

    for field, count in null_counts.items():
        if count > 0:
            pct = count / len(rows) * 100
            print(f"[FAIL] {field}: {count}/{len(rows)} NULLs ({pct:.1f}%)")
            passed = False
        else:
            print(f"[PASS] {field}: no NULLs")

    for tf in set(type_failures[:20]):
        print(f"[FAIL] TYPE: {tf}")
        passed = False

    cur.close()
    conn.close()

    if passed:
        print(f"\n[RESULT] PASS — {len(rows)} rows checked, all fields conform.")
        sys.exit(0)
    else:
        print(f"\n[RESULT] FAIL — conformance check failed.")
        sys.exit(1)


if __name__ == "__main__":
    run_checks()
