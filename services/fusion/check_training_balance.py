import json, numpy as np
from pathlib import Path
from collections import Counter
from imblearn.over_sampling import SMOTE

STREAMS = ["radar", "lidar", "telemetry"]
BASE_DIR = Path("data/synthetic")

FEATURE_COLS = [
    "range_m", "bearing_deg", "elevation_deg", "velocity_ms",
    "signal_strength_db", "scan_id", "point_count",
    "centroid_x_m", "centroid_y_m", "centroid_z_m",
    "max_range_m", "avg_intensity", "min_intensity", "value"
]

for stream in STREAMS:
    print(f"\n{'='*55}")
    print(f"[{stream.upper()}]")
    path = BASE_DIR / f"{stream}.jsonl"
    records = []
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))

    total = len(records)
    train_size = round(total * 0.8)

    # Stratified split
    anomaly_idx = [i for i, r in enumerate(records) if r.get("label") == 1]
    normal_idx  = [i for i, r in enumerate(records) if r.get("label") == 0]

    train_anom_n = round(len(anomaly_idx) * 0.8)
    train_norm_n = train_size - train_anom_n

    train_idx = anomaly_idx[:train_anom_n] + normal_idx[:train_norm_n]
    train_records = [records[i] for i in train_idx]

    print(f"  Train before SMOTE: {len(train_records):,} ({train_anom_n} anomaly / {train_norm_n} normal)")

    # Build feature matrix
    def safe_float(v):
        try: return float(v) if v is not None else 0.0
        except: return 0.0

    X = np.array([[safe_float(r.get(c)) for c in FEATURE_COLS] for r in train_records])
    y = np.array([r.get("label", 0) for r in train_records])

    print(f"  Class distribution before SMOTE: {Counter(y)}")

    # SMOTE — target 50/50
    smote = SMOTE(sampling_strategy=1.0, random_state=42)
    X_res, y_res = smote.fit_resample(X, y)

    after = Counter(y_res)
    print(f"  Class distribution after SMOTE:  {dict(after)}")
    print(f"  Total train after SMOTE: {len(y_res):,}")
    print(f"  Anomaly %: {after[1]/len(y_res)*100:.2f}%")

    test_records = [records[i] for i in anomaly_idx[train_anom_n:]] + \
                   [records[i] for i in normal_idx[train_norm_n:]]
    test_anom = sum(1 for r in test_records if r.get("label") == 1)
    test_norm = len(test_records) - test_anom
    print(f"  Test set (unchanged): {len(test_records):,} ({test_anom} anomaly / {test_norm} normal)")

print("\nDone.")
