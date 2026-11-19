"""M7W28T1 — model v2: Isolation Forest + per-feature robust z-score, either one alarms.

    python services/ml/model_v2.py train

Each detector gets half the 1% false-alarm budget (alarm at risk >= 0.995).
risk_score = the higher of the two; telemetry rule hits stay at 1.0.
Writes services/ml/artifacts/{stream}_v2.joblib (not committed) and model_card_v2.json.
"""

import json
import sys
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import IsolationForest

import baseline as bl
import feature_assembly as fa
import isolation_forest as iso

ARTIFACTS = Path("services/ml/artifacts")
CARD = ARTIFACTS / "model_card_v2.json"
MODEL_VERSION = "combined-m7w28t1-v2"
FPR_BUDGET = iso.FPR_BUDGET             # 1% in total, decision C (12 November)
ALARM_LINE = 1.0 - FPR_BUDGET / 2       # 0.995 per detector


def decide(risk_if, risk_z, rule_hit=None):
    """Two detector risks -> (anomaly_label, risk_score, confidence)."""
    risk = np.maximum(risk_if, risk_z)
    if rule_hit is not None:
        risk = np.where(rule_hit, 1.0, risk)
    label = (risk >= ALARM_LINE).astype(int)
    confidence = np.where(
        label == 1,
        (risk - ALARM_LINE) / (1.0 - ALARM_LINE),
        (ALARM_LINE - risk) / ALARM_LINE,
    )
    return label, risk, np.clip(confidence, 0.0, 1.0)


def reasons(risk_if, risk_z, worst_feature, feature_names, rule=None):
    """Why each alarm fired, e.g. 'zscore:velocity_ms' or 'rule:sequence_gap'. '' if no alarm."""
    out = []
    for i in range(len(risk_if)):
        r = []
        if rule is not None and rule[i]:
            r.append(f"rule:{rule[i]}")
        if risk_if[i] >= ALARM_LINE:
            r.append("isolation_forest")
        if risk_z[i] >= ALARM_LINE:
            r.append(f"zscore:{feature_names[worst_feature[i]]}")
        out.append("+".join(r))
    return out


class Detectors:
    """Both fitted detectors for one stream, plus their normal-training reference scores."""

    def __init__(self, forest, ref_if, med, mad, ref_z, feature_names):
        self.forest, self.ref_if = forest, ref_if
        self.med, self.mad, self.ref_z = med, mad, ref_z
        self.feature_names = feature_names

    @classmethod
    def fit(cls, X_train, X_normal_train, feature_names):
        forest = IsolationForest(n_estimators=iso.N_ESTIMATORS,
                                 random_state=iso.SEED).fit(X_train)
        med, mad = bl.fit_baseline(X_normal_train)
        ref_if = np.sort(-forest.score_samples(X_normal_train))
        ref_z = np.sort(bl.baseline_scores(X_normal_train, med, mad))
        return cls(forest, ref_if, med, mad, ref_z, feature_names)

    def risks(self, X):
        X = np.asarray(X, dtype=float)
        z = np.abs(X - self.med) / self.mad
        risk_if = iso.risk_from_scores(-self.forest.score_samples(X), self.ref_if)
        risk_z = iso.risk_from_scores(z.max(axis=1), self.ref_z)
        return risk_if, risk_z, z.argmax(axis=1)

    def bundle(self):
        return {"forest": self.forest, "ref_if": self.ref_if, "med": self.med,
                "mad": self.mad, "ref_z": self.ref_z, "features": self.feature_names,
                "model_version": MODEL_VERSION}


class V2Scorer:
    """Loads one stream's v2 model; used by the scoring path (M7W28T3)."""

    def __init__(self, stream):
        b = joblib.load(ARTIFACTS / f"{stream}_v2.joblib")
        if b["model_version"] != MODEL_VERSION:
            raise RuntimeError(f"{stream}: model file is {b['model_version']}, "
                               f"code expects {MODEL_VERSION} — rerun train")
        self.stream = stream
        self.det = Detectors(b["forest"], b["ref_if"], b["med"], b["mad"], b["ref_z"],
                             b["features"])

    def score(self, X, rule=None):
        """rule: array of rule names ('' = none) for telemetry, else None."""
        risk_if, risk_z, worst = self.det.risks(X)
        rule_hit = None if rule is None else (np.asarray(rule) != "")
        label, risk, conf = decide(risk_if, risk_z, rule_hit)
        why = reasons(risk_if, risk_z, worst, self.det.feature_names, rule)
        return {"anomaly_label": label, "risk_score": risk, "confidence": conf, "reason": why}


def train_stream(stream):
    d = fa.load_corpus(stream)
    tr = ~d["is_test"]
    det = Detectors.fit(d["X"][tr], d["X"][tr & (d["y"] == 0)], d["feature_names"])
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    joblib.dump(det.bundle(), ARTIFACTS / f"{stream}_v2.joblib")
    risk_if, risk_z, worst = det.risks(d["X"])
    rule = d.get("rule")
    label, risk, conf = decide(risk_if, risk_z, None if rule is None else rule != "")
    why = reasons(risk_if, risk_z, worst, d["feature_names"], rule)
    return d, label, risk, conf, np.array(why)


def alarm_sources(why, y):
    """How many alarms each detector raised, split by true anomaly / false alarm."""
    out = {}
    for w, truth in zip(why, y):
        if not w:
            continue
        for part in w.split("+"):
            key = part.split(":")[0]
            c = out.setdefault(key, {"true_alarms": 0, "false_alarms": 0})
            c["true_alarms" if truth else "false_alarms"] += 1
    return out


def cmd_train():
    import sklearn

    rng = np.random.default_rng(iso.SEED)
    card = {
        "model_version": MODEL_VERSION,
        "algorithm": "IsolationForest + per-feature robust z-score, one pair per stream; "
                     "alarm if either detector fires",
        "params": {"n_estimators": iso.N_ESTIMATORS, "max_samples": "auto (256)",
                   "random_state": iso.SEED,
                   "zscore": "|x - median| / MAD per feature, worst feature, "
                             "fitted on normal training rows"},
        "training_data": "M3 corpus, natural ~3% anomaly rate, split data/splits (seed 42)",
        "fpr_budget_on_train_normals": FPR_BUDGET,
        "alarm_line_per_detector": ALARM_LINE,
        "risk_score": "max of the two detectors' risks; each risk = share of normal "
                      "training scores <= this record's score",
        "telemetry_rules": "sequence_gap, timestamp_not_advancing -> risk 1.0",
        "sklearn_version": sklearn.__version__,
        "bootstrap_resamples": iso.BOOTSTRAP_N,
        "streams": {},
    }
    pooled = {"y": [], "risk": [], "label": [], "type": []}
    for stream in fa.STREAMS:
        d, label, risk, _, why = train_stream(stream)
        te, tr_norm = d["is_test"], ~d["is_test"] & (d["y"] == 0)
        y, t = d["y"][te], d["anomaly_type"][te]
        m = iso.evaluate(y, risk[te], label[te], t, rng)
        m["features"] = d["feature_names"]
        m["train_normal_fpr"] = float(label[tr_norm].mean())
        m["alarm_sources_test"] = alarm_sources(why[te], y)
        card["streams"][stream] = m
        for k, v in (("y", y), ("risk", risk[te]), ("label", label[te]), ("type", t)):
            pooled[k].append(v)
    p = {k: np.concatenate(v) for k, v in pooled.items()}
    card["pooled"] = iso.evaluate(p["y"], p["risk"], p["label"], p["type"], rng)

    CARD.write_text(json.dumps(card, indent=2) + "\n", encoding="utf-8", newline="\n")
    report(card)


def report(card):
    print(f"{card['model_version']}  (alarm line per detector: risk >= "
          f"{card['alarm_line_per_detector']})\n")
    for stream, m in list(card["streams"].items()) + [("pooled", card["pooled"])]:
        c = m["ci95"]
        print(f"{stream.upper():10s} AUC {m['auc']:.4f} [{c['auc'][0]:.3f}-{c['auc'][1]:.3f}]  "
              f"FPR {m['fpr'] * 100:5.2f}%  recall {m['recall'] * 100:5.1f}%  "
              f"precision {m['precision'] * 100:5.1f}%")
        for t, r in m["recall_by_type"].items():
            print(f"             {t:20s} {r['caught']:4d} / {r['n']:4d}")
        for src, n in m.get("alarm_sources_test", {}).items():
            print(f"             alarms from {src:17s} true {n['true_alarms']:4d}  "
                  f"false {n['false_alarms']:4d}")
    bar = card["pooled"]["auc"] >= 0.85 and card["pooled"]["fpr"] <= 0.05
    print(f"\nPrototype bar (AUC >= 0.85, FPR <= 5%): {'MET' if bar else 'NOT MET'}")


def main():
    if sys.argv[1:] != ["train"]:
        print("usage: python services/ml/model_v2.py train")
        return 2
    cmd_train()
    return 0


if __name__ == "__main__":
    sys.exit(main())
