"""
DataForge — Staging Ingestion Script
Task: M3W10T5
Owner: Beyza Ülkümen
Output: /scripts/ingestion/staging_ingestion_script.py

Loads Omer's generator NDJSON batches into:
  - raw_alice_events_staging
  - raw_sensor_events_staging
"""

import json
import uuid
import logging
from pathlib import Path
from datetime import datetime, timezone

import psycopg2
from psycopg2.extras import execute_batch

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
)
log = logging.getLogger(__name__)

# ── DB Connection ─────────────────────────────────────────────────────────────
DB_URL = "postgresql://postgres:dataforge@localhost:5432/dataforge_db"

# ── Constants ─────────────────────────────────────────────────────────────────
VALID_SCHEMA_VERSION = "1.0"
VALID_SENSOR_TYPES   = {"RADAR", "LIDAR", "TELEMETRY"}

ALICE_REQUIRED = [
    "event_id", "run_number", "timestamp_ms", "track_count",
    "net_momentum_x", "net_momentum_y", "net_momentum_z",
    "max_energy_gev", "total_energy_gev", "schema_version",
]

SENSOR_REQUIRED_COMMON = [
    "event_id", "sensor_id", "sensor_type", "timestamp_ms", "schema_version",
]

SENSOR_REQUIRED_BY_TYPE = {
    "RADAR":     ["target_id", "range_m", "bearing_deg", "elevation_deg",
                  "velocity_ms", "signal_strength_db"],
    "LIDAR":     ["scan_id", "point_count", "centroid_x_m", "centroid_y_m",
                  "centroid_z_m", "max_range_m", "avg_intensity", "min_intensity"],
    "TELEMETRY": ["device_id", "parameter_name", "value", "unit", "sequence_number"],
}


# ── Validation ────────────────────────────────────────────────────────────────

def validate_alice(record: dict) -> str | None:
    """Returns error string if invalid, None if valid."""
    if record.get("schema_version") != VALID_SCHEMA_VERSION:
        return f"schema_version must be '{VALID_SCHEMA_VERSION}'"
    for field in ALICE_REQUIRED:
        if record.get(field) is None:
            return f"required field missing or null: {field}"
    try:
        uuid.UUID(str(record["event_id"]), version=4)
    except ValueError:
        return "event_id is not a valid UUID v4"
    if not isinstance(record["timestamp_ms"], int) or record["timestamp_ms"] <= 0:
        return "timestamp_ms must be a positive integer"
    return None


def validate_sensor(record: dict) -> str | None:
    """Returns error string if invalid, None if valid."""
    if record.get("schema_version") != VALID_SCHEMA_VERSION:
        return f"schema_version must be '{VALID_SCHEMA_VERSION}'"
    for field in SENSOR_REQUIRED_COMMON:
        if record.get(field) is None:
            return f"required field missing or null: {field}"
    sensor_type = record.get("sensor_type", "").upper()
    if sensor_type not in VALID_SENSOR_TYPES:
        return f"sensor_type '{sensor_type}' not in {VALID_SENSOR_TYPES}"
    for field in SENSOR_REQUIRED_BY_TYPE[sensor_type]:
        if record.get(field) is None:
            return f"required {sensor_type} field missing or null: {field}"
    try:
        uuid.UUID(str(record["event_id"]), version=4)
    except ValueError:
        return "event_id is not a valid UUID v4"
    if not isinstance(record["timestamp_ms"], int) or record["timestamp_ms"] <= 0:
        return "timestamp_ms must be a positive integer"
    return None


# ── Loaders ───────────────────────────────────────────────────────────────────

ALICE_INSERT = """
    INSERT INTO raw_alice_events_staging (
        load_timestamp, batch_id,
        event_id, run_number, timestamp_ms, track_count,
        net_momentum_x, net_momentum_y, net_momentum_z,
        max_energy_gev, total_energy_gev,
        schema_version, load_status
    ) VALUES (
        %(load_timestamp)s, %(batch_id)s,
        %(event_id)s, %(run_number)s, %(timestamp_ms)s, %(track_count)s,
        %(net_momentum_x)s, %(net_momentum_y)s, %(net_momentum_z)s,
        %(max_energy_gev)s, %(total_energy_gev)s,
        %(schema_version)s, %(load_status)s
    )
"""

SENSOR_INSERT = """
    INSERT INTO raw_sensor_events_staging (
        load_timestamp, batch_id,
        event_id, sensor_id, sensor_type, timestamp_ms,
        target_id, range_m, bearing_deg, elevation_deg,
        velocity_ms, signal_strength_db,
        scan_id, point_count, centroid_x_m, centroid_y_m, centroid_z_m,
        max_range_m, avg_intensity, min_intensity,
        device_id, parameter_name, value, unit, sequence_number,
        schema_version, load_status
    ) VALUES (
        %(load_timestamp)s, %(batch_id)s,
        %(event_id)s, %(sensor_id)s, %(sensor_type)s, %(timestamp_ms)s,
        %(target_id)s, %(range_m)s, %(bearing_deg)s, %(elevation_deg)s,
        %(velocity_ms)s, %(signal_strength_db)s,
        %(scan_id)s, %(point_count)s, %(centroid_x_m)s, %(centroid_y_m)s,
        %(centroid_z_m)s, %(max_range_m)s, %(avg_intensity)s, %(min_intensity)s,
        %(device_id)s, %(parameter_name)s, %(value)s, %(unit)s, %(sequence_number)s,
        %(schema_version)s, %(load_status)s
    )
"""


def load_alice_batch(conn, records: list[dict], batch_id: str) -> tuple[int, int]:
    """Returns (loaded_count, failed_count)."""
    load_ts  = datetime.now(timezone.utc)
    valid, failed = [], []

    for rec in records:
        err = validate_alice(rec)
        if err:
            log.warning("ALICE reject [%s]: %s", rec.get("event_id", "?"), err)
            failed.append(rec)
            continue
        valid.append({
            "load_timestamp":  load_ts,
            "batch_id":        batch_id,
            "event_id":        rec["event_id"],
            "run_number":      rec["run_number"],
            "timestamp_ms":    rec["timestamp_ms"],
            "track_count":     rec["track_count"],
            "net_momentum_x":  rec["net_momentum_x"],
            "net_momentum_y":  rec["net_momentum_y"],
            "net_momentum_z":  rec["net_momentum_z"],
            "max_energy_gev":  rec["max_energy_gev"],
            "total_energy_gev": rec["total_energy_gev"],
            "schema_version":  rec["schema_version"],
            "load_status":     "validated",
        })

    if valid:
        with conn.cursor() as cur:
            execute_batch(cur, ALICE_INSERT, valid, page_size=500)
        conn.commit()

    return len(valid), len(failed)


def load_sensor_batch(conn, records: list[dict], batch_id: str) -> tuple[int, int]:
    """Returns (loaded_count, failed_count)."""
    load_ts  = datetime.now(timezone.utc)
    valid, failed = [], []

    for rec in records:
        err = validate_sensor(rec)
        if err:
            log.warning("SENSOR reject [%s]: %s", rec.get("event_id", "?"), err)
            failed.append(rec)
            continue
        valid.append({
            "load_timestamp":    load_ts,
            "batch_id":          batch_id,
            "event_id":          rec["event_id"],
            "sensor_id":         rec["sensor_id"],
            "sensor_type":       rec["sensor_type"].upper(),
            "timestamp_ms":      rec["timestamp_ms"],
            "target_id":         rec.get("target_id"),
            "range_m":           rec.get("range_m"),
            "bearing_deg":       rec.get("bearing_deg"),
            "elevation_deg":     rec.get("elevation_deg"),
            "velocity_ms":       rec.get("velocity_ms"),
            "signal_strength_db": rec.get("signal_strength_db"),
            "scan_id":           rec.get("scan_id"),
            "point_count":       rec.get("point_count"),
            "centroid_x_m":      rec.get("centroid_x_m"),
            "centroid_y_m":      rec.get("centroid_y_m"),
            "centroid_z_m":      rec.get("centroid_z_m"),
            "max_range_m":       rec.get("max_range_m"),
            "avg_intensity":     rec.get("avg_intensity"),
            "min_intensity":     rec.get("min_intensity"),
            "device_id":         rec.get("device_id"),
            "parameter_name":    rec.get("parameter_name"),
            "value":             rec.get("value"),
            "unit":              rec.get("unit"),
            "sequence_number":   rec.get("sequence_number"),
            "schema_version":    rec["schema_version"],
            "load_status":       "validated",
        })

    if valid:
        with conn.cursor() as cur:
            execute_batch(cur, SENSOR_INSERT, valid, page_size=500)
        conn.commit()

    return len(valid), len(failed)


# ── File Loader ───────────────────────────────────────────────────────────────

def load_ndjson_file(filepath: Path, stream_type: str, conn) -> dict:
    """
    Loads a single NDJSON file into the appropriate staging table.
    stream_type: 'alice' | 'radar' | 'lidar' | 'telemetry'
    Returns summary dict.
    """
    batch_id   = str(uuid.uuid4())
    records    = []

    with open(filepath, "r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as e:
                log.warning("JSON parse error line %d in %s: %s", i, filepath.name, e)

    if stream_type == "alice":
        loaded, failed = load_alice_batch(conn, records, batch_id)
    else:
        loaded, failed = load_sensor_batch(conn, records, batch_id)

    log.info(
        "%-30s  stream=%-10s  batch=%s  loaded=%d  failed=%d",
        filepath.name, stream_type, batch_id[:8], loaded, failed
    )
    return {
        "file":       filepath.name,
        "stream":     stream_type,
        "batch_id":   batch_id,
        "loaded":     loaded,
        "failed":     failed,
        "total":      loaded + failed,
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def ingest_directory(data_dir: str, stream_type: str):
    """
    Ingests all .ndjson files in data_dir for the given stream_type.
    stream_type: 'alice' | 'radar' | 'lidar' | 'telemetry'
    """
    path = Path(data_dir)
    files = sorted(path.glob("*.ndjson"))
    if not files:
        log.warning("No .ndjson files found in %s", data_dir)
        return

    conn = psycopg2.connect(DB_URL)
    results = []
    try:
        for f in files:
            result = load_ndjson_file(f, stream_type, conn)
            results.append(result)
    finally:
        conn.close()

    total_loaded = sum(r["loaded"] for r in results)
    total_failed = sum(r["failed"] for r in results)
    log.info(
        "DONE — stream=%s  files=%d  total_loaded=%d  total_failed=%d",
        stream_type, len(files), total_loaded, total_failed
    )
    return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="DataForge Staging Ingestion Script")
    parser.add_argument("stream_type", choices=["alice", "radar", "lidar", "telemetry"])
    parser.add_argument("data_dir", help="Directory containing .ndjson batch files")
    args = parser.parse_args()

    ingest_directory(args.data_dir, args.stream_type)
