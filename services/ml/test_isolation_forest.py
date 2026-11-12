"""M7W27T2 — tests for the risk score, the alarm line and the model card."""

import json
import sys
from pathlib import Path

import pytest

np = pytest.importorskip("numpy")
pytest.importorskip("sklearn")

sys.path.insert(0, str(Path(__file__).resolve().parent))

import isolation_forest as iso  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]


def test_risk_is_share_of_normal_scores_at_or_below():
    ref = np.array([0.1, 0.2, 0.3, 0.4])
    risk = iso.risk_from_scores(np.array([0.05, 0.2, 0.35, 0.9]), ref)
    assert list(risk) == [0.0, 0.5, 0.75, 1.0]


def test_alarm_line_is_inclusive_at_threshold():
    label, _, _ = iso.decide(np.array([0.9899, 0.99, 1.0]))
    assert list(label) == [0, 1, 1]


def test_rule_hit_forces_risk_one_and_alarm():
    label, risk, conf = iso.decide(np.array([0.10, 0.10]), np.array([True, False]))
    assert (label[0], risk[0], conf[0]) == (1, 1.0, 1.0)
    assert label[1] == 0


def test_outputs_stay_inside_the_db_check_ranges():
    risk_in = np.linspace(0, 1, 501)
    label, risk, conf = iso.decide(risk_in)
    assert set(label) <= {0, 1}
    assert risk.min() >= 0.0 and risk.max() <= 1.0
    assert conf.min() >= 0.0 and conf.max() <= 1.0


def test_confidence_is_zero_at_the_line_and_grows_away_from_it():
    _, _, conf = iso.decide(np.array([0.0, 0.5, 0.99, 0.995, 1.0]))
    assert conf[0] == pytest.approx(1.0)
    assert conf[2] == pytest.approx(0.0)
    assert conf[1] > conf[2] and conf[4] > conf[3] > conf[2]


def test_decide_does_not_modify_its_input():
    risk_in = np.array([0.2, 0.3])
    iso.decide(risk_in, np.array([True, True]))
    assert list(risk_in) == [0.2, 0.3]


def test_model_card_matches_the_code_settings():
    card = json.loads((ROOT / "services/ml/artifacts/model_card.json").read_text("utf-8"))
    assert card["model_version"] == iso.MODEL_VERSION
    assert card["risk_threshold"] == iso.RISK_THRESHOLD
    assert set(card["streams"]) == {"radar", "lidar", "telemetry"}


def test_model_card_meets_the_prototype_bar():
    """AUC >= 0.85 and FPR <= 5%, pooled and per stream (committed evaluation)."""
    card = json.loads((ROOT / "services/ml/artifacts/model_card.json").read_text("utf-8"))
    for name, m in list(card["streams"].items()) + [("pooled", card["pooled"])]:
        assert m["auc"] >= 0.85, name
        assert m["fpr"] <= 0.05, name
