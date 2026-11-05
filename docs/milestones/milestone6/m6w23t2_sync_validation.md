# M6W23T2 / T4 — Synchronization Validation, Watermark Boundary & Restart Safety

**Week:** M6W23  **Owner:** Abdalla
**Branch:** develop @ `6a7c688` plus the M6W23T3 injection mode
**Executed:** 15 October 2026, 10:04 – 12:09 (+03:00) — T4 sections
**Executed:** 5 November 2026, 15:54 – 16:12 (+03:00) — T2 measurements, under M6W26T4

This file carries two tasks, as the Week 23 plan specifies: T2's synchronization
measurements, and T4's boundary and restart results appended to them.

| Section | Task | Status |
|---|---|---|
| Timestamp-alignment error vs ±1 ms | T2 | **Measured** — target missed, cause stated |
| Match rate and unmatched count | T2 | **Measured** |
| Fused-count reconciliation | T2 | **Measured** |
| Fused-path p95 latency | T2 | **Measured** — not comparable to the ≤500 ms bar |
| Silent mis-pairing (open item 4) | T2 | **Not measured** — method cannot detect it |
| Watermark boundary | T4 | **Complete** |
| Restart safety | T4 | **Complete** |

> **Final.** The T2 figures were taken before the fused-record conformance gate
> (M6W26T1) had reported. It passed on 5 November (`766b6b7`), so the figures stand
> without a re-run.

## T2 blocker and the agreed route

`select_nearest()` in `fusion_engine.py` computes `abs_dt_ms`, which is exactly
the alignment error T2 must report. As originally written, `fused_writer.py`
discarded it.

Three options were weighed: log the distribution per batch, add a side table, or
add a column to `fused_events`. **Option A — log it — was chosen**, because
`fused_event_schema_v1` is locked and T2's deliverable is a measured figure with
its method, not permanent alignment monitoring. A side table is recorded as an
M6 open item for M9.

One qualification applies whichever route is taken, and it belongs in the Emrah
update: `abs_dt_ms` is the difference between the two events' **Kafka message
timestamps**, not between the sensors' own recorded times. The ±1 ms figure in
`data_flow_spec.md` is a software-timestamp synchronization target describing the
latter. The two describe different quantities.

## Status correction — written 5 November 2026 under M6W26T3

The paragraph above said the instrumentation was not built. **It was** — in
`34b0b7d`, the same commit that created this document, on 15 October. The
document went stale against its own commit, and the Week 26–28 catch-up plan
inherited the error from it. Recorded here rather than deleted, because this is
the third time on this project that a committed `.md` has contradicted the
branch, and the standing rule is to verify against committed files.

What was actually missing, and is now closed under M6W26T3:

1. **The sample did not survive a restart.** `_alignment_samples` was a module
   global. T4's restart-safety phase uses `docker kill`, so the cumulative
   distribution was lost exactly when the measurement run needed it most.
2. **Nothing was persisted.** The figures existed only in container stdout,
   which is not a measurement record.
3. **The 50,000 cap froze silently.** Past the cap the cumulative line kept
   printing a stale figure with no indication it had stopped collecting.

Delivered:

- `fused_writer.py` — `_persist_alignment()` appends one JSON line per batch,
  `fsync`'d, to `FUSION_ALIGNMENT_LOG_PATH`. Append-only, so it spans restarts.
  A failed write warns once and never fails the batch.
- `fused_writer.py` — `_accumulate_alignment()` warns once when the in-memory
  cap is reached and points at the report tool.
- `services/fusion/alignment_report.py` — run-wide distribution from the file.
  No dependencies, runs on the host. Filters by batch or wall-clock range, and
  tolerates a torn final line from a kill.
- `docker-compose.yml` — `./data/alignment` bind-mounted at `/app/alignment`.
  A bind mount rather than a named volume, so the host reads the file without
  `docker cp` and the M6W21T2 checkpoint reset cannot take the measurement
  with it.

Verified across a simulated two-process run with a truncated tail: 8 batches,
320 samples, torn line detected and skipped, percentiles unaffected.

### A correction to the planned detection method for open item 4

The catch-up plan states that comparing `abs_dt_ms` against the ±500 ms join
window is what detects open item 4's silent mis-pairing. **It cannot.**
`build_candidate_pairs()` admits only pairs already inside ±500 ms, so
`abs_dt_ms` is bounded by that window by construction. A record that drifts past
the window and fuses against an *older* ALICE event still produces a small
`abs_dt_ms` — for the wrong pair. The distribution will look clean either way.

Detecting it requires comparing the ALICE event time against the sensor's own
**payload** timestamp rather than its Kafka timestamp. `alignment_report.py`
prints this caveat with every run so the figure is not over-read. The reachable
payload timestamp depends on the M6W26T2 resolution rate, so the method is
scoped in T4 rather than assumed here.

---

# T2 — Synchronization Measurements (M6W26T4)

## Method

One live run, injection off, driven by `scripts/m6w26t4_sync_run.sh`:

| Phase | Duration | What happens |
|---|---|---|
| Warm-up | 120 s | Stack up with `--build`, so the M6W26T3 code is in the fusion image. Script stops if fusion is not running and writing |
| START | — | Wall-clock time and end offset of all four topics recorded |
| Window | 600 s | Producers and fusion run untouched |
| END | — | Same as START |
| Drain | 60 s | Producers keep running so the ~13 s effective watermark passes END and the window's last rows are emitted |

- **Published counts**: END offset minus START offset, per topic.
- **Fused counts**: `fused_events` rows with `timestamp_ms` inside START–END,
  by SQL through `docker exec` + psql. Not Adminer.
- **Latency**: `percentile_cont` over `latency_ms` on the same rows.
- **Alignment**: `alignment_report.py` over the M6W26T3 sample file.

Stack state: `develop` + M6W26T3 at `70a0100`. Window START `1793883404000`,
END `1793884033000` (epoch ms).

### A failed first run — recorded because it is a finding

The first attempt (15:27) wrote **zero fused rows**. Fusion had crashed two
minutes after start with `OffsetOutOfRangeException` on `sensor-lidar-0`:

```
Cannot fetch offset 4687364 ... Some data may have been lost because they are
not available in Kafka any more; either the data was aged out by Kafka ...
```

The fusion checkpoint still held 15 October offsets. Kafka's default retention
is 7 days and `docker-compose.yml` does not override it, so those segments had
been deleted during the 21-day pause. Spark refused to skip them, which is the
correct behaviour with `failOnDataLoss` at its default.

Resolved by the checkpoint reset procedure (remove `fusion-engine`, delete
`dataforgerepo_fusion-checkpoints`, restart). No database rows were touched.

Two consequences, both carried to `open_items_m6.md`:

1. **Any pause longer than 7 days breaks the fusion checkpoint.** Recovery
   needs a manual reset that silently abandons unread messages.
2. **The crash exited with code 0.** `run()` catches the query exception and
   exits normally, so `docker ps` reports `Exited (0)` — indistinguishable from
   a clean stop. Nothing in the stack would raise an alert.

`failOnDataLoss=false` was deliberately **not** used as a workaround. It would
convert a visible failure into silent loss on a project that measures data loss.

The run script now aborts after warm-up if fusion is not running or has written
no alignment samples, so a dead engine cannot produce an empty measurement again.

## Results

### Published and fused inside the window

| Topic | Published |
|---|---|
| `alice-events` | 1,250 |
| `sensor-radar` | 1,027 |
| `sensor-lidar` | 1,039 |
| `sensor-telemetry` | 1,020 |
| **Sensors total** | **3,086** |

| Fused rows by `sensor_type` | Rows |
|---|---|
| LIDAR | 426 |
| RADAR | 417 |
| TELEMETRY | 413 |
| **Total** | **1,256** |

### 1. Match rate and unmatched count

| Figure | Value |
|---|---|
| Fused rows / ALICE published | 1,256 / 1,250 = 100.48 % |
| **Reported match rate** | **≈ 100 %, ±6 events boundary error** |
| Unmatched ALICE events | **0 detectable** |

A rate above 100 % is not real output. The window is bounded two different
ways: published counts by Kafka offset, fused counts by `timestamp_ms`. The
offsets are read a few seconds after the timestamp is taken, and the timestamp
has one-second resolution, so the two edges do not coincide. Six rows is about
three seconds of ALICE traffic at ~2 events/s, which fits.

With injection off, every ALICE event found a sensor event within ±500 ms.
That is expected: sensor traffic across the three topics arrives roughly every
200 ms, well inside the window.

**Script limitation, recorded for re-runs:** reading offsets before taking the
timestamp and using millisecond resolution would narrow the boundary error. It
cannot remove it, because offsets and timestamps are different clocks.

### 2. Fused-count reconciliation

| Check | Result |
|---|---|
| Fused rows ≤ ALICE published (within boundary error) | **Pass** |
| Duplicate `(timestamp_ms, alice_event_id)` pairs | **0** |
| Distinct `sensor_event_id` / fused rows | 1,256 / 1,256 — **no sensor event used twice** |
| Rows dropped by watermark (`DroppedRowListener`) | **0** |
| Split across sensor types | 33.9 / 33.2 / 32.9 % — even |

Sensor events not used in a fused row: 3,086 − 1,256 = 1,830. **This is not
loss.** The join keeps one sensor event per ALICE event, the nearest, so with
sensors arriving ~2.5 times as often as ALICE, most sensor events are correctly
left unpaired.

This closes the scope limit stated under T4 restart safety: zero duplicates was
already proven, and every published ALICE event in the window is now accounted
for in fused output.

### 3. Timestamp-alignment error against ±1 ms

| Statistic | `abs_dt_ms` |
|---|---|
| Batches | 153 |
| Samples | 1,559 |
| min | 0 ms |
| p50 | 50 ms |
| p90 | 90 ms |
| **p95** | **96 ms** |
| p99 | 100 ms |
| max | 105 ms |
| mean | 50.33 ms |
| Within ±1 ms | 21 (1.35 %) |
| Over 500 ms | 0 |

**Against the ±1 ms target: missed, as measured.**

**Cause.** The distribution is almost exactly uniform on 0–100 ms: mean 50,
p90 90, p95 96. That is the signature of nearest-neighbour sampling, not of
clock error. Combined sensor traffic arrives about every 200 ms, so the nearest
sensor event to any ALICE event is at most ~100 ms away and 50 ms on average.
The 105 ms maximum is publish jitter at the edge of that interval.

So `abs_dt_ms` measures **how far apart two independent streams' events are**,
not how well their clocks agree. The ±1 ms figure in `data_flow_spec.md` is a
clock-synchronization target. These are different quantities. To bring
`abs_dt_ms` near 1 ms, sensor events would have to be published at ~1 ms
spacing; no clock improvement changes it.

**Kafka-timestamp qualification.** Values are differences between Kafka
message timestamps (producer `CreateTime`), not the sensors' own recorded times.

**Scope.** The alignment sample covers the whole run, warm-up and drain
included, not only the 600 s window: 1,559 samples against 1,256 windowed rows.
With injection off and a steady producer rate, the distribution does not depend
on the window.

### 4. Fused-path p95 latency

| Statistic | `latency_ms` |
|---|---|
| p50 | 16,640 ms |
| **p95** | **19,255 ms** |
| p99 | 20,392 ms |
| max | 21,755 ms |
| Rows | 1,256 |

**Definition.** `latency_ms` is fused-row write time minus the ALICE event's
Kafka timestamp. Both are taken from the same Docker host clock.

**This is not the ≤500 ms bar's quantity.** The bar describes processing
latency. Fused-path latency includes, by design:

1. **The watermark wait.** In append mode a fused row is emitted only once the
   watermark passes its window, and the effective watermark is ~13 s (T4
   headline finding below), not the configured 5 s.
2. **The trigger interval.** Up to 5 s waiting for the next micro-batch.
3. **Batch lag.** Commits measured 8–10 s against a 5 s trigger in Week 23.

The ~13 s watermark plus up to ~5 s of trigger and batch delay gives the
observed 16–20 s. The figure moves with the effective-watermark decision
(open item 1), not with processing speed. For comparison, M5's staging-path
p95 was 5.7 s.

## Not measured: silent mis-pairing (open item 4)

The Week 26–28 plan assigned this to the `abs_dt_ms` reconciliation. As set out
under M6W26T3 above, `abs_dt_ms` cannot detect it: a mis-paired row is still
within ±500 ms of the wrong ALICE event, so it looks clean.

With injection off, no drift was introduced, so the run does not suggest any
mis-pairing occurred. That is not the same as having measured it. Detecting it
needs the sensor's payload timestamp, whose availability depends on M6W26T2.
Carried to `open_items_m6.md` as unquantified.

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