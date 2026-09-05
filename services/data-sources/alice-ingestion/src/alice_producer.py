"""
DataForge — ALICE Kafka Producer
Task: M5W17T1
Owner: Abdullah

Publishes the 68 filtered, PyROOT-corrected ALICE records to the
alice-events Kafka topic, on a paced continuous loop, so Week 18's Spark
Structured Streaming consumer has a real ongoing stream to test
watermark/window logic against rather than a single burst.


"""

import io
import json
import logging
import os
import signal
import sys
import time
from pathlib import Path

import psycopg2
import psycopg2.extras
from confluent_kafka import Producer
from fastavro import parse_schema, schemaless_reader, schemaless_writer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(message)s",
)
log = logging.getLogger(__name__)

# ── Config ───────────────────────────────────────────────────────────────
# Same env-var pattern as services/adaptation-layer/avro_adaptation_job.py:
# works both inside Docker (DB_HOST=timescaledb, DB_PORT=5432 internal) and
# run locally on Abdullah's Windows setup outside Docker, where the DB is
# reached via the published host port (5433), not the container-internal
# port. See M4W16T3 finding — the 5432/5433 split is host-vs-container, not
# an inconsistency.
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = os.environ.get("DB_PORT", "5433")
DB_NAME = os.environ.get("DB_NAME", "dataforge")
DB_USER = os.environ.get("DB_USER", "dataforge")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "dataforge_dev")

KAFKA_BOOTSTRAP_SERVERS = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
KAFKA_TOPIC_ALICE = os.environ.get("KAFKA_TOPIC_ALICE", "alice-events")

# Pacing, not throughput — see design note #2 above. Default: one record
# every 500ms (~2 events/sec), a full 68-record loop every ~34s. Override
# via env var; ALICE_REPLAY_INTERVAL_MS=0 would produce a tight loop and
# is intentionally still allowed (for local stress-testing) but is NOT
# the default and should not be used to report a throughput figure.
ALICE_REPLAY_INTERVAL_MS = int(os.environ.get("ALICE_REPLAY_INTERVAL_MS", "500"))

# Gap added on top of the dataset's own event-time span when rebasing
# each loop (see design note #2b above), so loop N+1's first record is
# strictly after loop N's last record — never equal, never behind.
# Prevents a zero-width boundary from being ambiguous to the watermark.
ALICE_LOOP_GAP_MS = int(os.environ.get("ALICE_LOOP_GAP_MS", "1000"))

SCHEMA_PATH = Path(
    os.environ.get("ALICE_SCHEMA_PATH", "/app/schemas/alice_event_schema_v1.avsc")
)
CURRENT_SCHEMA_VERSION = "1.0"  # mirrors schema_versioning.CURRENT_SCHEMA_VERSIONS["alice_event"]

FETCH_QUERY = """
    SELECT event_id::text, run_number, timestamp_ms, track_count,
           net_momentum_x, net_momentum_y, net_momentum_z,
           max_energy_gev, total_energy_gev, schema_version
    FROM events
    WHERE source_type = 'alice'
    ORDER BY timestamp_ms;
"""

_running = True


def _handle_shutdown(signum, frame):
    global _running
    log.info("Shutdown signal received (%s) — finishing current record, then exiting.", signum)
    _running = False


def load_schema() -> dict:
    if not SCHEMA_PATH.exists():
        raise FileNotFoundError(
            f"alice_event_schema_v1.avsc not found at {SCHEMA_PATH}. "
            f"Mount /schemas into the container (see docker-compose.yml) or "
            f"set ALICE_SCHEMA_PATH."
        )
    with open(SCHEMA_PATH) as f:
        return parse_schema(json.load(f))


def fetch_records() -> list:
    """One-time fetch of all promoted ALICE records at startup. 68 rows
    expected — logged explicitly if that count drifts, since a changed
    count would mean the production events table itself changed shape
    since M4 close-out."""
    conn = psycopg2.connect(
        host=DB_HOST, port=DB_PORT, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD
    )
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(FETCH_QUERY)
            rows = [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()

    if len(rows) != 68:
        log.warning(
            "Expected 68 promoted ALICE records, found %d. Proceeding with "
            "actual count — not silently coercing to the expected figure.",
            len(rows),
        )
    else:
        log.info("Fetched %d promoted ALICE records from events table.", len(rows))
    return rows


def round_trip_encode(record: dict, parsed_schema: dict) -> bytes:
    """Serialize then immediately deserialize against the locked schema,
    same technique as schema_versioning.round_trip_check(). Raises on
    mismatch rather than publishing an unverified payload."""
    buf = io.BytesIO()
    schemaless_writer(buf, parsed_schema, record)
    encoded = buf.getvalue()

    buf.seek(0)
    decoded = schemaless_reader(buf, parsed_schema)

    for field in parsed_schema["fields"]:
        name = field["name"]
        if decoded.get(name) != record.get(name):
            # float32 rounding is expected for the momentum/energy fields;
            # only flag a real mismatch, not fastavro's own float32 cast.
            if isinstance(record.get(name), float) and isinstance(decoded.get(name), float):
                if abs(decoded[name] - record[name]) < 1e-3:
                    continue
            raise ValueError(
                f"Round-trip mismatch on field '{name}': "
                f"sent={record.get(name)!r} decoded={decoded.get(name)!r}"
            )

    return encoded


def delivery_report(err, msg):
    if err is not None:
        log.error("Delivery failed for event_id=%s: %s", msg.key(), err)
    else:
        log.debug("Delivered event_id=%s to %s[%d]", msg.key(), msg.topic(), msg.partition())


def run():
    global _running
    signal.signal(signal.SIGTERM, _handle_shutdown)
    signal.signal(signal.SIGINT, _handle_shutdown)

    log.info(
        "Starting ALICE Kafka producer — topic=%s bootstrap=%s interval_ms=%d",
        KAFKA_TOPIC_ALICE, KAFKA_BOOTSTRAP_SERVERS, ALICE_REPLAY_INTERVAL_MS,
    )

    parsed_schema = load_schema()
    records = fetch_records()
    if not records:
        log.error("No promoted ALICE records found (source_type='alice' in events). Exiting.")
        sys.exit(1)

    # M5W17T2 fix — see design note #2b: precompute the dataset's own
    # event-time span once, so each loop can be rebased forward by
    # (span + gap) instead of restarting from the earliest timestamp.
    min_ts = min(r["timestamp_ms"] for r in records)
    max_ts = max(r["timestamp_ms"] for r in records)
    loop_span_ms = (max_ts - min_ts) + ALICE_LOOP_GAP_MS
    log.info(
        "Dataset event-time span=%dms; each loop rebased forward by %dms (span + %dms gap).",
        max_ts - min_ts, loop_span_ms, ALICE_LOOP_GAP_MS,
    )

    producer = Producer({"bootstrap.servers": KAFKA_BOOTSTRAP_SERVERS})

    published_total = 0
    round_trip_failed_total = 0
    loop_count = 0

    while _running:
        loop_count += 1
        loop_published = 0
        loop_failed = 0
        # Offset applied to every record's timestamp_ms this loop. Loop 1
        # uses the real, unshifted timestamps (offset=0); loop 2 onward
        # shifts forward so event-time never repeats or goes backward.
        loop_offset_ms = (loop_count - 1) * loop_span_ms

        for record in records:
            if not _running:
                break

            # Stamp schema_version from the registry value rather than
            # trusting the DB column verbatim, same drift-safety posture
            # as schema_versioning.populate_schema_version().
            record = dict(record)
            record["timestamp_ms"] = record["timestamp_ms"] + loop_offset_ms
            if record.get("schema_version") != CURRENT_SCHEMA_VERSION:
                log.warning(
                    "event_id=%s schema_version drift: db=%s expected=%s — stamping expected value.",
                    record.get("event_id"), record.get("schema_version"), CURRENT_SCHEMA_VERSION,
                )
                record["schema_version"] = CURRENT_SCHEMA_VERSION

            try:
                payload = round_trip_encode(record, parsed_schema)
            except ValueError as e:
                round_trip_failed_total += 1
                loop_failed += 1
                log.error("event_id=%s round-trip check failed, NOT publishing: %s", record.get("event_id"), e)
                continue

            producer.produce(
                KAFKA_TOPIC_ALICE,
                key=record["event_id"].encode("utf-8"),
                value=payload,
                callback=delivery_report,
            )
            producer.poll(0)
            published_total += 1
            loop_published += 1

            if ALICE_REPLAY_INTERVAL_MS > 0:
                time.sleep(ALICE_REPLAY_INTERVAL_MS / 1000.0)

        producer.flush(timeout=10)
        log.info(
            "Loop %d complete (timestamp offset=+%dms): published=%d failed=%d "
            "(running totals: published=%d failed=%d)",
            loop_count, loop_offset_ms, loop_published, loop_failed,
            published_total, round_trip_failed_total,
        )

    log.info(
        "Producer stopped. Final totals: loops=%d published=%d round_trip_failed=%d",
        loop_count, published_total, round_trip_failed_total,
    )


if __name__ == "__main__":
    run()