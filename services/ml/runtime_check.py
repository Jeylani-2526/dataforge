# M8W29T8: proves the fusion container can score and explain with model v2.
# Inside the container (WORKDIR /app):
#     docker compose run --rm --no-deps --entrypoint python \
#         fusion-engine services/ml/runtime_check.py
import sys

import joblib
import numpy as np
import shap
import sklearn

import model_v2 as m2


def check(stream):
    sc = m2.V2Scorer(stream)
    det = sc.det
    # A typical record (the normal median) and one 50 normal spreads out on every feature.
    X = np.vstack([det.med, det.med + 50 * det.mad])
    rule = np.array(["", ""]) if stream == "telemetry" else None
    r = sc.score(X, rule)
    ok = r["anomaly_label"][0] == 0 and r["anomaly_label"][1] == 1
    line = (f"{stream:<9} loaded  typical -> label {r['anomaly_label'][0]}"
            f"  extreme -> label {r['anomaly_label'][1]} ({r['reason'][1]})")
    if X.shape[1] > 1:
        sv = shap.TreeExplainer(det.forest).shap_values(X[1:])[0]
        push = -sv
        ok = ok and push.sum() > 0
        top = det.feature_names[int(np.argmax(push))]
        line += f"  SHAP push {push.sum():.4f}, top {top}"
    else:
        line += "  SHAP skipped (single feature, by design)"
    print(("OK    " if ok else "FAIL  ") + line)
    return ok


if __name__ == "__main__":
    print(f"python {sys.version.split()[0]}  numpy {np.__version__}  scikit-learn "
          f"{sklearn.__version__}  joblib {joblib.__version__}  shap {shap.__version__}")
    print(f"model_version expected {m2.MODEL_VERSION}")
    results = [check(s) for s in ("radar", "lidar", "telemetry")]
    sys.exit(0 if all(results) else 1)
