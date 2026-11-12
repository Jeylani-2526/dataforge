"""M7W27T2 — per-stream Isolation Forest, common risk score, evaluation.

    python services/ml/isolation_forest.py train

Trains one model per sensor stream on the natural ~3% training split, sets the
alarm line from NORMAL TRAINING rows only (1% false-alarm budget), evaluates
once on the fixed test split, and writes:
  services/ml/artifacts/{stream}_iforest.joblib   (not committed; rebuilt by this command)
  services/ml/artifacts/model_card.json           (committed: settings + metrics)
"""

import json
import sys
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.metrics import roc_auc_score

import feature_assembly as fa

ARTIFACTS = Path("services/ml/artifacts")
MODEL_VERSION = "iforest-m7w27t2-v1"
SEED = 42
N_ESTIMATORS = 200
FPR_BUDGET = 0.01                 # decision C, 12 November 2026
RISK_THRESHOLD = 1.0 - FPR_BUDGET  # alarm when risk_score >= 0.99
BOOTSTRAP_N = 1000


def risk_from_scores(scores, ref_sorted):
    """Risk = share of normal training scores at or below this score (0..1)."""
    return np.searchsorted(ref_sorted, scores, side="right") / len(ref_sorted)


def decide(risk, rule_hit=None):
    """risk -> (anomaly_label, risk_score, confidence). A rule hit is certain."""
    risk = np.asarray(risk, dtype=float).copy()
    if rule_hit is not None:
        risk[rule_hit] = 1.0
    label = (risk >= RISK_THRESHOLD).astype(int)
    # Confidence = distance from the alarm line, scaled to 0..1 on each side of it.
    confidence = np.where(
        label == 1,
        (risk - RISK_THRESHOLD) / (1.0 - RISK_THRESHOLD),
        (RISK_THRESHOLD - risk) / RISK_THRESHOLD,
    )
    return label, risk, np.clip(confidence, 0.0, 1.0)


class StreamScorer:
    """Loads one stream's trained model; used by the live scoring path (M7W28T3)."""

    def __init__(self, stream):
        bundle = joblib.load(ARTIFACTS / f"{stream}_iforest.joblib")
        self.stream = stream
        self.model = bundle["model"]
        self.ref_sorted = bundle["ref_sorted"]

    def score(self, X, rule_hit=None):
        raw = -self.model.score_samples(np.asarray(X, dtype=float))
        return decide(risk_from_scores(raw, self.ref_sorted), rule_hit)


def train_stream(stream):
    d = fa.load_corpus(stream)
    tr = ~d["is_test"]
    model = IsolationForest(n_estimators=N_ESTIMATORS, random_state=SEED).fit(d["X"][tr])
    raw = -model.score_samples(d["X"])
    ref_sorted = np.sort(raw[tr & (d["y"] == 0)])
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {"model": model, "ref_sorted": ref_sorted, "features": d["feature_names"],
         "model_version": MODEL_VERSION},
        ARTIFACTS / f"{stream}_iforest.joblib",
    )
    rule_hit = (d["rule"] != "") if "rule" in d else None
    label, risk, conf = decide(risk_from_scores(raw, ref_sorted), rule_hit)
    if_only_risk = risk_from_scores(raw, ref_sorted)
    return d, label, risk, conf, if_only_risk


def _rates(y, label):
    tp = int(((label == 1) & (y == 1)).sum())
    fp = int(((label == 1) & (y == 0)).sum())
    fn = int(((label == 0) & (y == 1)).sum())
    tn = int(((label == 0) & (y == 0)).sum())
    return {
        "fpr": fp / (fp + tn),
        "recall": tp / (tp + fn),
        "precision": tp / (tp + fp) if tp + fp else 0.0,
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
    }


def _ci(y, risk, label, rng):
    """95% bootstrap interval for AUC, FPR, recall and precision."""
    n = len(y)
    out = {"auc": [], "fpr": [], "recall": [], "precision": []}
    for _ in range(BOOTSTRAP_N):
        i = rng.integers(0, n, n)
        if y[i].min() == y[i].max():
            continue
        out["auc"].append(roc_auc_score(y[i], risk[i]))
        r = _rates(y[i], label[i])
        for k in ("fpr", "recall", "precision"):
            out[k].append(r[k])
    return {k: [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))]
            for k, v in out.items()}


def evaluate(y, risk, label, anomaly_type, rng):
    m = {"auc": float(roc_auc_score(y, risk)), **_rates(y, label)}
    m["ci95"] = _ci(y, risk, label, rng)
    m["recall_by_type"] = {
        t: {"caught": int(label[anomaly_type == t].sum()), "n": int((anomaly_type == t).sum())}
        for t in sorted(set(anomaly_type)) if t != "normal"
    }
    m["n_test"] = int(len(y))
    m["n_anomalies"] = int(y.sum())
    return m


def cmd_train():
    import sklearn

    rng = np.random.default_rng(SEED)
    card = {
        "model_version": MODEL_VERSION,
        "algorithm": "IsolationForest, one per sensor stream",
        "params": {"n_estimators": N_ESTIMATORS, "max_samples": "auto (256)",
                   "contamination": "not used — alarm line set from normal training scores",
                   "random_state": SEED},
        "training_data": "M3 corpus, natural ~3% anomaly rate, split data/splits (seed 42)",
        "fpr_budget_on_train_normals": FPR_BUDGET,
        "risk_threshold": RISK_THRESHOLD,
        "risk_score": "share of normal training scores <= this record's score",
        "telemetry_rules": "sequence_gap, timestamp_not_advancing -> risk 1.0",
        "sklearn_version": sklearn.__version__,
        "bootstrap_resamples": BOOTSTRAP_N,
        "streams": {},
    }
    pooled = {"y": [], "risk": [], "label": [], "type": []}
    for stream in fa.STREAMS:
        d, label, risk, _, if_only_risk = train_stream(stream)
        te = d["is_test"]
        y, t = d["y"][te], d["anomaly_type"][te]
        m = evaluate(y, risk[te], label[te], t, rng)
        m["features"] = d["feature_names"]
        m["auc_if_only"] = float(roc_auc_score(y, if_only_risk[te]))
        tr_norm = ~te & (d["y"] == 0)
        m["train_normal_fpr"] = float(label[tr_norm].mean())
        card["streams"][stream] = m
        for k, v in (("y", y), ("risk", risk[te]), ("label", label[te]), ("type", t)):
            pooled[k].append(v)
    p = {k: np.concatenate(v) for k, v in pooled.items()}
    card["pooled"] = evaluate(p["y"], p["risk"], p["label"], p["type"], rng)

    (ARTIFACTS / "model_card.json").write_text(json.dumps(card, indent=2) + "\n",
                                               encoding="utf-8")
    report(card)


def report(card):
    def line(name, m):
        c = m["ci95"]
        print(f"{name:10s} AUC {m['auc']:.4f} [{c['auc'][0]:.3f}-{c['auc'][1]:.3f}]  "
              f"FPR {m['fpr'] * 100:5.2f}% [{c['fpr'][0] * 100:.2f}-{c['fpr'][1] * 100:.2f}]  "
              f"recall {m['recall'] * 100:5.1f}%  precision {m['precision'] * 100:5.1f}%")

    print(f"{card['model_version']}  (alarm line: risk >= {card['risk_threshold']})\n")
    for stream, m in card["streams"].items():
        line(stream.upper(), m)
        for t, r in m["recall_by_type"].items():
            print(f"             {t:20s} {r['caught']:4d} / {r['n']:4d}  "
                  f"({r['caught'] / r['n'] * 100:.0f}%)")
    print()
    line("POOLED", card["pooled"])
    bar = card["pooled"]["auc"] >= 0.85 and card["pooled"]["fpr"] <= 0.05
    print(f"\nPrototype bar (AUC >= 0.85, FPR <= 5%): {'MET' if bar else 'NOT MET'}")


def main():
    if sys.argv[1:] != ["train"]:
        print("usage: python services/ml/isolation_forest.py train")
        return 2
    cmd_train()
    return 0


if __name__ == "__main__":
    sys.exit(main())
