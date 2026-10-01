# Module 6 Fusion Join Design Note

**Task ID:** M6W21T1
**Owner:** Abdullah
**Milestone:** M6 · Week 21
**Status:** Signed off by Abdullah (1 October 2026), except Section 10 (FK target), which is pending M6W21T7 (Beyza).
**GitHub Path:** `/docs/milestones/milestone6/fusion_join_design_note.md`
**Builds against:** `schemas/fused_event_schema_v1.avsc` (locked 25 June 2026). No schema bump.
**Verified against:** `develop` HEAD `bb7ec81` (1 October 2026).

---

## 1. Purpose

This note defines the Module 6 stream-stream join before any join code is written. Week 22
implements it in `services/fusion/`. Four findings from checking the repo shaped the design:

1. **The two streams are on different clocks.** ALICE `timestamp_ms` is 2010 detector time plus a
   per-loop offset (`alice_producer.py`, M5W17T2). Sensor `timestamp_ms` is wall-clock time
   (`sensor_producer.py`). A ±500 ms join on `timestamp_ms` would never match. The ALICE timeline
   also drifts further behind each loop (20 s of event time per 34 s of wall time).
2. **Spark rejects a time-range-only stream-stream join.** It fails with *"Stream-stream join
   without equality predicate is not supported"*. This was confirmed in a local Spark 3.5 spike
   (Section 12).
3. **A plain Spark join emits every pair in the window.** It has no built-in "pick one" step.
4. **`data_flow_spec.md` Module 6 describes a different design** (1 : many, `clean_events`, 2 s
   window). M6W21T3 corrects it to match this note.

## 2. Decisions locked (Abdullah, 1 October 2026)

| # | Decision | Choice |
|---|---|---|
| D1 | Rows per ALICE event | **One fused row**: the single nearest sensor event across RADAR, LIDAR and TELEMETRY |
| D2 | Sensor-event reuse | **Allowed.** Each ALICE event selects independently, so one sensor event can appear in more than one fused row |
| D3 | Join clock | **Kafka message timestamp** (producer CreateTime, wall clock) on both sides |
| D4 | Selection rule | Smallest `\|Δt\|`, then earlier sensor timestamp, then smallest `sensor_event_id` |

D1 matches the locked "1 ALICE event : 1 sensor event" decision. D2 and D4 make the result
**deterministic**, so a replay from a checkpoint produces the same pairs. A strict one-to-one rule
(no reuse) would depend on arrival order and micro-batch boundaries.

D3 needs no producer or schema change. Neither producer sets an explicit Kafka timestamp, so both
topics carry the wall-clock time of the `produce()` call. Kafka stores that timestamp with the
message, so replays see the same value. It also matches the fused schema's own wording: records
are merged "on a shared software timestamp". ALICE's 2010 `timestamp_ms` stays untouched in the
ALICE record.

## 3. (a) Inputs

The join reads the **four live topics directly**. `clean_events` does not exist.

| Topic | Partitions | Fields the join needs | Source of each field |
|---|---|---|---|
| `alice-events` | 1 | `alice_event_id`, join time | Kafka key, Kafka `timestamp` |
| `sensor-radar` / `sensor-lidar` / `sensor-telemetry` | as created | `sensor_event_id`, `sensor_type`, join time | Kafka key, topic name, Kafka `timestamp` |

**Approved (1 October 2026): no Avro decoding in the fusion engine.** Both producers already set the
Kafka key to `event_id` (`alice_producer.py` L223–225, `sensor_producer.py` L218–220), and the topic
name gives `sensor_type`. Skipping `from_avro()` saves CPU on a host where every service shares 8
cores (M5 Item 7). This makes **key = `event_id`** a producer contract, which this note records. The
fusion engine validates that each key is a UUID and counts any that are not as rejected (Section 7).

## 4. (b) Join and 1 : 1 selection

The join has two stages, both stateful, chained in one query. Spark 3.4+ supports this in append
mode, and the project runs `pyspark==3.5.9`.

**Stage 1: interval join with a time-bucket key.** The bucket key gives Spark the equality
predicate it requires. Each sensor event goes into its 1-second bucket. Each ALICE event is copied
into every bucket its ±500 ms window touches (one or two buckets). A pair is therefore produced
exactly once.

```python
W = FUSION_WINDOW_MS            # 500
B = 2 * W                       # bucket width 1000 ms, so a window spans at most 2 buckets

alice = (alice_raw
    .withColumn("a_time", col("timestamp"))                  # Kafka timestamp
    .withColumn("a_ms", expr("unix_millis(timestamp)"))
    .withWatermark("a_time", f"{WATERMARK_DELAY_SECONDS} seconds")
    .withColumn("bucket", expr(f"explode(sequence(floor((a_ms - {W}) / {B}), floor((a_ms + {W}) / {B})))")))

sensor = union_of_three_topics   # each topic read and watermarked separately, see Section 5
    .withColumn("s_bucket", expr(f"floor(s_ms / {B})"))

pairs = alice.join(sensor, expr(f"""
    bucket = s_bucket AND
    s_time BETWEEN a_time - INTERVAL {W} MILLISECONDS AND a_time + INTERVAL {W} MILLISECONDS"""))
```

**Stage 2: pick the nearest match per ALICE event.** This is a stateful aggregation, not a step
inside `foreachBatch`. Candidates for one ALICE event can arrive across several micro-batches, so a
per-batch choice could lock in a worse match before a closer one arrives. The aggregation emits
**once**, after the watermark passes the ALICE event's window. By then no on-time candidate can
still arrive.

```python
best = (pairs
    .withColumn("abs_dt", abs(col("s_ms") - col("a_ms")))
    .groupBy("alice_event_id", "a_time")
    .agg(min(struct("abs_dt", "s_ms", "sensor_event_id", "sensor_type")).alias("m")))  # D4 via struct order
```

`min(struct(...))` compares the fields in order, which implements the D4 tie-break in one step.
`foreachBatch` then only builds the fused rows, enforces the fused schema and inserts them.

**Unmatched ALICE events** (no sensor event within ±500 ms) produce no row, because the join is an
inner join and `sensor_event_id` is non-nullable in v1. They are **not data loss**. They are
counted separately as published ALICE events minus fused rows (Section 7). At the default rates
(~4.9 sensor events/sec), the expected share is under 1%.

**Known M7 consequence of D2:** a sensor event can back two fused rows when two ALICE events fall
within 1 s of each other (ALICE publishes every 500 ms). Module 7 should treat those rows as
correlated. This is logged here and not hidden.

## 5. (c) Watermarks and state bounds

- **Watermark on both sides,** using the existing `WATERMARK_DELAY_SECONDS` (5 s). The column is
  the Kafka timestamp, not `timestamp_ms`.
- **Sensor topics are read as three separate streams,** each with its own watermark, and then
  unioned. Spark's default multiple-watermark policy (`min`) then keeps the global watermark at the
  slowest input. A lagging topic **holds the watermark back** instead of having its records dropped
  as late. This is the fix for M5 Item 8 caveat 2.
- **The time-range condition bounds join state.** An ALICE row can be dropped once the watermark
  passes `a_time + 500 ms`. A sensor row can be dropped once it passes `s_time + 500 ms`.
  Approximate state at the bar rate: (5 s delay + 0.5 s window) × 10,000/s ≈ 55,000 sensor rows.
  That is small.
- **Keep the `min` policy.** The `max` policy would let the fastest stream drive the watermark and
  drop the slower stream's records. That would silently break the 1 : 1 output.

**Accepted trade-off:** under `min`, if one producer stops entirely, the watermark freezes. Fused
output then pauses and join state grows until that producer resumes. This is the correct
behaviour, because the engine cannot know a closer match will never come. It needs to be visible
operationally: the Week 22 `fusion_status` heartbeat (Beyza) should mark that source `offline`.

## 6. (d) M5 Item 8 caveats as correctness requirements

In M5 these caveats only affected monitoring counts. In M6, a record dropped as late means a
missing fused event.

| Caveat | Effect on the join if unhandled | Requirement and how this design meets it |
|---|---|---|
| 1. Restarting `alice-ingestion` resets the rebasing offset, so `timestamp_ms` jumps back | ALICE rows dropped as late, so fused rows go missing | **R1: the join clock must never go backwards on a producer restart.** Met by D3. Kafka timestamps are wall-clock at publish, so a restart continues forward. The README restart rule (M6W21T3) is still needed for spark-processor's windowed counts, which use `timestamp_ms`. After M6W21T2 that rule includes deleting the `alice_throughput` checkpoint, because a restart restores the saved watermark |
| 2. One shared watermark across the three sensor topics | A lagging topic's events dropped, so wrong or missing matches | **R2: each sensor topic needs its own watermark.** Met by Section 5 (three streams, `min` policy) |
| (new) Cross-batch candidates | A closer match arriving in a later batch is ignored | **R3: selection must be final only after the window closes.** Met by Section 4 Stage 2 (append-mode aggregation). Confirmed in the spike (Section 12) |

## 7. (e) How the fused fields are populated

| v1 field | Value | Notes |
|---|---|---|
| `fused_event_id` | UUID v4, generated at write | Replay de-duplication uses the key below, not this ID |
| `alice_event_id` | Kafka key of the ALICE message | |
| `sensor_event_id` | Kafka key of the selected sensor message | |
| `timestamp_ms` | **ALICE Kafka timestamp** (ms) | The shared timeline anchor for the pair. Deterministic on replay. ERD `time` = `to_timestamp(timestamp_ms)` |
| `fusion_window_ms` | `FUSION_WINDOW_MS` (500) | New env var. The value is written per row, as the schema requires |
| `sensor_type` | From the topic name | Avro enum is uppercase (`RADAR`). The ERD note says lowercase. **T6 must pick one**; this note recommends uppercase to match the locked schema |
| `data_loss_pct` | Share of the micro-batch rejected by fused-schema `enforce()` | Same definition as the M5 staging writes, so the column means the same thing across tables |
| `latency_ms` | Write time − `timestamp_ms` | Event-to-fused-row latency, the same "creation → write" definition as M5 Item 6, so figures stay comparable |
| `schema_version` | `"1.0"` | |

**What `data_loss_pct` does not capture, logged plainly:** join inputs dropped as late. Spark
reports these per stateful operator as `numRowsDroppedByWatermark` in query progress. Week 22
should log them through a `StreamingQueryListener` and feed them into `fusion_status.data_loss`.
Unmatched ALICE events (Section 4) are tracked as a separate match-rate figure, not as loss.

**De-duplication key (requirement for T6):** a unique index on `(time, alice_event_id)` with
`ON CONFLICT DO NOTHING`. It includes `time`, as hypertable unique indexes must. It also handles the
fact that the ALICE producer reuses the same 68 `event_id`s every loop: each loop has a different
`time`, so the rows stay distinct, while a checkpoint replay of the same loop is de-duplicated.

## 8. (f) Trigger interval options and their cost (M5 Items 1 and 6)

A fused row can only be final after the watermark passes `a_time + 500 ms`. The watermark moves
forward one micro-batch after the data that advances it. That gives a **latency floor** of roughly
window + watermark delay + one to two trigger intervals.

| Option | Trigger | Delay | Estimated fused latency | Cost |
|---|---|---|---|---|
| A (M5 baseline) | 5 s | 5 s | ~10–15 s | Lowest per-batch overhead |
| B | 1 s | 5 s | ~6.5–7.5 s | 5× more micro-batches, each paying fixed planning and state-commit cost |
| C | 500 ms | 1 s | ~2–2.5 s | Highest overhead. A 1 s delay also tolerates less out-of-order data |

**Honest finding:** the ≤500 ms p95 bar **cannot be met** by an exact nearest-match join with a
±500 ms window. The engine must wait at least 500 ms after an ALICE event to know no closer sensor
event will arrive, and the watermark delay comes on top of that. No trigger setting alone removes
this floor. Options for the M10 framing, to discuss with Emrah, include:

- keeping this definition and reporting the floor;
- measuring the fusion stage's own processing overhead separately;
- a "first match" rule, which would reach lower latency but break determinism (D2/D4).

**Approved (1 October 2026):** Week 22 starts with **Option A** so the first fused figures compare
directly with M5, then measures B and C with the same latency SQL (M5 Item 6 action). The trigger
is an env var (`FUSION_TRIGGER_SECONDS`), so this needs no code change.

## 9. (g) Where the join runs

**Approved (1 October 2026): a separate `fusion-engine` service** (`services/fusion/`, Compose profile
`m6-and-above`), not inside spark-processor.

| | Separate `fusion-engine` ✅ | Inside `spark-processor` |
|---|---|---|
| Effect on staging writes (M5 Item 1) | Isolated | Shares executors with the stateful join |
| Checkpoints | Own volume and reset procedure | A reset affects all queries together |
| Shuffle partitions | Can differ per app | One value for everything |
| CPU cost (Item 7) | One more JVM on 8 shared cores. Kept low by skipping Avro decode (Section 3) | No extra JVM |
| Fit with the existing plan | Matches the Compose skeleton and the Week 22 plan (`fusion.Dockerfile`, Item 10 path fix) | Would change the Week 22 plan |

## 10. FK target (pending M6W21T7, Beyza)

**Pending.** The ERD points `fused_events.alice_event_id` and `sensor_event_id` at the production
`events` table, but streamed records land only in staging. This section is filled in from Beyza's
T7 recommendation at the Thursday 1 October checkpoint.

Inputs from this design that T7 should weigh:
- Fused rows reference **raw Kafka keys** (Section 3). A record rejected by spark-processor's `enforce()`
  could still be fused. At the observed 0 rejections this is rare, but a hard FK would make the
  fused insert fail.
- ALICE `event_id`s repeat every loop. Staging keeps only the first copy (`ON CONFLICT DO NOTHING`),
  so a staging FK would point every loop's fused rows at the loop-1 staging row.

## 11. (h) Final shuffle-partition values

Stateful queries lock the shuffle-partition count into their checkpoint, so these values are final
once the first checkpoint is written.

| App | Value | Reason |
|---|---|---|
| `spark-processor` | **8** (unchanged) | M5W20T1 root-cause fix. Near the core count. **Confirmed final for M6W21T2** before its first checkpoint |
| `fusion-engine` | **8** | Same reasoning. The join and the aggregation each keep 8 state-store partitions, which suits the low ALICE rate and bounded state (Section 5) |

Changing either value later needs a fresh checkpoint. The reset procedure is documented in
M6W21T2.

## 12. Evidence: local Spark spike (1 October 2026)

PySpark 3.5.6, local mode, file sources standing in for Kafka, 2 s watermark, 500 ms window, same
stage 1 and stage 2 logic as Section 4.

| Check | Result |
|---|---|
| Time-range-only join | Rejected: "Stream-stream join without equality predicate is not supported", which led to the bucket key |
| Nearest of two candidates (Δ300, Δ400) | Δ300 chosen ✅ |
| Tie at Δ200 | Earlier sensor timestamp chosen ✅ |
| Two ALICE events, same nearest sensor (D2) | Both matched it ✅ |
| Closer candidate in a later, on-time micro-batch | Waited and chose Δ80 over Δ400 ✅ (R3) |
| Candidate arriving behind the watermark | Dropped and counted in `numRowsDroppedByWatermark` ✅ |

Not covered by the spike, so it moves to Week 22: real Kafka sources, recovery from a checkpoint
after a restart, and throughput at load.

## 13. Week 22 implementation checklist

- [ ] T7 FK decision filled into Section 10; T6 DDL includes the `(time, alice_event_id)` unique index and
  the agreed `sensor_type` case
- [ ] `services/fusion/fusion_engine.py` per Sections 4–7; `FUSION_WINDOW_MS`, `FUSION_TRIGGER_SECONDS` env vars
- [ ] Checkpoint on a named volume, using the M6W21T2 pattern
- [ ] `StreamingQueryListener` for `numRowsDroppedByWatermark`, then `fusion_status`
- [ ] Latency and match-rate measured with the M5 Item 6 SQL method; trigger options B and C tested
- [ ] `write_fused_events()` stub replaced (closes M4 Item 4)

## 14. Sign-off

| Role | Name | Decision | Date |
|---|---|---|---|
| Schema authority | Abdullah | ☑ Approved (Section 10 pending T7) | 1 October 2026 |
| Section 10 FK input | Beyza (M6W21T7) | ☐ Provided | |