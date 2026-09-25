"""
Tests for the Spark consumer's staging write path (M5W20T1).

Unit tests use a fake DB connection, so they run in CI without Kafka, Spark
jobs or Postgres. The last test runs against a real Postgres only when
DATAFORGE_TEST_DB_DSN is set, e.g.:
    DATAFORGE_TEST_DB_DSN="host=localhost port=5433 dbname=dataforge \
        user=dataforge password=dataforge_dev"
It writes into the real staging tables and deletes its own rows afterwards.

Run: pytest services/streaming/spark/src/test_spark_consumer.py -v
"""

import csv
import io
import os
import re
import sys
import uuid
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[4]
# schema_versioning.py, as mounted into the Spark container by docker-compose
sys.path.insert(0, str(REPO / "services" / "adaptation-layer"))

import psycopg2  # noqa: E402
import spark_consumer as sc  # noqa: E402

SENSOR_SCHEMA = sc.load_parsed_avro_schema(REPO / "schemas" / "sensor_schema_v1.avsc")
ALICE_SCHEMA = sc.load_parsed_avro_schema(REPO / "schemas" / "alice_event_schema_v1.avsc")


# ── Fixtures and fakes ──────────────────────────────────────────────────────

def telemetry(**overrides):
    rec = {f: None for f in sc.SENSOR_FIELDS}
    rec.update(event_id=str(uuid.uuid4()), sensor_id=str(uuid.uuid4()), sensor_type="TELEMETRY",
               timestamp_ms=1_790_000_000_000, device_id="SENSOR-UNIT-01",
               parameter_name="cpu_temp_c", value=56.5, unit="C", sequence_number=1,
               schema_version="1.0")
    rec.update(overrides)
    return rec


def alice(**overrides):
    rec = dict(event_id=str(uuid.uuid4()), run_number=137_000, timestamp_ms=1_291_000_000_000,
               track_count=12, net_momentum_x=1.5, net_momentum_y=-2.25, net_momentum_z=0.0,
               max_energy_gev=10.5, total_energy_gev=42.0, schema_version="1.0")
    rec.update(overrides)
    return rec


class FakeBatchDF:
    def __init__(self, rows):
        self.rows = rows

    def select(self, *cols):
        self.cols = cols
        return self

    def collect(self):
        return [type("Row", (), {"asDict": lambda s, r=r: {c: r.get(c) for c in self.cols}})()
                for r in self.rows]


class FakeCursor:
    def __init__(self, conn):
        self.conn = conn
        self.rowcount = 0

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, *args):
        self.conn.sql.append(sql)
        if sql.lstrip().startswith("INSERT"):
            self.rowcount = self.conn.pending_rows

    def copy_expert(self, sql, buf):
        if self.conn.fail_plan:
            raise self.conn.fail_plan.pop(0)
        self.conn.sql.append(sql)
        data = buf.read()
        self.conn.copied.append(data)
        self.conn.pending_rows = data.count("\n")


class FakeConn:
    def __init__(self, registry):
        registry.append(self)
        self.closed = 0
        self.sql, self.copied = [], []
        self.commits = self.rollbacks = 0
        self.pending_rows = 0
        self.fail_plan = registry.fail_plan

    def cursor(self):
        return FakeCursor(self)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = 1


class Registry(list):
    fail_plan: list = []


@pytest.fixture
def fake_db(monkeypatch):
    reg = Registry()
    reg.fail_plan = []
    monkeypatch.setattr(sc, "_get_db_connection", lambda: FakeConn(reg))
    return reg


# ── COPY encoding ───────────────────────────────────────────────────────────

def test_csv_field_null_vs_empty_and_quoting():
    assert sc._csv_field(None) == ""            # unquoted empty = NULL in COPY CSV
    assert sc._csv_field("") == '""'            # quoted empty = empty string
    assert sc._csv_field('say "hi"') == '"say ""hi"""'
    assert sc._csv_field("a,b") == '"a,b"'
    assert sc._csv_field(-0.0) == '"-0.0"'
    assert sc._csv_field(2**63 - 1) == f'"{2**63 - 1}"'


def test_copy_buffer_round_trips_awkward_values():
    tricky = ["", "a,b", 'q"q', "line1\nline2", "cr\r\nlf", "back\\slash", "\\N", "tab\t", "ünï 🚀"]
    cols = ["a", "b"]
    rows = [{"a": s, "b": None} for s in tricky] + [{"a": 1.0 / 3, "b": 3.4e38}]
    parsed = list(csv.reader(io.StringIO(sc._copy_buffer(rows, cols).getvalue())))
    assert [r[0] for r in parsed] == [str(x["a"]) for x in rows]
    assert all(r[1] == "" for r in parsed[:-1])           # NULLs
    assert float(parsed[-1][1]) == 3.4e38                   # floats survive as repr text


# ── Column lists guard against DDL drift ────────────────────────────────────

def _ddl_columns(table):
    sql = (REPO / "infrastructure" / "scripts" / "init-db.sql").read_text(encoding="utf-8")
    body = re.search(rf"CREATE TABLE IF NOT EXISTS {table} \((.*?)\n\);", sql, re.S).group(1)
    return [line.split()[0] for line in body.strip().splitlines() if line.strip()]


@pytest.mark.parametrize("table,columns", [
    (sc.SENSOR_STAGING_TABLE, sc.SENSOR_STAGING_COLUMNS),
    (sc.ALICE_STAGING_TABLE, sc.ALICE_STAGING_COLUMNS),
])
def test_staging_columns_match_init_db_sql(table, columns):
    assert columns == [c for c in _ddl_columns(table) if c != "load_id"]


# ── Writer behaviour (fake DB) ──────────────────────────────────────────────

def test_one_connection_reused_and_copy_then_insert(fake_db):
    write = sc.make_sensor_batch_writer(SENSOR_SCHEMA)
    for i in range(5):
        write(FakeBatchDF([telemetry() for _ in range(3)]), i)
    assert len(fake_db) == 1
    conn = fake_db[0]
    assert conn.commits == 5
    first_batch = conn.sql[:3]
    assert first_batch[0].startswith(
        "CREATE TEMP TABLE IF NOT EXISTS tmp_raw_sensor_events_staging")
    assert first_batch[1].startswith("COPY tmp_raw_sensor_events_staging")
    assert "ON CONFLICT (event_id) DO NOTHING" in first_batch[2]
    assert all(data.count("\n") == 3 for data in conn.copied)


def test_sensor_rows_carry_label_defaults(fake_db):
    sc.make_sensor_batch_writer(SENSOR_SCHEMA)(FakeBatchDF([telemetry()]), 0)
    row = next(csv.reader(io.StringIO(fake_db[0].copied[0])))
    by_col = dict(zip(sc.SENSOR_STAGING_COLUMNS, row))
    assert by_col["label"] == "0" and by_col["anomaly_type"] == ""
    assert by_col["load_status"] == "validated" and by_col["schema_version"] == "1.0"


def test_connection_error_reconnects_once_and_resends_full_batch(fake_db):
    fake_db.fail_plan.append(psycopg2.OperationalError("server closed the connection"))
    sc.make_alice_batch_writer(ALICE_SCHEMA)(FakeBatchDF([alice() for _ in range(4)]), 0)
    assert len(fake_db) == 2 and fake_db[0].closed
    assert fake_db[1].copied[0].count("\n") == 4        # buffer rewound, nothing lost


def test_persistent_outage_raises_after_one_retry(fake_db):
    fake_db.fail_plan.extend([psycopg2.OperationalError("down")] * 2)
    with pytest.raises(psycopg2.OperationalError):
        sc.make_alice_batch_writer(ALICE_SCHEMA)(FakeBatchDF([alice()]), 0)
    assert len(fake_db) == 2


def test_data_error_rolls_back_without_reconnecting(fake_db):
    fake_db.fail_plan.append(psycopg2.DataError("bad value"))
    write = sc.make_alice_batch_writer(ALICE_SCHEMA)
    with pytest.raises(psycopg2.DataError):
        write(FakeBatchDF([alice()]), 0)
    assert len(fake_db) == 1 and fake_db[0].rollbacks == 1 and not fake_db[0].closed
    write(FakeBatchDF([alice()]), 1)                     # same connection still usable
    assert len(fake_db) == 1 and fake_db[0].commits == 1


def test_empty_and_fully_rejected_batches_touch_no_db(fake_db):
    write = sc.make_sensor_batch_writer(SENSOR_SCHEMA)
    write(FakeBatchDF([]), 0)
    write(FakeBatchDF([telemetry(schema_version="9.9")]), 1)   # version drift -> rejected
    assert fake_db == []


# ── Kafka source options ────────────────────────────────────────────────────

class FakeReader:
    def __init__(self):
        self.options = {}

    def format(self, fmt):
        self.fmt = fmt
        return self

    def option(self, key, value):
        self.options[key] = value
        return self

    def load(self):
        return self


def _kafka_options(monkeypatch, **config):
    for key, value in config.items():
        monkeypatch.setattr(sc, key, value)
    reader = FakeReader()
    fake_spark = type("Spark", (), {"readStream": reader})()
    sc._read_kafka(fake_spark, "topic-a,topic-b")
    return reader.options


def test_kafka_defaults_cap_batches_and_start_latest(monkeypatch):
    opts = _kafka_options(monkeypatch, SPARK_MAX_OFFSETS_PER_TRIGGER=50000,
                          SPARK_STARTING_TIMESTAMP_MS="")
    assert opts["subscribe"] == "topic-a,topic-b"
    assert opts["startingOffsets"] == "latest"
    assert opts["maxOffsetsPerTrigger"] == 50000
    assert "startingTimestamp" not in opts


def test_kafka_cap_disabled_and_timestamp_replay(monkeypatch):
    opts = _kafka_options(monkeypatch, SPARK_MAX_OFFSETS_PER_TRIGGER=0,
                          SPARK_STARTING_TIMESTAMP_MS="1790000000000")
    assert "maxOffsetsPerTrigger" not in opts
    assert opts["startingTimestamp"] == "1790000000000"
    assert opts["startingOffsetsByTimestampStrategy"] == "latest"


# ── Optional: real Postgres ────────────────────────────────────────────────

DSN = os.environ.get("DATAFORGE_TEST_DB_DSN")


@pytest.mark.skipif(not DSN, reason="set DATAFORGE_TEST_DB_DSN to run against a real Postgres")
def test_real_db_values_nulls_and_duplicates(monkeypatch):
    monkeypatch.setattr(sc, "_get_db_connection", lambda: psycopg2.connect(DSN))
    recs = [telemetry(unit=""), telemetry(unit=None), telemetry(parameter_name='a,"b"\nc'),
            telemetry(value=-0.0), telemetry(value=1.0 / 3)]
    recs.append(dict(recs[0]))                               # in-batch duplicate
    ids = sorted({r["event_id"] for r in recs})
    write = sc.make_sensor_batch_writer(SENSOR_SCHEMA)
    try:
        write(FakeBatchDF(recs), 0)
        write(FakeBatchDF(recs[:2]), 1)                      # redelivery: nothing new
        with psycopg2.connect(DSN) as conn, conn.cursor() as cur:
            cur.execute("SELECT event_id::text, unit, parameter_name, value "
                        "FROM raw_sensor_events_staging "
                        "WHERE event_id::text = ANY(%s) ORDER BY load_id", (ids,))
            got = {r[0]: r[1:] for r in cur.fetchall()}
        assert len(got) == 5
        assert got[recs[0]["event_id"]][0] == "" and got[recs[1]["event_id"]][0] is None
        assert got[recs[2]["event_id"]][1] == 'a,"b"\nc'
        assert got[recs[4]["event_id"]][2] == pytest.approx(1.0 / 3, rel=1e-6)
    finally:
        with psycopg2.connect(DSN) as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM raw_sensor_events_staging "
                        "WHERE event_id::text = ANY(%s)", (ids,))
        sc._close_persistent_connections()
