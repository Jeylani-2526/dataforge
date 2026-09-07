"""
Topics:
  sensor-radar      → RADAR records
  sensor-lidar      → LIDAR records
  sensor-telemetry  → TELEMETRY records
"""

import io
import json
import logging
import os
import random
import signal
import sys
import time
import uuid
from pathlib import Path

from confluent_kafka import Producer
from fastavro import parse_schema, schemaless_writer
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
)
log = logging.getLogger(__name__)

# ── Config ───────────────────────────────────────────────────────────────
KAFKA_BOOTSTRAP_SERVERS = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")

TOPIC_RADAR     = os.environ.get("KAFKA_TOPIC_RADAR",     "sensor-radar")
TOPIC_LIDAR     = os.environ.get("KAFKA_TOPIC_LIDAR",     "sensor-lidar")
TOPIC_TELEMETRY = os.environ.get("KAFKA_TOPIC_TELEMETRY", "sensor-telemetry")

SENSOR_PUBLISH_INTERVAL_MS = int(os.environ.get("SENSOR_PUBLISH_INTERVAL_MS", "200"))
SCHEMA_PATH = Path(
    os.environ.get("SENSOR_SCHEMA_PATH", "/app/schemas/sensor_schema_v1.avsc")
)
CURRENT_SCHEMA_VERSION = "1.0"

# Device IDs — per m5_prework_device_diversity_scope.md (M4W13T8)
RADAR_SENSOR_IDS     = ["radar-001", "radar-002", "radar-003"]
LIDAR_SENSOR_IDS     = ["lidar-001", "lidar-002", "lidar-003"]
TELEMETRY_DEVICE_IDS = ["UAV-01", "UAV-02", "SENSOR-UNIT-01", "SENSOR-UNIT-02", "GCS-01"]
TELEMETRY_PARAMS     = [
    ("cpu_temp_c",   lambda: round(random.uniform(40.0, 90.0), 2),  "C"),
    ("battery_pct",  lambda: round(random.uniform(10.0, 100.0), 2), "%"),
    ("voltage_v",    lambda: round(random.uniform(10.0, 16.8), 2),  "V"),
    ("altitude_m",   lambda: round(random.uniform(0.0, 500.0), 2),  "m"),
    ("signal_rssi",  lambda: round(random.uniform(-90.0, -20.0), 2),"dBm"),
]

_running = True
_sequence_counters: dict[str, int] = {}


def _handle_shutdown(signum, frame):
    global _running
    log.info("Shutdown signal (%s) — finishing current record, then exiting.", signum)
    _running = False


def load_schema() -> dict:
    if not SCHEMA_PATH.exists():
        raise FileNotFoundError(
            f"sensor_schema_v1.avsc not found at {SCHEMA_PATH}. "
            f"Set SENSOR_SCHEMA_PATH or mount /schemas into the container."
        )
    with open(SCHEMA_PATH) as f:
        return parse_schema(json.load(f))


def validate_and_serialize(record: dict, schema: dict) -> bytes | None:
    """Serialize record against schema. Returns None if validation fails."""
    try:
        buf = io.BytesIO()
        schemaless_writer(buf, schema, record)
        return buf.getvalue()
    except Exception as e:
        log.warning("Schema validation failed for event_id=%s: %s",
                    record.get("event_id"), e)
        return None


def _base(sensor_type: str, sensor_id: str) -> dict:
    """Common fields shared across all sensor types."""
    return {
        "event_id":       str(uuid.uuid4()),
        "sensor_id":      sensor_id,
        "sensor_type":    sensor_type,
        "timestamp_ms":   int(time.time() * 1000),
        "schema_version": CURRENT_SCHEMA_VERSION,
        # Fields belonging to other subtypes — null, not omitted
        "target_id":        None,
        "range_m":          None,
        "bearing_deg":      None,
        "elevation_deg":    None,
        "velocity_ms":      None,
        "signal_strength_db": None,
        "scan_id":          None,
        "point_count":      None,
        "centroid_x_m":     None,
        "centroid_y_m":     None,
        "centroid_z_m":     None,
        "max_range_m":      None,
        "avg_intensity":    None,
        "min_intensity":    None,
        "device_id":        None,
        "parameter_name":   None,
        "value":            None,
        "unit":             None,
        "sequence_number":  None,
    }


def generate_radar() -> dict:
    sensor_id = random.choice(RADAR_SENSOR_IDS)
    record = _base("RADAR", sensor_id)
    record.update({
        "target_id":          str(uuid.uuid4())[:8],
        "range_m":            round(random.uniform(50.0, 5000.0), 2),
        "bearing_deg":        round(random.uniform(0.0, 360.0), 2),
        "elevation_deg":      round(random.uniform(-90.0, 90.0), 2),
        "velocity_ms":        round(random.uniform(-100.0, 100.0), 2),
        "signal_strength_db": round(random.uniform(-80.0, -20.0), 2),
    })
    return record


def generate_lidar() -> dict:
    sensor_id = random.choice(LIDAR_SENSOR_IDS)
    record = _base("LIDAR", sensor_id)
    avg_i = round(random.uniform(80.0, 220.0), 2)
    min_i = round(random.uniform(0.0, avg_i), 2)
    record.update({
        "scan_id":     str(uuid.uuid4())[:8],
        "point_count": random.randint(500, 5000),
        "centroid_x_m": round(random.uniform(-500.0, 500.0), 3),
        "centroid_y_m": round(random.uniform(-500.0, 500.0), 3),
        "centroid_z_m": round(random.uniform(0.0, 200.0), 3),
        "max_range_m":  round(random.uniform(10.0, 200.0), 2),
        "avg_intensity": avg_i,
        "min_intensity": min_i,
    })
    return record


def generate_telemetry() -> dict:
    device_id = random.choice(TELEMETRY_DEVICE_IDS)
    param_name, value_fn, unit = random.choice(TELEMETRY_PARAMS)

    # Monotonic sequence per device
    seq = _sequence_counters.get(device_id, 0) + 1
    _sequence_counters[device_id] = seq

    record = _base("TELEMETRY", device_id)
    record.update({
        "device_id":       device_id,
        "parameter_name":  param_name,
        "value":           value_fn(),
        "unit":            unit,
        "sequence_number": seq,
    })
    return record


def delivery_report(err, msg):
    if err is not None:
        log.error("Delivery failed topic=%s event_id=%s: %s",
                  msg.topic(), msg.key(), err)
    else:
        log.debug("Delivered topic=%s partition=%d offset=%d event_id=%s",
                  msg.topic(), msg.partition(), msg.offset(), msg.key())


def run():
    global _running
    signal.signal(signal.SIGTERM, _handle_shutdown)
    signal.signal(signal.SIGINT, _handle_shutdown)

    log.info(
        "Starting Sensor Kafka Producer — bootstrap=%s interval_ms=%d",
        KAFKA_BOOTSTRAP_SERVERS, SENSOR_PUBLISH_INTERVAL_MS,
    )

    schema = load_schema()
    producer = Producer({"bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS})

    generators = [
        (generate_radar,     TOPIC_RADAR),
        (generate_lidar,     TOPIC_LIDAR),
        (generate_telemetry, TOPIC_TELEMETRY),
    ]

    published  = {"radar": 0, "lidar": 0, "telemetry": 0}
    failed     = {"radar": 0, "lidar": 0, "telemetry": 0}

    log.info("Publishing to topics: %s | %s | %s",
             TOPIC_RADAR, TOPIC_LIDAR, TOPIC_TELEMETRY)

    while _running:
        gen_fn, topic = random.choice(generators)
        record = gen_fn()
        sensor_key = record["sensor_type"].lower()

        payload = validate_and_serialize(record, schema)
        if payload is None:
            failed[sensor_key] += 1
            continue

        producer.produce(
            topic,
            key=record["event_id"].encode("utf-8"),
            value=payload,
            callback=delivery_report,
        )
        producer.poll(0)
        published[sensor_key] += 1

        if published[sensor_key] % 500 == 0:
            log.info(
                "Published totals — radar=%d lidar=%d telemetry=%d | "
                "failed — radar=%d lidar=%d telemetry=%d",
                published["radar"], published["lidar"], published["telemetry"],
                failed["radar"],    failed["lidar"],    failed["telemetry"],
            )

        if SENSOR_PUBLISH_INTERVAL_MS > 0:
            time.sleep(SENSOR_PUBLISH_INTERVAL_MS / 1000.0)

    producer.flush(timeout=10)
    log.info(
        "Producer stopped. Final totals — radar=%d lidar=%d telemetry=%d",
        published["radar"], published["lidar"], published["telemetry"],
    )


if __name__ == "__main__":
    run()