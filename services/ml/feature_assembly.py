"""M7W27T1 — feature assembly: one feature function, two inputs.

Training reads the M3 corpus (data/synthetic + data/splits); scoring reads fused
rows joined to raw_sensor_events_staging. Both go through featurize(), so the
two paths cannot drift apart. Decided in M6W26T5.

    python services/ml/feature_assembly.py corpus   # build matrices, write stats
    python services/ml/feature_assembly.py db       # scoring-path row counts
"""

import argparse
import json
import math
import os
import sys
from pathlib import Path

STREAMS = ["radar", "lidar", "telemetry"]
CORPUS_DIR = Path("data/synthetic")
SPLIT_DIR = Path("data/splits")
STATS_PATH = Path("services/ml/artifacts/telemetry_value_stats.json")

FEATURES = {
    "radar": ["range_m", "bearing_deg", "elevation_deg", "velocity_ms",
              "signal_strength_db"],
    "lidar": ["log_point_count", "centroid_x_m", "centroid_y_m", "centroid_z_m",
              "max_range_m", "avg_intensity", "min_intensity", "centroid_range_ratio"],
    "telemetry": ["value_z"],
}

# Raw columns each stream needs; a scoring row missing any of them is not assembled.
REQUIRED = {
    "radar": FEATURES["radar"],
    "lidar": ["point_count", "centroid_x_m", "centroid_y_m", "centroid_z_m",
              "max_range_m", "avg_intensity", "min_intensity"],
    "telemetry": ["parameter_name", "value"],
}


def featurize(stream, rec, value_stats=None):
    """One record -> feature vector. Used by both training and scoring."""
    if stream == "radar":
        return [float(rec[c]) for c in FEATURES["radar"]]

    if stream == "lidar":
        x, y, z = (float(rec[c]) for c in ("centroid_x_m", "centroid_y_m", "centroid_z_m"))
        max_range = float(rec["max_range_m"])
        # A centroid far beyond the sensor's own max range is geometrically impossible.
        ratio = math.sqrt(x * x + y * y + z * z) / max_range if max_range > 0 else 0.0
        return [
            math.log1p(float(rec["point_count"])),
            x, y, z, max_range,
            float(rec["avg_intensity"]),
            float(rec["min_intensity"]),
            ratio,
        ]

    if stream == "telemetry":
        # cpu_temp_c, voltage_v and battery_pct have different units, so each is
        # standardised against its own normal training distribution.
        stats = value_stats[rec["parameter_name"]]
        return [(float(rec["value"]) - stats["mean"]) / stats["std"]]

    raise ValueError(f"unknown stream: {stream}")


def sequence_flag(prev, rec):
    """Integrity rules for telemetry (M7W27 decision, option A).

    One-sided on purpose: the record after an anomaly is not flagged.
    Returns the rule that fired, or None.
    """
    if prev is None:
        return None
    if rec["sequence_number"] - prev["sequence_number"] > 1:
        return "sequence_gap"
    if rec["timestamp_ms"] - prev["timestamp_ms"] <= 0:
        return "timestamp_not_advancing"
    return None


def sequence_flags(records):
    """Apply sequence_flag over records in arrival order, per device."""
    last, out = {}, []
    for rec in records:
        out.append(sequence_flag(last.get(rec["device_id"]), rec))
        last[rec["device_id"]] = rec
    return out


def read_corpus(stream):
    with open(CORPUS_DIR / f"{stream}.jsonl", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def read_test_ids(stream):
    with open(SPLIT_DIR / f"{stream}_test_ids.txt", encoding="utf-8") as f:
        return {line.strip() for line in f if line.strip()}


def fit_value_stats(records, test_ids):
    """Mean/std of telemetry value per parameter, from NORMAL TRAINING rows only."""
    groups = {}
    for r in records:
        if r["event_id"] not in test_ids and r["label"] == 0:
            groups.setdefault(r["parameter_name"], []).append(float(r["value"]))
    stats = {}
    for name, vals in groups.items():
        mean = sum(vals) / len(vals)
        std = math.sqrt(sum((v - mean) ** 2 for v in vals) / len(vals))
        stats[name] = {"mean": mean, "std": std, "n": len(vals)}
    return stats


def load_value_stats():
    with open(STATS_PATH, encoding="utf-8") as f:
        return json.load(f)


def load_corpus(stream, value_stats=None):
    """Training/test matrices for one stream, in corpus (arrival) order."""
    import numpy as np

    records = read_corpus(stream)
    test_ids = read_test_ids(stream)
    if stream == "telemetry" and value_stats is None:
        value_stats = load_value_stats()

    data = {
        "X": np.array([featurize(stream, r, value_stats) for r in records]),
        "y": np.array([r["label"] for r in records]),
        "anomaly_type": np.array([r.get("anomaly_type") or "normal" for r in records]),
        "event_id": np.array([r["event_id"] for r in records]),
        "is_test": np.array([r["event_id"] in test_ids for r in records]),
        "feature_names": FEATURES[stream],
    }
    if stream == "telemetry":
        data["rule"] = np.array([f or "" for f in sequence_flags(records)])
    return data


# Scoring path: fused row -> its sensor event in staging (M6W26T5 Decision A1).
SCORING_SQL = """
SELECT f.fused_event_id, f.sensor_type, s.*
FROM fused_events f
LEFT JOIN raw_sensor_events_staging s ON s.event_id = f.sensor_event_id
{where}
"""


def fetch_scoring_rows(conn, limit=None):
    from psycopg2.extras import RealDictCursor

    sql = SCORING_SQL.format(where="") + (f" LIMIT {int(limit)}" if limit else "")
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql)
        return cur.fetchall()


def assemble_scoring_row(row, value_stats):
    """Return (stream, features) or (stream, None) with the reason it failed."""
    stream = (row["sensor_type"] or "").lower()
    if row.get("event_id") is None:
        return stream, None, "no staging row"
    missing = [c for c in REQUIRED[stream] if row.get(c) is None]
    if missing:
        return stream, None, "missing " + ",".join(missing)
    if stream == "telemetry" and row["parameter_name"] not in value_stats:
        return stream, None, f"unknown parameter {row['parameter_name']}"
    return stream, featurize(stream, row, value_stats), None


def cmd_corpus():
    tel = read_corpus("telemetry")
    stats = fit_value_stats(tel, read_test_ids("telemetry"))
    STATS_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATS_PATH.write_text(json.dumps(stats, indent=2) + "\n", encoding="utf-8")
    print(f"telemetry value stats -> {STATS_PATH}")
    for name, s in sorted(stats.items()):
        print(f"  {name:12s} mean {s['mean']:8.3f}  std {s['std']:7.3f}  (n={s['n']:,})")

    for stream in STREAMS:
        d = load_corpus(stream, stats)
        tr, te = ~d["is_test"], d["is_test"]
        print(f"\n[{stream.upper()}] X {d['X'].shape}  features: {', '.join(d['feature_names'])}")
        print(f"  train {tr.sum():,} ({d['y'][tr].sum():,} anomalies)   "
              f"test {te.sum():,} ({d['y'][te].sum():,} anomalies)")
        if stream == "telemetry":
            for t in sorted(set(d["anomaly_type"])):
                sel = d["anomaly_type"] == t
                print(f"  rules fire on {t:20s} {(d['rule'][sel] != '').sum():5,} / {sel.sum():6,}")


def cmd_db():
    import psycopg2

    dsn = os.environ.get("TIMESCALE_DSN",
                         "postgresql://dataforge:dataforge_dev@localhost:5433/dataforge")
    stats = load_value_stats()
    with psycopg2.connect(dsn) as conn:
        rows = fetch_scoring_rows(conn)
    total, ok, by, reasons = len(rows), 0, {}, {}
    for row in rows:
        stream, feats, why = assemble_scoring_row(row, stats)
        b = by.setdefault(stream, [0, 0])
        b[0] += 1
        if feats is not None:
            ok += 1
            b[1] += 1
        else:
            reasons[why] = reasons.get(why, 0) + 1
    print(f"fused rows {total:,}   assembled {ok:,}   "
          f"({(ok / total * 100) if total else 0:.2f}%)")
    for stream, (n, a) in sorted(by.items()):
        print(f"  {stream:10s} {a:,} / {n:,}")
    for why, n in sorted(reasons.items(), key=lambda kv: -kv[1]):
        print(f"  not assembled: {why} ({n:,})")


def main():
    ap = argparse.ArgumentParser(description="M7W27T1 feature assembly")
    ap.add_argument("mode", choices=["corpus", "db"])
    args = ap.parse_args()
    cmd_corpus() if args.mode == "corpus" else cmd_db()
    return 0


if __name__ == "__main__":
    sys.exit(main())
