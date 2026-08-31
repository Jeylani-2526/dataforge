"""
DataForge — Staging to Production Promotion Script
Task: M4W15T5
Owner: Beyza Ülkümen
Source: docs/database/staging_to_production_promotion_design.md
"""

import logging
import psycopg2
from psycopg2.extras import execute_batch

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s")
log = logging.getLogger(__name__)

DB_URL = "postgresql://dataforge:dataforge_dev@localhost:5433/dataforge"

VALID_SENSOR_TYPES = {"RADAR", "LIDAR", "TELEMETRY"}


# ── Validation ────────────────────────────────────────────────────────────────

def validate_alice_record(rec: dict) -> str | None:
    if not rec.get("event_id"):
        return "event_id missing"
    if not rec.get("timestamp_ms") or rec["timestamp_ms"] <= 0:
        return "timestamp_ms invalid"
    if rec.get("run_number") is None:
        return "run_number missing"
    if rec.get("track_count") is None or rec["track_count"] < 0:
        return "track_count invalid"
    if rec.get("net_momentum_x") is None:
        return "net_momentum_x missing"
    if rec.get("net_momentum_y") is None:
        return "net_momentum_y missing"
    if rec.get("net_momentum_z") is None:
        return "net_momentum_z missing"
    if rec.get("max_energy_gev") is None or rec["max_energy_gev"] < 0:
        return "max_energy_gev invalid"
    if rec.get("total_energy_gev") is None or rec["total_energy_gev"] < 0:
        return "total_energy_gev invalid"
    return None


def validate_sensor_record(rec: dict) -> str | None:
    if not rec.get("event_id"):
        return "event_id missing"
    if not rec.get("timestamp_ms") or rec["timestamp_ms"] <= 0:
        return "timestamp_ms invalid"
    if rec.get("sensor_type", "").upper() not in VALID_SENSOR_TYPES:
        return f"sensor_type invalid: {rec.get('sensor_type')}"
    if rec.get("label") not in (0, 1):
        return f"label invalid: {rec.get('label')}"
    return None


# ── Promotion ─────────────────────────────────────────────────────────────────

ALICE_INSERT = """
    INSERT INTO events (
        event_id, timestamp_ms, source_type,
        run_number, track_count,
        net_momentum_x, net_momentum_y, net_momentum_z,
        max_energy_gev, total_energy_gev,
        schema_version
    ) VALUES (
        %(event_id)s, %(timestamp_ms)s, 'alice',
        %(run_number)s, %(track_count)s,
        %(net_momentum_x)s, %(net_momentum_y)s, %(net_momentum_z)s,
        %(max_energy_gev)s, %(total_energy_gev)s,
        %(schema_version)s
    ) ON CONFLICT (event_id, timestamp_ms) DO NOTHING
"""

SENSOR_INSERT = """
    INSERT INTO events (
        event_id, timestamp_ms, source_type,
        sensor_type, label, anomaly_type,
        schema_version
    ) VALUES (
        %(event_id)s, %(timestamp_ms)s, %(source_type)s,
        %(sensor_type)s, %(label)s, %(anomaly_type)s,
        %(schema_version)s
    ) ON CONFLICT (event_id, timestamp_ms) DO NOTHING
"""

ALICE_UPDATE = """
    UPDATE raw_alice_events_staging
    SET load_status = 'promoted'
    WHERE load_status = 'validated'
"""

SENSOR_UPDATE = """
    UPDATE raw_sensor_events_staging
    SET load_status = 'promoted'
    WHERE load_status = 'validated'
"""


def promote_alice(conn) -> tuple[int, int]:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT event_id, timestamp_ms, run_number, track_count,
                   net_momentum_x, net_momentum_y, net_momentum_z,
                   max_energy_gev, total_energy_gev, schema_version
            FROM raw_alice_events_staging
            WHERE load_status = 'validated'
        """)
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]

    records = [dict(zip(cols, r)) for r in rows]
    valid, failed = [], []

    for rec in records:
        err = validate_alice_record(rec)
        if err:
            log.warning("ALICE skip [%s]: %s", rec.get("event_id"), err)
            failed.append(rec)
        else:
            valid.append(rec)

    if valid:
        with conn.cursor() as cur:
            execute_batch(cur, ALICE_INSERT, valid, page_size=100)
            cur.execute(ALICE_UPDATE)
        conn.commit()

    log.info("ALICE — promoted=%d  skipped=%d", len(valid), len(failed))
    return len(valid), len(failed)


def promote_sensors(conn) -> tuple[int, int]:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT event_id, timestamp_ms, sensor_type,
                   label, anomaly_type, schema_version
            FROM raw_sensor_events_staging
            WHERE load_status = 'validated'
        """)
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description]

    records = [dict(zip(cols, r)) for r in rows]
    valid, failed = [], []

    for rec in records:
        err = validate_sensor_record(rec)
        if err:
            log.warning("SENSOR skip [%s]: %s", rec.get("event_id"), err)
            failed.append(rec)
        else:
            rec["source_type"] = rec["sensor_type"].lower()
            valid.append(rec)

    if valid:
        with conn.cursor() as cur:
            execute_batch(cur, SENSOR_INSERT, valid, page_size=500)
            cur.execute(SENSOR_UPDATE)
        conn.commit()

    log.info("SENSOR — promoted=%d  skipped=%d", len(valid), len(failed))
    return len(valid), len(failed)


# ── Main ──────────────────────────────────────────────────────────────────────

def run_promotion():
    conn = psycopg2.connect(DB_URL)
    try:
        log.info("Starting promotion — ALICE")
        alice_ok, alice_fail = promote_alice(conn)

        log.info("Starting promotion — SENSOR")
        sensor_ok, sensor_fail = promote_sensors(conn)

        total_ok   = alice_ok + sensor_ok
        total_fail = alice_fail + sensor_fail

        log.info("DONE — total_promoted=%d  total_skipped=%d", total_ok, total_fail)
        return total_ok, total_fail
    finally:
        conn.close()


if __name__ == "__main__":
    run_promotion()
