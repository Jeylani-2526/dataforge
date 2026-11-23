"""M7W27T4 -- fixed 80/20 split, per stream, stratified by anomaly_type."""

import json
from collections import Counter
from pathlib import Path

from sklearn.model_selection import train_test_split

STREAMS = ["radar", "lidar", "telemetry"]
SRC = Path("data/synthetic")
OUT = Path("data/splits")
SEED = 42


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for stream in STREAMS:
        with open(SRC / f"{stream}.jsonl", encoding="utf-8") as f:
            recs = [json.loads(line) for line in f if line.strip()]

        ids = [r["event_id"] for r in recs]
        strata = [r.get("anomaly_type") or "normal" for r in recs]
        _, test_ids, _, test_strata = train_test_split(
            ids, strata, test_size=0.2, stratify=strata, random_state=SEED
        )

        (OUT / f"{stream}_test_ids.txt").write_text(
            "\n".join(sorted(test_ids)) + "\n", encoding="utf-8"
        )

        train_strata = Counter(strata) - Counter(test_strata)
        print(f"[{stream.upper()}] train {sum(train_strata.values()):,} / "
              f"test {len(test_ids):,}")
        for t in sorted(set(strata)):
            print(f"  {t:22s} train {train_strata[t]:6,}  test {Counter(test_strata)[t]:5,}")


if __name__ == "__main__":
    main()
