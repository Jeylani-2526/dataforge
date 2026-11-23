"""
M6W26T3 — run-wide alignment distribution from alignment_samples.jsonl.

Host-side tool, no dependencies. Reads the file fused_writer.py appends to and
reports the figure M6W23T2 needs. Unlike the in-memory sample in the engine,
this spans restarts.
"""

import argparse
import json
import sys
from pathlib import Path

# The join predicate in fusion_engine.build_candidate_pairs admits only pairs
# within +/- this, so abs_dt_ms is bounded by it BY CONSTRUCTION. See the
# caveat printed at the end of the report.
JOIN_WINDOW_MS = 500

# data_flow_spec.md synchronization target.
SYNC_TARGET_MS = 1


def load(path: Path, from_batch=None, to_batch=None, since_ms=None, until_ms=None):
    values, batches, torn, filtered = [], set(), 0, 0

    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                # Expected once at most: a kill mid-write truncates the tail.
                torn += 1
                continue

            batch = rec.get("batch")
            written = rec.get("written_at_ms")
            dts = rec.get("abs_dt_ms") or []

            if from_batch is not None and (batch is None or batch < from_batch):
                filtered += 1
                continue
            if to_batch is not None and (batch is None or batch > to_batch):
                filtered += 1
                continue
            if since_ms is not None and (written is None or written < since_ms):
                filtered += 1
                continue
            if until_ms is not None and (written is None or written > until_ms):
                filtered += 1
                continue

            values.extend(int(d) for d in dts)
            if batch is not None:
                batches.add(batch)

    return values, batches, torn, filtered


def pct(sorted_values: list, p: float) -> int:
    n = len(sorted_values)
    return sorted_values[min(n - 1, int(round(p * (n - 1))))]


def summarize(values: list) -> dict:
    s = sorted(values)
    n = len(s)
    # The BETWEEN predicate is inclusive, so == window is legal. Only a value
    # strictly over it would mean the join emitted something it should not.
    over_window = sum(1 for v in s if v > JOIN_WINDOW_MS)
    at_window = sum(1 for v in s if v == JOIN_WINDOW_MS)
    within_target = sum(1 for v in s if v <= SYNC_TARGET_MS)

    return {
        "n": n,
        "min": s[0],
        "p50": pct(s, 0.50),
        "p90": pct(s, 0.90),
        "p95": pct(s, 0.95),
        "p99": pct(s, 0.99),
        "max": s[-1],
        "mean": round(sum(s) / n, 2),
        "over_window": over_window,
        "at_window": at_window,
        "within_sync_target": within_target,
        "within_sync_target_pct": round(within_target / n * 100, 2),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "path",
        nargs="?",
        default="data/alignment/alignment_samples.jsonl",
        help="alignment_samples.jsonl (default: %(default)s)",
    )
    ap.add_argument("--from-batch", type=int)
    ap.add_argument("--to-batch", type=int)
    ap.add_argument("--since-ms", type=int, help="epoch ms, written_at_ms lower bound")
    ap.add_argument("--until-ms", type=int, help="epoch ms, written_at_ms upper bound")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args()

    path = Path(args.path)
    if not path.exists():
        print(f"[ERROR] not found: {path}", file=sys.stderr)
        print(
            "        The fusion engine writes it only when fused rows carry "
            "abs_dt_ms.\n"
            "        Check the FUSION_ALIGNMENT_LOG_PATH mount in docker-compose.yml.",
            file=sys.stderr,
        )
        return 1

    values, batches, torn, filtered = load(
        path, args.from_batch, args.to_batch, args.since_ms, args.until_ms
    )

    if not values:
        print(f"[ERROR] no samples in {path} after filtering.", file=sys.stderr)
        return 1

    stats = summarize(values)
    stats["batches"] = len(batches)
    stats["torn_lines"] = torn
    stats["records_filtered_out"] = filtered
    stats["source"] = str(path)

    if args.json:
        print(json.dumps(stats, indent=2))
        return 0

    print(f"Alignment error (abs_dt_ms) — {path}")
    print(f"  batches          {stats['batches']}")
    print(f"  samples          {stats['n']}")
    if torn:
        print(f"  torn lines       {torn}  (truncated tail after a kill — expected)")
    if filtered:
        print(f"  filtered out     {filtered} record(s) by the range arguments")
    print()
    print(f"  min              {stats['min']} ms")
    print(f"  p50              {stats['p50']} ms")
    print(f"  p90              {stats['p90']} ms")
    print(f"  p95              {stats['p95']} ms")
    print(f"  p99              {stats['p99']} ms")
    print(f"  max              {stats['max']} ms")
    print(f"  mean             {stats['mean']} ms")
    print()
    print(
        f"  within +/-{SYNC_TARGET_MS} ms   {stats['within_sync_target']} "
        f"({stats['within_sync_target_pct']}%)"
    )
    print(f"  exactly {JOIN_WINDOW_MS} ms    {stats['at_window']} (legal, predicate is inclusive)")
    print(f"  over {JOIN_WINDOW_MS} ms       {stats['over_window']} (must be 0)")
    print()
    print("Method: nearest-rank percentiles, no interpolation. Values are the")
    print("difference between the two events' KAFKA MESSAGE timestamps, not")
    print("between the sensors' own recorded times. The +/-1 ms figure in")
    print("data_flow_spec.md describes the latter — the two are different")
    print("quantities and the report must say so.")
    print()
    print(f"Caveat: the join admits only pairs within +/-{JOIN_WINDOW_MS} ms, so")
    print("'over window' is 0 by construction and is NOT evidence against open")
    print("item 4. A record that drifts past the window and fuses with an older")
    print("ALICE event still produces a SMALL abs_dt_ms for that wrong pair.")
    print("Detecting it needs the sensor's payload timestamp, not this figure.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
