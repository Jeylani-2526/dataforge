"""M7W28T3 — one-off batch scoring of fused rows with model v2.

    python services/ml/batch_score.py --since 2026-11-12T07:06:00Z --dry-run
    python services/ml/batch_score.py --since 2026-11-12T07:06:00Z

Writes anomaly_label, risk_score, confidence to fused_events, then refreshes summary_5min.
Rows with no staging row cannot be assembled and stay NULL. Live wiring moves to M8.
"""

import argparse
import os
import sys
from datetime import datetime, timezone

import numpy as np

import feature_assembly as fa
import model_v2 as v2

DSN = os.environ.get("TIMESCALE_DSN",
                     "postgresql://dataforge:dataforge_dev@localhost:5433/dataforge")

# Telemetry rules compare a record with the device's previous record, so they run over the
# full stream in staging, not over fused rows only (fusion keeps a subset -> false gaps).
# Ordered by time: producer restarts reset sequence_number, which then reads as no gap.
TELEMETRY_STREAM_SQL = """
SELECT event_id::text AS event_id, device_id, sequence_number, timestamp_ms
FROM raw_sensor_events_staging
WHERE sensor_type = 'TELEMETRY' AND timestamp_ms BETWEEN %(lo)s AND %(hi)s
ORDER BY timestamp_ms, sequence_number
"""
RULE_LOOKBACK_MS = 60_000   # so the first fused record in the window has its predecessor

UPDATE_SQL = """
UPDATE fused_events AS f
SET anomaly_label = v.label, risk_score = v.risk, confidence = v.conf
FROM (VALUES %s) AS v(fused_event_id, timestamp_ms, label, risk, conf)
WHERE f.fused_event_id = v.fused_event_id::uuid AND f.timestamp_ms = v.timestamp_ms
"""

CHECK_SQL = {
    "fused rows in window": "SELECT COUNT(*) FROM fused_events WHERE timestamp_ms >= %(s)s",
    "scored rows in window":
        "SELECT COUNT(*) FROM fused_events WHERE timestamp_ms >= %(s)s "
        "AND anomaly_label IS NOT NULL",
    "anomaly_label = 1": "SELECT COUNT(*) FROM fused_events WHERE timestamp_ms >= %(s)s "
                         "AND anomaly_label = 1",
}
SUMMARY_SQL = """
SELECT sensor_type, COUNT(*) AS buckets, ROUND(AVG(anomaly_rate)::numeric, 4) AS avg_rate,
       COUNT(anomaly_rate) AS buckets_with_rate
FROM summary_5min WHERE bucket >= %(s)s GROUP BY sensor_type ORDER BY 1
"""


def telemetry_rule_flags(stream_rows):
    """Staging telemetry rows in time order -> {event_id: rule name or ''}."""
    flags = fa.sequence_flags(stream_rows)
    return {r["event_id"]: (f or "") for r, f in zip(stream_rows, flags)}


def score_rows(rows, rule_by_event, value_stats, scorers):
    """Fused rows joined to staging -> (updates, summary). Unassembled rows are skipped."""
    groups, skipped = {}, {}
    for row in rows:
        stream, feats, why = fa.assemble_scoring_row(row, value_stats)
        if feats is None:
            skipped[why] = skipped.get(why, 0) + 1
            continue
        g = groups.setdefault(stream, {"X": [], "keys": [], "rule": []})
        g["X"].append(feats)
        g["keys"].append((str(row["fused_event_id"]), int(row["fused_timestamp_ms"])))
        g["rule"].append(rule_by_event.get(str(row["staging_event_id"]), ""))

    updates, summary = [], {"skipped": skipped, "streams": {}}
    for stream, g in sorted(groups.items()):
        rule = np.array(g["rule"]) if stream == "telemetry" else None
        out = scorers[stream].score(np.array(g["X"], dtype=float), rule)
        sources = {}
        for w in out["reason"]:
            for part in filter(None, w.split("+")):
                key = part.split(":")[0]
                sources[key] = sources.get(key, 0) + 1
        ts = [k[1] for k in g["keys"]]
        summary["streams"][stream] = {
            "scored": len(g["keys"]), "flagged": int(out["anomaly_label"].sum()),
            "sources": sources, "first_ms": min(ts), "last_ms": max(ts),
        }
        for (fid, t), lab, risk, conf in zip(g["keys"], out["anomaly_label"],
                                             out["risk_score"], out["confidence"]):
            updates.append((fid, t, int(lab), float(risk), float(conf)))
    return updates, summary


def fetch_rule_flags(conn, rows):
    from psycopg2.extras import RealDictCursor

    tel = [int(r["timestamp_ms"]) for r in rows
           if (r["sensor_type"] or "").upper() == "TELEMETRY" and r.get("timestamp_ms")]
    if not tel:
        return {}
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(TELEMETRY_STREAM_SQL, {"lo": min(tel) - RULE_LOOKBACK_MS, "hi": max(tel)})
        return telemetry_rule_flags(cur.fetchall())


def write_scores(conn, updates):
    from psycopg2.extras import execute_values

    with conn.cursor() as cur:
        execute_values(cur, UPDATE_SQL, updates, template="(%s, %s, %s, %s, %s)",
                       page_size=1000)
    conn.commit()


def refresh_and_check(dsn, since_ms):
    import psycopg2

    conn = psycopg2.connect(dsn)
    conn.autocommit = True   # CALL refresh_continuous_aggregate cannot run in a transaction
    try:
        with conn.cursor() as cur:
            cur.execute("CALL refresh_continuous_aggregate('summary_5min', NULL, NULL)")
            print("\nsummary_5min refreshed. Check:")
            for label, sql in CHECK_SQL.items():
                cur.execute(sql, {"s": since_ms})
                print(f"  {label:24s} {cur.fetchone()[0]:,}")
            cur.execute(SUMMARY_SQL, {"s": since_ms})
            print("  summary_5min  sensor_type  buckets  avg anomaly_rate  buckets with a rate")
            for st, n, rate, with_rate in cur.fetchall():
                print(f"                {st:11s}  {n:7d}  {rate}  {with_rate:7d}")
    finally:
        conn.close()


def report(summary, n_rows, dry_run):
    def utc(ms):
        return datetime.fromtimestamp(ms / 1000, timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    total = sum(s["scored"] for s in summary["streams"].values())
    print(f"{'DRY RUN — nothing written' if dry_run else 'WRITE'}  "
          f"model {v2.MODEL_VERSION}  alarm line {v2.ALARM_LINE}")
    print(f"fused rows in window {n_rows:,}   scored {total:,}   "
          f"skipped {sum(summary['skipped'].values()):,}")
    for why, n in summary["skipped"].items():
        print(f"  skipped: {why} ({n:,})")
    for stream, s in summary["streams"].items():
        print(f"  {stream:10s} scored {s['scored']:6,}  flagged {s['flagged']:5,} "
              f"({s['flagged'] / s['scored'] * 100:5.2f}%)  {utc(s['first_ms'])} -> "
              f"{utc(s['last_ms'])} UTC  sources {s['sources']}")


def parse_since(text):
    dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise SystemExit("--since needs a time zone, e.g. 2026-11-12T07:06:00Z")
    return int(dt.timestamp() * 1000)


def main():
    import psycopg2

    ap = argparse.ArgumentParser(description="M7W28T3 batch scoring with model v2")
    ap.add_argument("--since", required=True, help="score fused rows from this UTC time on")
    ap.add_argument("--dry-run", action="store_true", help="score and report, write nothing")
    args = ap.parse_args()
    since_ms = parse_since(args.since)

    stats = fa.load_value_stats()
    scorers = {s: v2.V2Scorer(s) for s in fa.STREAMS}
    with psycopg2.connect(DSN) as conn:
        rows = fa.fetch_scoring_rows(conn, since_ms)
        flags = fetch_rule_flags(conn, rows)
        updates, summary = score_rows(rows, flags, stats, scorers)
        report(summary, len(rows), args.dry_run)
        if args.dry_run or not updates:
            return 0
        write_scores(conn, updates)
    print(f"\nwrote {len(updates):,} rows")
    refresh_and_check(DSN, since_ms)
    return 0


if __name__ == "__main__":
    sys.exit(main())
