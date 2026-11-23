"""M7W27T3 — tests for the statistical baseline."""

import json
import sys
from pathlib import Path

import pytest

np = pytest.importorskip("numpy")
pytest.importorskip("sklearn")

sys.path.insert(0, str(Path(__file__).resolve().parent))

import baseline as bl  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]


def test_fit_uses_median_and_mad():
    X = np.array([[1.0, 10.0], [2.0, 10.0], [3.0, 10.0], [4.0, 10.0], [100.0, 10.0]])
    med, mad = bl.fit_baseline(X)
    assert med[0] == 3.0          # the outlier 100 does not move the median
    assert mad[0] == 1.0


def test_constant_feature_does_not_divide_by_zero():
    med, mad = bl.fit_baseline(np.array([[5.0], [5.0], [5.0]]))
    assert mad[0] == 1.0
    assert bl.baseline_scores(np.array([[5.0]]), med, mad)[0] == 0.0


def test_score_is_the_worst_feature():
    med, mad = np.array([0.0, 0.0]), np.array([1.0, 2.0])
    assert bl.baseline_scores(np.array([[3.0, 4.0]]), med, mad)[0] == 3.0
    assert bl.baseline_scores(np.array([[1.0, -10.0]]), med, mad)[0] == 5.0


def test_committed_comparison_covers_all_streams_and_detectors():
    data = json.loads((ROOT / bl.OUT).read_text("utf-8"))
    assert set(data["streams"]) == {"radar", "lidar", "telemetry"}
    for res in data["streams"].values():
        for split in ("train", "test"):
            assert {"isolation_forest", "baseline", "either_half_budget"} <= set(res[split])
