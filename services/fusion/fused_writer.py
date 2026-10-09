"""
DataForge — real write_fused_events() (M6W22T2, closes M4 Item 4).

Called by fusion_engine.py's foreachBatch. Every batch runs through
schema_versioning.enforce() before any row reaches fused_events — same
posture as the M5 staging writers, not a lighter check, because
data_loss_pct here is a quality figure other tables already rely on
meaning the same thing (design note Section 7).
"""

import io
import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from pyspark.sql import DataFrame

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s"
)
log = logging.getLogger(__name__)

# ── Config — same env-var pattern as spark_consumer.py ──────────────────
DB_HOST = os.environ.get("DB_HOST", "localhost")
DB_PORT = os.environ.get(
    "DB_PORT", "5433"
)  # 5433 outside Docker; compose overrides to 5432
DB_NAME = os.environ.get("DB_NAME", "dataforge")
DB_USER = os.environ.get("DB_USER", "dataforge")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "dataforge_dev")

FUSION_WINDOW_MS = int(os.environ.get("FUSION_WINDOW_MS", "500"))

FUSED_SCHEMA_PATH = Path(
    os.environ.get("FUSED_SCHEMA_PATH", "/app/schemas/fused_event_schema_v1.avsc")
)
FUSED_STREAM_NAME = "fused_event"  # key into schema_versioning.CURRENT_SCHEMA_VERSIONS
FUSED_TABLE = "fused_events"

# Exact field order from fused_event_schema_v1.avsc — enforce()'s round-trip
# check encodes positionally, same convention as ALICE_FIELDS/SENSOR_FIELDS
# in spark_consumer.py.
FUSED_FIELDS = [
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

_parsed_schema = None  # loaded once, reused across batches


def _load_parsed_schema():
    global _parsed_schema
    if _parsed_schema is None:
        from fastavro import parse_schema

        with open(FUSED_SCHEMA_PATH, "r", encoding="utf-8") as f:
            _parsed_schema = parse_schema(json.load(f))
    return _parsed_schema


# ── DB connection ─────────────────────────────────────────────────────────
# One shared connection for this service (design note T2: coordinate with T5
# so the heartbeat and the fused write don't contend for separate connections
# — the M5 write-path fault). Beyza's heartbeat writer imports get_connection()
# from this module rather than opening its own.

_connections = []


def _get_db_connection():
    import psycopg2

    return psycopg2.connect(
        host=DB_HOST, port=DB_PORT, dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD
    )


class PersistentConnection:
    """Same shape as spark_consumer.py's — one psycopg2 connection reused
    across micro-batches, reconnected on a broken-connection error."""

    def __init__(self, name: str):
        self.name = name
        self._conn = None
        _connections.append(self)

    def get(self):
        if self._conn is None or self._conn.closed:
            self._conn = _get_db_connection()
            log.info("[%s] opened persistent DB connection.", self.name)
        return self._conn

    def discard(self):
        conn, self._conn = self._conn, None
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass

    close = discard


_fusion_db = PersistentConnection("fusion_write")


def get_connection() -> PersistentConnection:
    """The shared connection for this service. Use this instead of opening a
    second one (design note T2 / T5 coordination note)."""
    return _fusion_db


def close_connections():
    for db in _connections:
        db.close()


# ── COPY insert with the replay-dedup conflict target ────────────────────


def _csv_field(value) -> str:
    if value is None:
        return ""
    return '"' + str(value).replace('"', '""') + '"'


def _copy_buffer(values: list, columns: list) -> io.StringIO:
    buf = io.StringIO()
    for rec in values:
        buf.write(",".join(_csv_field(rec[c]) for c in columns))
        buf.write("\n")
    return buf


def _copy_insert_fused(db: PersistentConnection, values: list) -> int:
    """Same COPY-then-INSERT pattern as spark_consumer.py's _copy_insert, but
    the conflict target is (timestamp_ms, alice_event_id) — the replay-dedup
    index (uq_fused_events_replay), not a single-column key. Retries once on
    a connection-level error, same as the staging writers."""
    import psycopg2

    columns = FUSED_FIELDS
    col_list = ", ".join(columns)
    buf = _copy_buffer(values, columns)

    for attempt in (1, 2):
        conn = db.get()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    f"CREATE TEMP TABLE IF NOT EXISTS tmp_fused_events ON COMMIT DELETE ROWS "
                    f"AS SELECT {col_list} FROM {FUSED_TABLE} WITH NO DATA"
                )
                buf.seek(0)
                cur.copy_expert(
                    f"COPY tmp_fused_events ({col_list}) FROM STDIN WITH (FORMAT csv)",
                    buf,
                )
                cur.execute(
                    f"INSERT INTO {FUSED_TABLE} ({col_list}) "
                    f"SELECT {col_list} FROM tmp_fused_events "
                    f"ON CONFLICT (timestamp_ms, alice_event_id) DO NOTHING"
                )
                inserted = cur.rowcount
            conn.commit()
            return inserted
        except (psycopg2.OperationalError, psycopg2.InterfaceError) as exc:
            db.discard()
            if attempt == 2:
                raise
            log.warning(
                "[fusion_write] DB connection failed (%s) — reconnecting and retrying once.",
                exc,
            )
        except Exception:
            try:
                conn.rollback()
            except Exception:
                db.discard()
            raise


# ── foreachBatch entry point ─────────────────────────────────────────────


def write_fused_events(batch_df: DataFrame, spark_batch_id: int):
    """Closes M4 Item 4. Replaces the NotImplementedError stub that lived in
    avro_adaptation_job.py — that function was a placeholder for exactly this,
    pending the join this now reads from.

    batch_df columns: alice_event_id, timestamp_ms, sensor_event_id,
    sensor_type, abs_dt_ms (fusion_engine.py's select_nearest output).
    abs_dt_ms is for logging only and is not a fused_events column.
    """
    from schema_versioning import enforce  # mounted read-only by docker-compose

    t0 = time.perf_counter()
    rows = [
        r.asDict()
        for r in batch_df.select(
            "alice_event_id", "timestamp_ms", "sensor_event_id", "sensor_type"
        ).collect()
    ]
    t1 = time.perf_counter()

    if not rows:
        log.info(
            "fusion micro-batch %d: empty, nothing to enforce/write.", spark_batch_id
        )
        return

    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

    # data_loss_pct and latency_ms are not yet known — enforce() needs some
    # value to round-trip, and both are recomputed below once the real figures
    # exist (data_loss_pct from this batch's own rejection count; latency_ms
    # from write time). Same ordering as spark_consumer.py's extra_columns,
    # which are likewise assigned after enforce(), not re-verified by it.
    raw_records = [
        {
            "fused_event_id": str(uuid.uuid4()),
            "alice_event_id": r["alice_event_id"],
            "sensor_event_id": r["sensor_event_id"],
            "timestamp_ms": r["timestamp_ms"],
            "fusion_window_ms": FUSION_WINDOW_MS,
            "sensor_type": r["sensor_type"],
            "data_loss_pct": 0.0,
            "latency_ms": 0,
            "schema_version": "1.0",
        }
        for r in rows
    ]

    result = enforce(raw_records, FUSED_STREAM_NAME, _load_parsed_schema())
    t2 = time.perf_counter()

    if result.rejected:
        first = (
            result.round_trip_failed[0][1]
            if result.round_trip_failed
            else f"version drift, fused_event_id={result.version_drift[0].get('fused_event_id')}"
        )
        log.warning(
            "fusion micro-batch %d: %d version drift, %d round-trip failures (first: %s).",
            spark_batch_id,
            len(result.version_drift),
            len(result.round_trip_failed),
            str(first)[:300],
        )

    if not result.valid_records:
        log.warning(
            "fusion micro-batch %d: 0 of %d records passed enforcement — nothing written.",
            spark_batch_id,
            result.total,
        )
        return

    # Design note Section 7: data_loss_pct is the share of THIS micro-batch
    # rejected by enforce() — same definition as the M5 staging writes, so
    # the column means the same thing across tables. latency_ms is write
    # time minus timestamp_ms, computed now so it reflects the actual write.
    values = [
        {
            **rec,
            "data_loss_pct": result.data_loss_pct,
            "latency_ms": now_ms - rec["timestamp_ms"],
        }
        for rec in result.valid_records
    ]

    inserted = _copy_insert_fused(get_connection(), values)
    t3 = time.perf_counter()

    log.info(
        "fusion micro-batch %d: %d written, %d rejected (data_loss_pct=%.4f%%), "
        "%d duplicate(s)/replay(s) skipped | collect=%dms enforce=%dms insert=%dms",
        spark_batch_id,
        inserted,
        result.rejected,
        result.data_loss_pct,
        len(values) - inserted,
        (t1 - t0) * 1000,
        (t2 - t1) * 1000,
        (t3 - t2) * 1000,
    )

    # T5 heartbeat — per-source fusion_status write (M6W22T5).
    # Import is local so spike_join_check.py and tests can import this module
    # without heartbeat_writer on sys.path.
    from heartbeat_writer import write_heartbeat
    avg_latency = sum(v["latency_ms"] for v in values) / len(values) if values else 0.0
    write_heartbeat("alice", result.data_loss_pct, avg_latency, 1.0)
    write_heartbeat("sensor", result.data_loss_pct, avg_latency, 1.0)