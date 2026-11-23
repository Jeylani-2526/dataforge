# M7W28T3 — Scoring Fused Rows with Model v2 (Batch)

**Owner:** Abdalla
**Milestone:** M7 · Week 28 · Task M7W28T3
**Date:** 19 November 2026
**Code:** `services/ml/batch_score.py`, `services/ml/test_batch_score.py`
**Model:** `combined-m7w28t1-v2` (M7W28T1)
**Result:** 12,123 fused rows scored and written — `anomaly_label`, `risk_score`, `confidence`
populated, `summary_5min.anomaly_rate` live. Flag rates 1.00–1.09% against a 1% budget. **Live
wiring into the fusion stream moves to M8.**

---

## 1. Decision — batch, not live

The plan's trigger for live inference was Wednesday 18 November. It was not met. Decided
19 November (Abdalla), option C of three:

| Option | Outcome |
|---|---|
| A — defer all of T3 to M8 | Scored columns stay NULL; M7W28T8 has nothing to verify |
| B — build live scoring Thursday–Saturday | Touches the fusion write path three days before close |
| **C — one-off batch scorer (chosen)** | Exercises the real write path, the CHECK constraints and `summary_5min` on real fused rows; live wiring moves to M8 with the SHAP work, which changes the same code |

---

## 2. What the scorer does

1. Reads fused rows from a start time on, joined to their sensor row in
   `raw_sensor_events_staging` — the M6W26T5 Decision A1 route and the same
   `fetch_scoring_rows()` M7W27T1 uses.
2. Builds features with `featurize()`, the function training used.
3. Scores with `V2Scorer` and writes the three columns by the table's key,
   `(fused_event_id, timestamp_ms)`, in one transaction.
4. Refreshes `summary_5min` by hand. Its policy only refreshes the last 15 minutes, so rows
   scored after the fact would otherwise never reach `anomaly_rate`.
5. Prints check counts from the database.

Rows with no staging row are **skipped and counted**, never guessed — they stay NULL.
`--dry-run` scores and reports without writing.

### 2.1 Telemetry rules run on the full stream

The rules compare a record with the same device's previous record. Fusion keeps roughly one
sensor event in three, so consecutive **fused** rows from one device skip sequence numbers by
design. Run on fused rows alone, `sequence_gap` would fire on almost every telemetry row
(`test_rules_on_full_stream_do_not_flag_the_fused_subset` shows it).

The scorer therefore runs the rules over the device's **full** stream in staging, with a 60 s
look-back so the first row in the window has its predecessor, and each fused row looks up its
result. The stream is ordered by `timestamp_ms`: the producer keeps sequence counters in memory,
so a restart sends them back to 1, which then reads as "no gap" rather than a false alarm.

---

## 3. What the database held (Abdalla's machine, 19 November)

| | Fused rows | With a staging row |
|---|---|---|
| 15 October | 25,419 | 0 |
| 5 November | 11,641 | 0 |
| 12 November, after the producer alignment | 12,123 | 12,123 |
| **Total** | **49,183** | **12,123 (24.65%)** |

Two findings, both recorded in `open_items_m7.md`:

1. **37,060 orphaned fused rows.** Every row before 12 November points to a staging row that
   does not exist. Fusion reads sensor events from Kafka directly; staging is written separately
   by `spark-processor`. The cause on this machine is not established from the data. M6W26T2's
   100% resolution was measured on Beyza's database, so the two results do not contradict each
   other — but `open_items_m6.md` Item 10's orphan risk is realised on at least one machine.
2. **The orphans also predate the producer alignment.** The live producer was aligned to the
   corpus ranges at `8af19aa` (12 November, 06:42 UTC) and its image rebuilt at 07:05 UTC.
   Before alignment, the corpus-trained model flagged 93.9% of LIDAR's normal live records
   (M7W27T1). Scored, these rows would have written ~94% anomaly rates into the database.

**Scoring window:** from 2026-11-12 07:06:00 UTC, after the rebuild. The rows before it stay
NULL — they can't be scored, and wouldn't be meaningful if they could.

---

## 4. Results

### 4.1 Dry run, then write — identical summaries

```
python services/ml/batch_score.py --since 2026-11-12T07:06:00Z --dry-run
python services/ml/batch_score.py --since 2026-11-12T07:06:00Z
```

| Stream | Scored | Flagged | Rate | Isolation Forest | z-score | Rules |
|---|---|---|---|---|---|---|
| LIDAR | 4,077 | 42 | 1.03% | 33 | 33 | — |
| RADAR | 4,053 | 44 | 1.09% | 22 | 28 | — |
| TELEMETRY | 3,993 | 40 | 1.00% | 32 | 28 | 0 |
| **Total** | **12,123** | **126** | **1.04%** | | | |

Window 07:08:04 → 08:49:23 UTC. 0 rows skipped. Detector counts exceed alarms where both fired.

**Reading it:** the live producer generates normal records only, so every flag is a false
alarm by construction. A rate at the 1% budget is the expected result, and it matches the
evaluation report's live preview (0.76–1.04%, M7W28T1 Section 8). Zero telemetry rule hits
confirms the full-stream ordering in Section 2.1.

### 4.2 Database checks after the write

| Check | Result |
|---|---|
| Fused rows in window | 12,123 |
| Scored rows in window | 12,123 |
| `anomaly_label = 1` | 126 |
| `summary_5min` buckets with an `anomaly_rate` | 20 / 20 per stream |
| `summary_5min` mean `anomaly_rate` | LIDAR 0.0103 · RADAR 0.0111 · TELEMETRY 0.0099 |

No CHECK constraint was violated — the write would have failed whole otherwise.
Independent verification by SQL through `docker exec` is M7W28T8 (Beyza).

---

## 5. Verified before it touched the real database

On a throwaway PostgreSQL 16 with the same `fused_events` and staging DDL as `init-db.sql`
(TimescaleDB functions stubbed), seeded with 9,000 aligned-producer records, a fused subset,
500 orphans, rows before the window and a producer restart mid-run:

- Dry run wrote nothing; the write scored all 3,162 linked rows, flag rates 0.86–1.16%
- 0 telemetry rule hits across the restart
- Orphans and rows before the window stayed NULL
- All values inside the CHECK ranges; `anomaly_label = 1` exactly where `risk_score ≥ 0.995`
- A second run left every value unchanged
- Deleting one staging record made the next fused row from that device score
  `rule:sequence_gap`, risk 1.0

`test_batch_score.py` — 6 tests, no database needed — covers the full-stream rule, the restart,
a real gap, `--since` parsing, skipped orphans, and plain-Python update values.

---

## 6. Undo

```bash
docker exec dataforge-timescaledb psql -U dataforge -d dataforge -c \
  "UPDATE fused_events SET anomaly_label = NULL, risk_score = NULL, confidence = NULL
   WHERE timestamp_ms >= 1794467160000;"
docker exec dataforge-timescaledb psql -U dataforge -d dataforge -c \
  "CALL refresh_continuous_aggregate('summary_5min', NULL, NULL);"
```

---

## 7. Carried forward

| Item | Owner | Target |
|---|---|---|
| Live scoring inside the fusion stream (this task's original scope) | Abdalla | M8 — with SHAP, same code path |
| 37,060 orphaned fused rows on Abdalla's machine; cause not established | Abdalla | M8 — check `spark-processor` uptime against fusion runs |
| Rows before the producer alignment stay unscored | Abdalla | Closed by design — recorded, not a defect |
