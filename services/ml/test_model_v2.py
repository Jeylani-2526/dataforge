"""M7W28T1 — tests for model v2 (combined detector)."""

import json
import sys
from pathlib import Path

import pytest

np = pytest.importorskip("numpy")
pytest.importorskip("sklearn")

sys.path.insert(0, str(Path(__file__).resolve().parent))

import model_v2 as v2  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]


def _card():
    return json.loads((ROOT / v2.CARD).read_text("utf-8"))


def test_alarm_when_either_detector_crosses_the_line():
    risk_if = np.array([0.10, 0.995, 0.10, 0.9949])
    risk_z = np.array([0.10, 0.10, 0.995, 0.9949])
    label, risk, _ = v2.decide(risk_if, risk_z)
    assert list(label) == [0, 1, 1, 0]
    assert list(risk) == list(np.maximum(risk_if, risk_z))


def test_rule_hit_forces_risk_one_and_alarm():
    label, risk, conf = v2.decide(np.array([0.1, 0.1]), np.array([0.1, 0.1]),
                                  np.array([True, False]))
    assert (label[0], risk[0], conf[0]) == (1, 1.0, 1.0)
    assert label[1] == 0


def test_outputs_stay_inside_the_db_check_ranges():
    grid = np.linspace(0, 1, 201)
    a, b = np.meshgrid(grid, grid)
    label, risk, conf = v2.decide(a.ravel(), b.ravel())
    assert set(label) <= {0, 1}
    assert risk.min() >= 0.0 and risk.max() <= 1.0
    assert conf.min() >= 0.0 and conf.max() <= 1.0


def test_confidence_is_zero_at_the_line():
    _, _, conf = v2.decide(np.array([v2.ALARM_LINE, 0.0, 1.0]), np.zeros(3))
    assert conf[0] == pytest.approx(0.0)
    assert conf[1] == pytest.approx(1.0) and conf[2] == pytest.approx(1.0)


def test_reason_names_the_detector_and_feature():
    why = v2.reasons(np.array([0.999, 0.1, 0.1]), np.array([0.999, 0.1, 0.1]),
                     np.array([1, 0, 0]), ["a", "b"], np.array(["", "", "sequence_gap"]))
    assert why == ["isolation_forest+zscore:b", "", "rule:sequence_gap"]


def test_model_card_matches_the_code_settings():
    card = _card()
    assert card["model_version"] == v2.MODEL_VERSION
    assert card["alarm_line_per_detector"] == v2.ALARM_LINE
    assert set(card["streams"]) == {"radar", "lidar", "telemetry"}


def test_model_card_meets_the_prototype_bar():
    card = _card()
    for name, m in list(card["streams"].items()) + [("pooled", card["pooled"])]:
        assert m["auc"] >= 0.85, name
        assert m["fpr"] <= 0.05, name


def test_card_reproduces_the_m7w27t3_combined_figures():
    """v2 is the 'either, half budget' detector M7W27T3 recommended — same numbers."""
    t3 = json.loads((ROOT / "services/ml/artifacts/baseline_comparison.json").read_text("utf-8"))
    for stream, m in _card()["streams"].items():
        ref = t3["streams"][stream]["test"]["either_half_budget"]
        for k in ("auc", "fpr", "recall", "precision"):
            assert m[k] == pytest.approx(ref[k]), (stream, k)
