"""
DataForge — Round-Trip Format-Conversion Test Suite (Avro -> Parquet -> Avro)
Task: M4W15T3
Owner: Abdullah

Extends the Avro -> Avro round-trip technique (schema_versioning.
round_trip_check) one layer further, driving a record through the full
storage path the adaptation layer uses:

    Avro (adaptation job output)
      -> Parquet (parquet_writer.py, M4W14T4 — existing, unmodified)
      -> Avro (parquet_to_avro.py, M4W15T3 — new, this task)

Confirms the record that comes out matches what went in, for all four
streams: alice_event and the sensor schema's RADAR/LIDAR/TELEMETRY
variants. Checks per stream: (1) data-integrity, floats compared at
float32 precision; (2) schema_version propagates unchanged through the
Parquet leg.

Fixtures: reuses the existing per-stream test records under /schemas/
rather than duplicating them.

Run directly: pytest services/adaptation-layer/test_round_trip_conversion.py -v
Also auto-discovered by CI's test-python stage (ci.yml Stage 3), which
now installs services/adaptation-layer/requirements.txt (pyspark,
fastavro) before pytest so this suite collects correctly.
"""

import json
from pathlib import Path

import pytest
from fastavro import parse_schema, reader as avro_reader, writer as avro_writer

from avro_adaptation_job import ALICE_FIELDS, SENSOR_FIELDS
from parquet_to_avro import convert_parquet_to_avro
from parquet_writer import convert_alice_to_parquet, convert_sensor_streams_to_parquet
from schema_versioning import CURRENT_SCHEMA_VERSIONS, _avro_field_types, _float32_round

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_DIR = REPO_ROOT / "schemas"
TEST_RECORDS_DIR = SCHEMA_DIR / "test_records"


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def spark():
    """
    One Spark session for the whole module — matches the cost profile of
    the pipeline's own get_spark_session() calls (session creation is the
    expensive part; individual conversions are cheap against it).
    """
    from pyspark.sql import SparkSession

    session = (
        SparkSession.builder.appName("dataforge-round-trip-tests")
        .master("local[1]")
        .config("spark.sql.session.timeZone", "UTC")
        .getOrCreate()
    )
    yield session
    session.stop()


def _load_schema(filename: str) -> dict:
    with open(SCHEMA_DIR / filename, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return parse_schema(raw)


def _load_record(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        record = json.load(f)
    # Strip the same "_comment" helper key validate_schema.py already
    # strips — these test fixtures are shared across tools.
    return {k: v for k, v in record.items() if k != "_comment"}


def _normalize_floats(record: dict, parsed_schema: dict) -> dict:
    """
    Normalizes a record's `float`-typed fields to float32 precision for
    comparison, exactly as schema_versioning.round_trip_check does for
    its own Avro-only round trip. A field declared `float` in the schema
    is only ever supposed to carry float32 precision, so this is the
    correct expected baseline, not a workaround.
    """
    field_types = _avro_field_types(parsed_schema)
    normalized = dict(record)
    for key, value in normalized.items():
        is_numeric = isinstance(value, (int, float)) and value is not None
        if field_types.get(key) == "float" and is_numeric:
            normalized[key] = _float32_round(value)
    return normalized


def _run_round_trip(
    spark,
    tmp_path: Path,
    stream_label: str,
    avro_input_subdir: str,
    schema_filename: str,
    schema_version_key: str,
    field_order: list,
    input_records: list,
    parquet_convert_fn,
    parquet_subdir: str,
):
    """
    Shared driver for the Avro -> Parquet -> Avro loop. Returns the list
    of decoded records read back from the final Avro file, in file order,
    for the caller to assert against.

    avro_input_subdir must match the fixed directory name parquet_writer's
    convert_* functions actually look for ("alice_event" or "sensor_event"
    — see parquet_writer.py's input_dir construction), which is NOT the
    same as stream_label: stream_label only names this test case's output
    file and is per-sensor-type (e.g. "sensor_event_radar") to keep the
    three sensor sub-cases' output files from colliding, while all three
    still write into the one shared "sensor_event" input directory the
    real pipeline uses.
    """
    parsed_schema = _load_schema(schema_filename)

    avro_root = tmp_path / "avro" / avro_input_subdir
    parquet_root = tmp_path / "parquet"
    avro_back_path = tmp_path / "avro_roundtrip" / f"{stream_label}.avro"

    # ---- Leg 1: write the starting Avro file (mirrors
    # avro_adaptation_job._write_partition_to_avro's container-writer call) ----
    avro_root.mkdir(parents=True, exist_ok=True)
    avro_in_path = avro_root / "part-00000.avro"
    with open(avro_in_path, "wb") as f:
        avro_writer(f, parsed_schema, input_records)

    # ---- Leg 2: Avro -> Parquet, via the EXISTING M4W14T4 writer,
    # unmodified. avro_root's parent is passed since parquet_writer's
    # convert_* functions each append their own stream subdirectory. ----
    written_count = parquet_convert_fn(spark, avro_root.parent, parquet_root)
    if isinstance(written_count, dict):
        written_count = written_count[parquet_subdir]
    assert written_count == len(input_records), (
        f"[{stream_label}] Avro->Parquet leg dropped records: "
        f"wrote {written_count}, expected {len(input_records)}"
    )

    # ---- Leg 3: Parquet -> Avro, via the NEW M4W15T3 module ----
    parquet_dir = parquet_root / parquet_subdir
    round_tripped_count = convert_parquet_to_avro(
        spark, parquet_dir, parsed_schema, field_order, avro_back_path
    )
    assert round_tripped_count == len(input_records), (
        f"[{stream_label}] Parquet->Avro leg dropped records: "
        f"wrote {round_tripped_count}, expected {len(input_records)}"
    )

    # ---- Read back the final Avro file ----
    with open(avro_back_path, "rb") as f:
        decoded = list(avro_reader(f))

    return decoded, parsed_schema


def _assert_records_match(
    original: dict, decoded: dict, parsed_schema: dict, stream_version_key: str
):
    expected = _normalize_floats(original, parsed_schema)
    actual = _normalize_floats(decoded, parsed_schema)

    assert actual == expected, (
        f"Round-trip mismatch.\nOriginal (float32-normalized): {expected}\n"
        f"Decoded (float32-normalized): {actual}"
    )

    expected_version = CURRENT_SCHEMA_VERSIONS[stream_version_key]
    assert decoded["schema_version"] == expected_version, (
        f"schema_version did not propagate through the round trip: "
        f"got {decoded['schema_version']!r}, expected {expected_version!r}"
    )


# ---------------------------------------------------------------------------
# ALICE stream
# ---------------------------------------------------------------------------


def test_alice_event_round_trip(spark, tmp_path):
    original = _load_record(SCHEMA_DIR / "alice_event_test_record.json")

    decoded_records, parsed_schema = _run_round_trip(
        spark,
        tmp_path,
        stream_label="alice_event",
        avro_input_subdir="alice_event",
        schema_filename="alice_event_schema_v1.avsc",
        schema_version_key="alice_event",
        field_order=ALICE_FIELDS,
        input_records=[original],
        parquet_convert_fn=convert_alice_to_parquet,
        parquet_subdir="alice_event",
    )

    assert len(decoded_records) == 1
    _assert_records_match(original, decoded_records[0], parsed_schema, "alice_event")


# ---------------------------------------------------------------------------
# Sensor stream — RADAR / LIDAR / TELEMETRY
#
# KNOWN ISSUE surfaced while building this suite (see conversation notes /
# Week 15 update): parquet_writer.records_to_dataframe() calls
# spark.createDataFrame(records) with no explicit schema. If a batch
# contains only one sensor_type, every column belonging to the *other*
# two subtypes is None in every row, and Spark's type inference cannot
# determine a type for an all-null column — it raises
# PySparkValueError: CANNOT_DETERMINE_TYPE. This is NOT hit by the real
# pipeline today because the adaptation job always writes RADAR, LIDAR,
# and TELEMETRY into one shared sensor_event Avro output before the
# Parquet writer reads it back, so every column has at least one non-null
# value across the combined batch (proven by the passing test below).
# But it IS a real fragility: any future single-type sensor batch (a
# partial partition, a backfill of one sensor_type, a unit test in
# isolation) will hit this exact crash. Filed as an M4W15T3 finding
# rather than fixed here — fixing parquet_writer.py's schema-inference
# behavior is a parquet_writer.py change outside this task's scope, not
# a test-suite change. See explicit_schema_recommendation in the Week 15
# update draft.
# ---------------------------------------------------------------------------


def test_sensor_streams_round_trip_combined_batch(spark, tmp_path):
    """
    Writes RADAR, LIDAR, and TELEMETRY test records into ONE Avro file —
    matching how avro_adaptation_job.py actually produces the unified
    sensor_event stream in production (all three subtypes in the same
    output, split into separate Parquet datasets only at the Parquet-
    writer stage) — then verifies each subtype round-trips correctly
    through its own split Parquet dataset back to Avro.
    """
    fixtures = {
        "RADAR": "sensor_radar_test_record.json",
        "LIDAR": "sensor_lidar_test_record.json",
        "TELEMETRY": "sensor_telemetry_test_record.json",
    }
    originals = {}
    for sensor_type, filename in fixtures.items():
        record = _load_record(TEST_RECORDS_DIR / filename)
        assert record["sensor_type"] == sensor_type, (
            f"Fixture {filename} sensor_type={record['sensor_type']!r} "
            f"does not match expected {sensor_type!r} — check the fixture file."
        )
        originals[sensor_type] = record

    combined_input = [originals["RADAR"], originals["LIDAR"], originals["TELEMETRY"]]

    parsed_schema = _load_schema("sensor_schema_v1.avsc")
    avro_root = tmp_path / "avro" / "sensor_event"
    parquet_root = tmp_path / "parquet"

    # ---- Leg 1: one combined Avro file, all three subtypes ----
    avro_root.mkdir(parents=True, exist_ok=True)
    with open(avro_root / "part-00000.avro", "wb") as f:
        avro_writer(f, parsed_schema, combined_input)

    # ---- Leg 2: Avro -> Parquet (existing M4W14T4 writer, unmodified) ----
    counts = convert_sensor_streams_to_parquet(spark, tmp_path / "avro", parquet_root)
    assert counts == {"radar": 1, "lidar": 1, "telemetry": 1}, (
        f"Avro->Parquet leg produced unexpected per-type counts: {counts}"
    )

    # ---- Leg 3: Parquet -> Avro (new M4W15T3 module), per subtype ----
    for sensor_type in fixtures:
        parquet_dir = parquet_root / sensor_type.lower()
        avro_back_path = tmp_path / "avro_roundtrip" / f"sensor_event_{sensor_type.lower()}.avro"

        round_tripped_count = convert_parquet_to_avro(
            spark, parquet_dir, parsed_schema, SENSOR_FIELDS, avro_back_path
        )
        assert round_tripped_count == 1, (
            f"[{sensor_type}] Parquet->Avro leg dropped records: "
            f"wrote {round_tripped_count}, expected 1"
        )

        with open(avro_back_path, "rb") as f:
            decoded_records = list(avro_reader(f))

        assert len(decoded_records) == 1
        _assert_records_match(
            originals[sensor_type], decoded_records[0], parsed_schema, "sensor_event"
        )


def test_sensor_single_type_batch_hits_known_spark_inference_gap(spark, tmp_path):
    """
    Documents the CANNOT_DETERMINE_TYPE fragility described above as a
    reproducible, intentional test rather than an unexplained skip: a
    single-sensor-type batch is expected to fail Spark's schema
    inference in parquet_writer.records_to_dataframe(), since every
    column belonging to the other two subtypes is null in every row.

    If this test starts FAILING (i.e. the call stops raising), that
    means parquet_writer.py's schema inference has changed — likely
    because an explicit schema was added — and this test (and the
    finding it documents) should be revisited/removed rather than left
    stale.
    """
    original = _load_record(TEST_RECORDS_DIR / "sensor_radar_test_record.json")

    parsed_schema = _load_schema("sensor_schema_v1.avsc")
    avro_root = tmp_path / "avro" / "sensor_event"
    avro_root.mkdir(parents=True, exist_ok=True)
    with open(avro_root / "part-00000.avro", "wb") as f:
        avro_writer(f, parsed_schema, [original])

    from pyspark.errors.exceptions.base import PySparkValueError

    with pytest.raises(PySparkValueError, match="CANNOT_DETERMINE_TYPE"):
        convert_sensor_streams_to_parquet(spark, tmp_path / "avro", tmp_path / "parquet")
