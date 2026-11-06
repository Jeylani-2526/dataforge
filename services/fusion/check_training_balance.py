import json, sys
from pathlib import Path

STREAMS = ["radar", "lidar", "telemetry"]
BASE_DIR = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/synthetic")
results = {}

for stream in STREAMS:
    path = BASE_DIR / f"{stream}.jsonl"
    records = []
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    total = len(records)
    anomalies = sum(1 for r in records if r.get("label") == 1)
    normal = total - anomalies
    anomaly_pct = anomalies / total * 100
    train_size = round(total * 0.8)
    test_size = total - train_size
    train_anom = round(anomalies * 0.8)
    test_anom = anomalies - train_anom
    results[stream] = dict(total=total,normal=normal,anomalies=anomalies,anomaly_pct=anomaly_pct,train_size=train_size,test_size=test_size,train_anom=train_anom,test_anom=test_anom)
    print(f"\n[{stream.upper()}]")
    print(f"  Total       : {total:,}")
    print(f"  Normal      : {normal:,}")
    print(f"  Anomaly     : {anomalies:,} ({anomaly_pct:.2f}%)")
    print(f"  Train (80%) : {train_size:,} -- {train_anom} anomaly")
    print(f"  Test  (20%) : {test_size:,} -- {test_anom} anomaly")

print("\n" + "="*50)
total_all = sum(r["total"] for r in results.values())
total_anom = sum(r["anomalies"] for r in results.values())
print(f"Total all streams : {total_all:,}")
print(f"Total anomalies   : {total_anom:,} ({total_anom/total_all*100:.2f}%)")
print("\nFEATURE COLUMNS:")
for stream in STREAMS:
    path = BASE_DIR / f"{stream}.jsonl"
    with open(path, "r") as f:
        first = json.loads(f.readline())
    print(f"  {stream}: {list(first.keys())}")
