"""M7W28T3 — tests for batch scoring (no database needed)."""

import sys
from pathlib import Path

import pytest

np = pytest.importorskip("numpy")
pytest.importorskip("sklearn")

sys.path.insert(0, str(Path(__file__).resolve().parent))

import batch_score as bs  # noqa: E402
import feature_assembly as fa  # noqa: E402
import model_v2 as v2  # noqa: E402


def _tel_stream(n, device="UAV-01", start_seq=1, start_ms=0):
    return [{"event_id": f"{device}-{start_seq + i}-{start_ms}", "device_id": device,
             "sequence_number": start_seq + i, "timestamp_ms": start_ms + i * 200}
            for i in range(n)]


def test_rules_on_full_stream_do_not_flag_the_fused_subset():
    stream = _tel_stream(30)
    flags = bs.telemetry_rule_flags(stream)
    fused_ids = [r["event_id"] for r in stream[::3]]       # fusion keeps every third
    assert all(flags[e] == "" for e in fused_ids)
    # The same rule over the fused subset alone would flag almost every row.
    naive = fa.sequence_flags(stream[::3])
    assert sum(f == "sequence_gap" for f in naive) == len(naive) - 1


def test_producer_restart_is_not_a_gap():
    stream = _tel_stream(10) + _tel_stream(10, start_ms=10 * 200)   # counter restarts at 1
    assert set(bs.telemetry_rule_flags(stream).values()) == {""}


def test_missing_record_in_staging_is_flagged():
    stream = _tel_stream(10)
    del stream[5]
    flags = bs.telemetry_rule_flags(stream)
    assert flags[stream[5]["event_id"]] == "sequence_gap"


def test_parse_since_needs_a_time_zone():
    assert bs.parse_since("2026-11-12T07:06:00Z") == 1794467160000
    with pytest.raises(SystemExit):
        bs.parse_since("2026-11-12T07:06:00")


class _FakeScorer:
    def score(self, X, rule=None):
        n = len(X)
        risk = np.linspace(0.0, 1.0, n)
        if rule is not None:
            risk = np.where(rule != "", 1.0, risk)
        label, risk, conf = v2.decide(risk, np.zeros(n))
        return {"anomaly_label": label, "risk_score": risk, "confidence": conf,
                "reason": ["rule:x" if r else "" for r in (rule if rule is not None else [""] * n)]}


def _row(i, sensor_type, staging=True, **feats):
    row = {"fused_event_id": f"f{i}", "fused_timestamp_ms": 1000 + i, "sensor_type": sensor_type,
           "staging_event_id": f"s{i}" if staging else None}
    row.update(feats)
    return row


def test_unassembled_rows_are_skipped_and_updates_are_plain_python():
    radar = dict(range_m=1000.0, bearing_deg=10.0, elevation_deg=5.0, velocity_ms=50.0,
                 signal_strength_db=-50.0)
    rows = [_row(i, "RADAR", **radar) for i in range(4)] + [_row(9, "RADAR", staging=False)]
    updates, summary = bs.score_rows(rows, {}, {}, {"radar": _FakeScorer()})
    assert summary["skipped"] == {"no staging row": 1}
    assert len(updates) == 4 and "f9" not in {u[0] for u in updates}
    for fid, ts, lab, risk, conf in updates:
        assert type(lab) is int and type(risk) is float and type(conf) is float
        assert lab in (0, 1) and 0.0 <= risk <= 1.0 and 0.0 <= conf <= 1.0


def test_telemetry_rule_result_reaches_the_scorer():
    stats = {"temperature": {"mean": 20.0, "std": 5.0}}
    tel = dict(device_id="UAV-01", parameter_name="temperature", value=21.0, sequence_number=1,
               timestamp_ms=0)
    rows = [_row(i, "TELEMETRY", **tel) for i in range(3)]
    updates, _ = bs.score_rows(rows, {"s1": "sequence_gap"}, stats,
                               {"telemetry": _FakeScorer()})
    by_id = {u[0]: u for u in updates}
    assert by_id["f1"][2:4] == (1, 1.0)
