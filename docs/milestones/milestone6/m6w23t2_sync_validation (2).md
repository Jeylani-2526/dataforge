# M6W23T2 / T4 — Synchronization Validation, Watermark Boundary & Restart Safety

**Week:** M6W23  **Owner:** Abdalla
**Branch:** develop @ `6a7c688` plus the M6W23T3 injection mode
**Executed:** 15 October 2026, 10:04 – 12:09 (+03:00)

This file carries two tasks, as the Week 23 plan specifies: T2's synchronization
measurements, and T4's boundary and restart results appended to them.

| Section | Task | Status |
|---|---|---|
| Timestamp-alignment error vs ±1 ms | T2 | Pending — Option A instrumentation agreed, not yet run |
| Match rate and unmatched count | T2 | Pending |
| Fused-count reconciliation | T2 | Pending |
| Fused-path p95 latency | T2 | Pending |
| Watermark boundary | T4 | **Complete** |
| Restart safety | T4 | **Complete** |

## T2 blocker and the agreed route

`select_nearest()` in `fusion_engine.py` computes `abs_dt_ms`, which is exactly
the alignment error T2 must report. `fused_writer.py` then discards it — the
docstring states it is "for logging only and is not a fused_events column", and
it is not in fact logged either. There is no path from the database to an
alignment distribution as the code stands.

Three options were weighed: log the distribution per batch, add a side table, or
add a column to `fused_events`. **Option A — log it — was chosen**, because
`fused_event_schema_v1` is locked and T2's deliverable is a measured figure with
its method, not permanent alignment monitoring. A side table is recorded as an
M6 open item for Week 24.

One qualification applies whichever route is taken, and it belongs in the Emrah
update: `abs_dt_ms` is the difference between the two events' **Kafka message
timestamps**, not between the sensors' own recorded times. The ±1 ms figure in
`data_flow_spec.md` is a software-timestamp synchronization target describing the
latter. The two describe different quantities.

---

# T4 — Watermark Boundary Test

## Method

Phases against a live stack using the M6W23T3 injection mode, row counts taken
with `docker exec` + psql, dropped rows read from the `DroppedRowListener`
repaired in M6W22T8. Injection applies to the sensor producers only; the ALICE
producer is unmodified.

## Headline finding — the operative watermark is not 5 seconds

`WATERMARK_DELAY_SECONDS` is 5. The watermark actually in force during injection
measured **12.4 – 13.5 seconds** behind the newest event time, consistently:

| Batch | Watermark | Max event time | Gap |
|---|---|---|---|
| 1 | 08:46:46.164Z | 08:46:59.639Z | 13.47 s |
| 2 | 08:46:52.216Z | 08:47:04.649Z | 12.43 s |
| 3 | 08:46:56.236Z | 08:47:09.640Z | 13.40 s |

Two contributors, both present and not fully separable from this sample:

1. `multipleWatermarkPolicy=min`, set deliberately in `fusion_engine.py` so that
   a lagging topic holds the global watermark back rather than having its records
   dropped — the M5 Item 8 caveat 2 fix. The surplus over the configured 5 s
   tracked the injected shift closely.
2. Batch processing lag. `commitTimeMs` measured 8033 ms and 9876 ms against a
   5000 ms trigger, so batches were taking roughly twice their interval. This
   also pushes the watermark further behind wall clock, and is the same effect
   behind the ~16 s fused-path latency recorded in M6W23T1.

**This is the most important result of the task.** Anyone reading
`WATERMARK_DELAY_SECONDS=5` would conclude that data more than 5 seconds late is
discarded. In practice the threshold is roughly two and a half times that, and it
moves with load and with the lateness already present in the stream. For a system
intended for defense and industrial sensors, "how late is too late" is a
specification-level question, and the answer is currently adaptive rather than
fixed.

## Results

| Phase | Configuration | Fused rows | Rate | Dropped |
|---|---|---|---|---|
| **A** baseline | injection off | 3977 → 4986 | 1.68 /s | **0** |
| **B** shift 1–3 s, fraction 1.0 | inside any watermark | 5384 → 6592 | 2.01 /s | **0** |
| **C** shift 7–9 s, fraction 1.0 | pre-kill | 6612 → 7333 | 1.90 /s | not read |
| **C** shift 7–9 s, fraction 1.0 | post-restart | 7333 → 7952 | 2.06 /s | **0** |
| **D** disorder 1.0, buffer 2 | no timestamp shift | 7998 → 9029 | 2.02 /s | **0** |
| **C′** shift 7–9 s, fraction 0.1 | 294 records flagged late | 11379 → 12919 | 2.00 /s | **0** |
| **E** shift 30 s, fraction 0.05 | ~165 records flagged late | — | — | **160** |

### Phases A, B, D — no drops, as predicted

Baseline establishes the reference rate. Phase B shifted every record 1–3 s and
dropped nothing. Phase D scrambled arrival order with a buffer of 2, holding
records roughly 400 ms so they stayed inside the ±500 ms fusion window, and
dropped nothing. Out-of-order arrival inside the window is absorbed cleanly.

Buffer size is load-bearing in Phase D: a buffer of 8 would have held records
roughly 1.6 s, pushing them outside the fusion window and quietly turning a
disorder test into a lateness test.

### Phase C — the first wrong turn: lateness is spread, not offset

Every record shifted 7–9 s back produced zero drops. A watermark tracks the
newest event time seen in its own stream, not wall clock. Shifting the entire
stream moved the watermark with it, and the 2 s spread between 7000 and 9000 ms
was never close to the limit. A uniformly delayed stream is not late; it is slow.

**Consequence for M6W23T3.** The injection mode's classification was wrong: it
labelled records beyond-watermark by shift magnitude alone, reporting 3,097 such
records while Spark correctly dropped none. Corrected under this task ID — the
injector now models the per-topic high-water mark, scores each record against it
at emission time, and warns at startup when a fraction of 1.0 with a narrow
spread would shift the whole stream. The corrected model reproduces zero expected
drops for Phases B, C and D, matching what was observed.

### Phase C′ — correct classification, still no drops

With fraction 0.1, 90 percent of records stayed on time and the injector
correctly flagged 294 of 3,047 as genuinely behind their topic's high-water mark.
Spark still dropped none. Two possibilities had to be separated: the shift was
not reaching Kafka, or the records were being excluded without being counted.

### Diagnostic 1 — the shift does reach Kafka

Raw message timestamps read from `sensor-radar` with `kafka-console-consumer`
under fraction 0.5 and a fixed 8000 ms shift. Exactly 10 of 20 messages carried
the shift, and adding 8000 ms back to that half reconstructed a monotonic
sequence averaging 581 ms between messages — matching the expected per-topic
cadence of a 200 ms publish interval split across three topics. The broker runs
the default `CreateTime` policy, so producer timestamps are preserved.

Producer-side explanation ruled out.

### Diagnostic 2 — nothing was late, so nothing was dropped

The progress payload showed `numRowsDroppedByWatermark: 0` on **both** state
operators, `symmetricHashJoin` and `stateStoreSave`. The counter was not blind —
there was genuinely nothing to drop, because the operative watermark was ~13 s
and the records were only 8 s late.

### Phase E — the boundary crossed

A 30 s shift at fraction 0.05, well beyond the measured ~13 s threshold:

```
fusion_join: 2 row(s) dropped by watermark this batch
```

**160 rows dropped.** The injector flagged 138 records beyond the watermark at a
snapshot taken 109 seconds before the run ended; projecting the remaining time at
the observed rate gives roughly 165. Injected and dropped counts agree.

This is the first run on this branch in which `numRowsDroppedByWatermark` has
produced a non-zero figure, confirming the M6W22T8 listener repair works against
a real stream.

## Boundary conclusion

Both sides of the line are now tested — but the line is not where the
configuration says it is:

| Shift | Result |
|---|---|
| 1–3 s | accepted |
| 7–9 s | accepted |
| 30 s | **dropped, 160 rows** |

The transition sits near the measured 12–13 s effective watermark, not at the
configured 5 s. Narrowing that interval was not attempted and is left as an M6
open item.

Also worth recording: a shift between 500 ms and the effective watermark survives
the watermark but falls outside the ±500 ms join window, so the record silently
matches an older ALICE event rather than its contemporaneous one. Fused counts
held near 2 rows/s in every phase, so dropped-row counts alone would never have
revealed this.

---

# T4 — Restart Safety

## Method

`docker kill` mid-stream during Phase C, so recovery was tested with injected
lateness present. SIGKILL rather than SIGTERM, to test the checkpoint itself
rather than the graceful shutdown path.

## Results: PASS

| Check | Result |
|---|---|
| Rows before kill | 7333 |
| Rows after restart | 7952 |
| Duplicate `(timestamp_ms, alice_event_id)` pairs | **0** |
| Rate before kill | 1.90 /s |
| Rate after restart | 2.06 /s |

`uq_fused_events_replay` absorbed replayed offsets under injection exactly as in
the M6W22T2 unit test and the clean restart in M6W23T1. Throughput resumed at the
pre-kill rate.

**Scope limit.** Zero duplicates is proven. "No fused row skipped" is not
provable from row counts alone — it needs reconciliation against published input
counts, which is T2's pending step. T4 establishes that the checkpoint resumed
and replay did not double-count, under lateness.

With M6W23T1's clean-stream restart, restart safety now holds both with and
without injected lateness.

## Instrumentation added

`fusion_engine.py` gains a `FUSION_PROGRESS_DEBUG` environment switch, **off by
default**, which dumps Spark's per-batch progress payload — event-time stats,
per-source input rows and the full state-operator JSON. It is what located the
13-second watermark, and it is left in place because the same question will
recur.

## Carried to Week 24

1. The effective watermark is 12–13 s, not the configured 5 s. Decide whether
   that is acceptable, and whether `multipleWatermarkPolicy` should stay at `min`.
2. Batch commit times of 8–10 s against a 5 s trigger.
3. The exact transition point between 9 s and 30 s was not narrowed.