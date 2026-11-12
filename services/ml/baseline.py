"""M7W27T3 — statistical baseline, compared with the Isolation Forest.

    python services/ml/baseline.py compare

The baseline is a per-feature robust z-score: how many "normal spreads" a value
sits from the normal median, taking the worst feature. Same features, same
split, same 1% alarm budget and same risk-score definition as M7W27T2, so the
only thing that differs is the detector.
"""

import json
import sys
from pathlib import Path

import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.metrics import roc_auc_score

import feature_assembly as fa
import isolation_forest as iso

OUT = Path("services/ml/artifacts/baseline_comparison.json")


def fit_baseline(X_normal):
    """Median and MAD per feature, from normal training rows."""
    med = np.median(X_normal, axis=0)
    mad = np.median(np.abs(X_normal - med), axis=0)
    return med, np.where(mad > 0, mad, 1.0)


def baseline_scores(X, med, mad):
    """Largest robust z-score across features."""
    return np.max(np.abs(X - med) / mad, axis=1)


def _eval(y, risk, label, types):
    r = iso._rates(y, label)
    out = {"auc": float(roc_auc_score(y, risk)), "fpr": r["fpr"], "recall": r["recall"],
           "precision": r["precision"], "fp": r["fp"], "fn": r["fn"]}
    out["recall_by_type"] = {
        t: {"caught": int(label[types == t].sum()), "n": int((types == t).sum())}
        for t in sorted(set(types)) if t != "normal"
    }
    return out


def run_stream(stream):
    d = fa.load_corpus(stream)
    tr, te = ~d["is_test"], d["is_test"]
    normal_tr = tr & (d["y"] == 0)
    rule = (d["rule"] != "") if "rule" in d else np.zeros(len(d["y"]), bool)

    forest = IsolationForest(n_estimators=iso.N_ESTIMATORS, random_state=iso.SEED).fit(d["X"][tr])
    s_if = -forest.score_samples(d["X"])
    s_bl = baseline_scores(d["X"], *fit_baseline(d["X"][normal_tr]))

    risk_if = iso.risk_from_scores(s_if, np.sort(s_if[normal_tr]))
    risk_bl = iso.risk_from_scores(s_bl, np.sort(s_bl[normal_tr]))

    def detector(risk, use_rules):
        return iso.decide(risk, rule if use_rules else None)[:2]

    res = {}
    for split, sel in (("train", tr), ("test", te)):
        y, t = d["y"][sel], d["anomaly_type"][sel]
        block = {}
        for name, risk in (("isolation_forest", risk_if), ("baseline", risk_bl)):
            label, r = detector(risk, use_rules=True)
            block[name] = _eval(y, r[sel], label[sel], t)
            if stream == "telemetry":
                label, r = detector(risk, use_rules=False)
                block[name + "_no_rules"] = _eval(y, r[sel], label[sel], t)
        # Either detector raises the alarm; risk is the higher of the two.
        risk_or = np.maximum(risk_if, risk_bl)
        label, r = detector(risk_or, use_rules=True)
        block["either"] = _eval(y, r[sel], label[sel], t)
        # Same, but each detector gets half the budget, so the total stays near 1%.
        half = 1.0 - iso.FPR_BUDGET / 2
        label_h = ((risk_or >= half) | rule).astype(int)
        risk_h = np.where(rule, 1.0, risk_or)
        block["either_half_budget"] = _eval(y, risk_h[sel], label_h[sel], t)
        res[split] = block
    return res


def cmd_compare():
    out = {"alarm_line": iso.RISK_THRESHOLD, "streams": {}}
    for stream in fa.STREAMS:
        out["streams"][stream] = run_stream(stream)
    OUT.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8", newline="\n")

    for stream, res in out["streams"].items():
        print(f"\n[{stream.upper()}] test set")
        for name, m in res["test"].items():
            per = "  ".join(f"{t} {r['caught']}/{r['n']}" for t, r in m["recall_by_type"].items())
            print(f"  {name:26s} AUC {m['auc']:.4f}  FPR {m['fpr'] * 100:5.2f}%  "
                  f"recall {m['recall'] * 100:5.1f}%  precision {m['precision'] * 100:5.1f}%")
            print(f"  {'':26s} {per}")


def main():
    if sys.argv[1:] != ["compare"]:
        print("usage: python services/ml/baseline.py compare")
        return 2
    cmd_compare()
    return 0


if __name__ == "__main__":
    sys.exit(main())
