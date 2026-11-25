# M8W29T1: reproduces the SHAP figures in m8w29t1_xai_design.md (test-set alarms, model v2).
# Run from the repo root after `python services/ml/model_v2.py train`:
#     python services/ml/xai_probe.py
import json
import time

import numpy as np
import shap

import feature_assembly as fa
import model_v2 as m2

# Features each anomaly type changes (scripts/generators/anomaly_injection.py),
# mapped onto model features: point_count -> log_point_count; centroid or max range -> ratio.
INJECTED = {
    "velocity_spike": {"velocity_ms"},
    "sensor_dropout": {"signal_strength_db"},
    "ghost_target": {"range_m", "bearing_deg", "elevation_deg", "signal_strength_db"},
    "point_cloud_dropout": {"log_point_count", "min_intensity", "centroid_range_ratio"},
    "ghost_point": {"log_point_count", "centroid_x_m", "centroid_y_m", "centroid_z_m",
                    "max_range_m", "centroid_range_ratio"},
    "noise_burst": {"avg_intensity", "min_intensity", "centroid_x_m", "centroid_y_m",
                    "centroid_z_m", "centroid_range_ratio"},
}


def expected_path_length(forest, X):
    # score_samples = -2^(-E[h] / c(n))  ->  E[h] = -log2(-score) * c(n)
    n = forest._max_samples
    c = 2.0 * (np.log(n - 1) + np.euler_gamma) - 2.0 * (n - 1) / n
    return -np.log2(-forest.score_samples(X)) * c


def probe(stream):
    d = fa.load_corpus(stream)
    sc = m2.V2Scorer(stream)
    te = d["is_test"]
    X, t = d["X"][te], d["anomaly_type"][te]
    r = sc.score(X, d["rule"][te] if "rule" in d else None)
    a = r["anomaly_label"] == 1
    risk_if, risk_z, worst = sc.det.risks(X)
    fired_if, fired_z = (risk_if >= m2.ALARM_LINE)[a], (risk_z >= m2.ALARM_LINE)[a]
    out = {"alarms": int(a.sum()),
           "both_detectors": int((fired_if & fired_z).sum()),
           "forest_only": int((fired_if & ~fired_z).sum()),
           "zscore_only": int((~fired_if & fired_z).sum()),
           "saturated_risk_1": int((r["risk_score"][a] >= 1.0).sum())}
    if X.shape[1] == 1:
        out["shap"] = "not run: single-feature forest (TreeExplainer IndexError in shap 0.54.1)"
        return out

    names = np.array(d["feature_names"])
    Xa = X[a]
    ex = shap.TreeExplainer(sc.det.forest)
    t0 = time.perf_counter()
    sv = ex.shap_values(Xa)
    ms = (time.perf_counter() - t0) * 1000 / len(Xa)
    base = float(np.ravel(ex.expected_value)[0])
    push = -sv                                   # positive = pushes toward alarm
    top = names[np.argmax(push, axis=1)]
    ztop = names[worst[a]]
    z_only = ~fired_if & fired_z
    sat = r["risk_score"][a] >= 1.0

    out.update({
        "ms_per_alarm": round(ms, 2),
        "base_expected_path_length": round(base, 3),
        "max_additivity_error": float(np.abs(base + sv.sum(1)
                                             - expected_path_length(sc.det.forest, Xa)).max()),
        "share_pushing_toward_alarm": float((push.sum(1) > 0).mean()),
        "zscore_only_shap_top_equals_z": int((top[z_only] == ztop[z_only]).sum()),
        "saturated_distinct_push_totals": int(len(np.unique(np.round(push.sum(1)[sat], 6)))),
        "fewer_than_3_positive_features": int(((push > 0).sum(1) < 3).sum()),
        "top1_is_a_changed_feature": {},
    })
    for typ, changed in INJECTED.items():
        m = t[a] == typ
        if m.any():
            out["top1_is_a_changed_feature"][typ] = {
                "alarms": int(m.sum()),
                "shap": int(sum(f in changed for f in top[m])),
                "zscore": int(sum(f in changed for f in ztop[m])),
                "shap_and_z_name_same_feature": int((top[m] == ztop[m]).sum())}
    return out


if __name__ == "__main__":
    print(json.dumps({s: probe(s) for s in fa.STREAMS}, indent=1))
