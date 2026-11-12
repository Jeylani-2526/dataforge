"""M7W27T1 — tests for feature_assembly and the live/corpus alignment."""

import importlib
import json
import math
import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

import feature_assembly as fa  # noqa: E402

STATS = {
    "cpu_temp_c": {"mean": 55.0, "std": 10.0},
    "voltage_v": {"mean": 12.0, "std": 0.5},
    "battery_pct": {"mean": 60.0, "std": 20.0},
}


def tel(seq, ts, device="D1", name="cpu_temp_c", value=55.0):
    return {"device_id": device, "sequence_number": seq, "timestamp_ms": ts,
            "parameter_name": name, "value": value}


# ── featurize ───────────────────────────────────────────────────────────

def test_feature_lengths_match_names():
    radar = dict(range_m=1, bearing_deg=2, elevation_deg=3, velocity_ms=4, signal_strength_db=-5)
    lidar = dict(point_count=1000, centroid_x_m=3, centroid_y_m=4, centroid_z_m=0,
                 max_range_m=10, avg_intensity=100, min_intensity=30)
    assert len(fa.featurize("radar", radar)) == len(fa.FEATURES["radar"])
    assert len(fa.featurize("lidar", lidar)) == len(fa.FEATURES["lidar"])
    assert len(fa.featurize("telemetry", tel(1, 0), STATS)) == len(fa.FEATURES["telemetry"])


def test_lidar_log_count_and_range_ratio():
    rec = dict(point_count=999, centroid_x_m=3, centroid_y_m=4, centroid_z_m=0,
               max_range_m=10, avg_intensity=100, min_intensity=30)
    f = fa.featurize("lidar", rec)
    assert f[0] == pytest.approx(math.log1p(999))
    assert f[-1] == pytest.approx(0.5)  # |(3,4,0)| = 5, / 10


def test_lidar_zero_max_range_does_not_divide_by_zero():
    rec = dict(point_count=1, centroid_x_m=1, centroid_y_m=1, centroid_z_m=1,
               max_range_m=0, avg_intensity=1, min_intensity=1)
    assert fa.featurize("lidar", rec)[-1] == 0.0


def test_telemetry_standardised_per_parameter():
    assert fa.featurize("telemetry", tel(1, 0, value=65.0), STATS) == [pytest.approx(1.0)]
    assert fa.featurize("telemetry", tel(1, 0, name="voltage_v", value=11.0),
                        STATS) == [pytest.approx(-2.0)]


def test_scoring_row_and_corpus_record_give_same_features():
    """A staging row carries extra columns; features must not change."""
    corpus = dict(range_m=100.5, bearing_deg=10, elevation_deg=5, velocity_ms=20,
                  signal_strength_db=-40)
    staging = dict(corpus, fused_event_id="x", sensor_type="RADAR", staging_event_id="e",
                   point_count=None, value=None, label=0)
    assert fa.featurize("radar", corpus) == fa.featurize("radar", staging)


# ── integrity rules ─────────────────────────────────────────────────────

def test_rules_normal_sequence_not_flagged():
    assert fa.sequence_flags([tel(1, 1000), tel(2, 2000), tel(3, 3000)]) == [None, None, None]


def test_rule_sequence_gap():
    assert fa.sequence_flag(tel(1, 1000), tel(5, 2000)) == "sequence_gap"


def test_rule_timestamp_not_advancing():
    assert fa.sequence_flag(tel(1, 1000), tel(2, 1000)) == "timestamp_not_advancing"


def test_record_after_an_anomaly_is_not_flagged():
    # gap at seq 9, then the stream resumes at 3: one-sided rules stay quiet
    flags = fa.sequence_flags([tel(1, 1000), tel(9, 2000), tel(3, 3000)])
    assert flags == [None, "sequence_gap", None]


def test_rules_are_per_device():
    flags = fa.sequence_flags([tel(1, 1000, "A"), tel(7, 1100, "B"), tel(2, 2000, "A")])
    assert flags == [None, None, None]


# ── scoring-row assembly ────────────────────────────────────────────────

def test_assemble_reports_missing_staging_row():
    stream, feats, why = fa.assemble_scoring_row({"sensor_type": "RADAR", "staging_event_id": None},
                                                 STATS)
    assert (stream, feats, why) == ("radar", None, "no staging row")


def test_assemble_reports_unknown_parameter():
    row = dict(tel(1, 0, name="altitude_m"), sensor_type="TELEMETRY", staging_event_id="e")
    assert fa.assemble_scoring_row(row, STATS)[2] == "unknown parameter altitude_m"


def test_scoring_sql_keeps_fused_sensor_type():
    """Regression: s.* used to overwrite f.sensor_type with NULL on a missing join."""
    select = fa.SCORING_SQL.split("FROM")[0]
    assert "s.*" not in select
    assert "s.sensor_type" not in select


# ── live producer stays inside the corpus's normal ranges ───────────────

def _import_producer():
    stubs = {
        "confluent_kafka": types.SimpleNamespace(Producer=object),
        "fastavro": types.SimpleNamespace(parse_schema=None, schemaless_writer=None),
        "dotenv": types.SimpleNamespace(load_dotenv=lambda *a, **k: None),
        "injection": types.SimpleNamespace(Injector=object),
    }
    for name, mod in stubs.items():
        sys.modules.setdefault(name, mod)
    src = ROOT / "services/data-sources/sensor-generators/src"
    sys.path.insert(0, str(src))
    return importlib.import_module("sensor_producer")


def _corpus_normal_bounds(stream, cols):
    lo = {c: math.inf for c in cols}
    hi = {c: -math.inf for c in cols}
    with open(ROOT / "data/synthetic" / f"{stream}.jsonl", encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            if r["label"] == 0:
                for c in cols:
                    lo[c] = min(lo[c], r[c])
                    hi[c] = max(hi[c], r[c])
    return lo, hi


@pytest.mark.parametrize("stream,gen,cols", [
    ("radar", "generate_radar", fa.REQUIRED["radar"]),
    ("lidar", "generate_lidar", fa.REQUIRED["lidar"]),
])
def test_live_producer_matches_corpus_normal(stream, gen, cols):
    producer = _import_producer()
    lo, hi = _corpus_normal_bounds(stream, cols)
    for _ in range(3000):
        rec = getattr(producer, gen)()
        for c in cols:
            margin = 0.01 * (hi[c] - lo[c])
            assert lo[c] - margin <= rec[c] <= hi[c] + margin, (stream, c, rec[c])


def test_live_telemetry_parameters_match_corpus():
    producer = _import_producer()
    live = {name for name, _, _ in producer.TELEMETRY_PARAMS}
    stats = json.loads((ROOT / fa.STATS_PATH).read_text(encoding="utf-8"))
    assert live == set(stats)
