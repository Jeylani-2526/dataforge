# DataForge — M5 Validation Report

**Task:** M5W20T3
**Owner:** Abdullah
**Milestone:** M5 (Streaming Pipeline) — final validation ahead of M5 package assembly (T5)

---

## 1. Purpose

This report validates five things ahead of closing Milestone 5:

1. **Live streaming pipeline:** do all four topics have live producers, and does Spark Structured
   Streaming consume all four?
2. **Watermark/window correctness:** does the event-time watermark and windowing behave as designed,
   without silently dropping records?
3. **Throughput and data loss:** what does the real streaming pipeline achieve against the locked
   prototype bar, and why?
4. **Latency:** what is the pipeline's end-to-end latency? This is the metric M4 deferred to M5.
5. **Schema-versioning continuity:** is M4's batch-mode enforcement carried into the streaming
   writers unchanged, or reimplemented?

Each section cites committed source documents or runtime output, not figures that exist only in
console output.

---

## 2. Live streaming pipeline: all four streams

**Sources:** `m5w19t1_spark_consumer_verification.md`; `m5w20t2_throughput_benchmark.md` §5.

- **Producers live on all four pre-scoped topics:**
  - `alice-events` from `alice_producer.py`: 68 promoted ALICE records, replayed in rebased loops.
  - `sensor-radar`, `sensor-lidar`, `sensor-telemetry` from `sensor_producer.py`.
- **All four Spark queries confirmed healthy against live Kafka (M5W19T1):**
  - windowed monitoring queries `alice_throughput` and `sensor_throughput`;
  - staging writers `alice_staging_write` and `sensor_staging_write`.
  - Verified from live logs and direct SQL, not Adminer.
- **One blocking bug found and fixed during that verification:** the sensor producer published
  readable labels as `sensor_id`, which violated the schema's UUID contract. It now publishes stable
  UUID v4 values.
- **Re-verified in Week 20 on the modified consumer (M5W20T1):**
  - The sensor path processed ~2.6M streamed events with 0 errors.
  - The ALICE path ran 26 consecutive micro-batches on 25 September, all correctly skipped as
    redelivered duplicates (see §6).
  - `alice-ingestion` had been stopped cleanly, not crashed, before the Week 20 runs; this is
    explained in M5W20T2 §5.

**Status: PASS.**

---

## 3. Watermark/window correctness

**Sources:** `watermark_window_design_note.md` (M5W17T2); `m5w19t1_spark_consumer_verification.md`
§2a; `m5w20t2_throughput_benchmark.md` §3.

**Design as implemented:**
- Event time is derived from each record's `timestamp_ms`.
- `withWatermark("event_time", "5 seconds")` uses the existing `WATERMARK_DELAY_SECONDS`.
- 5-second tumbling windows are grouped by topic for throughput and late-data visibility.
- The staging write path is deliberately not gated by the watermark, so every valid record lands
  individually.
- For ALICE, the producer rebases timestamps per loop, so event time never goes backwards at a loop
  boundary.

**Evidence:**
- **Live windowed counts on all four topics (M5W19T1).** ALICE windows carry the original 2010
  detector timestamps: event time, not ingestion time, exactly as designed.
- **No late-data drops at 2.19M events (M5W20T2 drain test).** The design note measures late data as
  the gap between received and windowed counts:
  - The windowed sensor counts for the replayed period sum to exactly **2,191,854**.
  - The rows stored for the same period are the same **2,191,854**.
  - So no sensor record was dropped as late, while three topics were replayed at ~3,650 events/sec
    through a single shared watermark.

**Caveats** (analytical, not observed in any run; they affect windowed monitoring counts only, never
staging writes):
1. **Restarting the ALICE producer while Spark keeps running.**
   - The producer's loop offset resets to zero, so its timestamps jump back behind Spark's watermark.
   - The windowed ALICE counts then drop those records as late until event time catches up.
   - Staging writes are unaffected.
   - Operating rule: restart `spark-processor` after restarting `alice-ingestion`. This was the
     order used on 25 September.
2. **One shared watermark for three sensor topics.**
   - If one topic's event time falls more than 5 s behind the others (for example, an uneven
     backlog), its windowed counts drop records.
   - Kafka's per-trigger cap is split proportionally across topics, which kept them aligned in the
     drain test.
   - Re-check this if topic partition counts or producer rates diverge.

**Status: PASS**, with two documented operational caveats.

---

## 4. Throughput and data loss

**Sources:** `m5w19t2_throughput_benchmark.md`; `m5w20t1_write_path_root_cause.md`;
`m5w20t2_throughput_benchmark.md`.

| Metric | Bar | Result | Status |
|---|---|---|---|
| Throughput, like-for-like (M5W19T2 method) | ≥ 10,000 events/sec | **1,417 events/sec** (was 594) | **FAIL** |
| Throughput, pipeline capacity (backlog drain) | ≥ 10,000 events/sec | **~3,650 events/sec** | **FAIL** |
| Data loss | ≤ 1% | **0.0%** (2,191,834 published → all stored; 0 rejected) | PASS |

**How the gap was worked (Week 20):**
- **The pre-fix figure (594/sec) was traced to one serial DB connection.** Pooling the connection
  was implemented and measured first. It worked as designed but left throughput unchanged (~471/sec).
- **The actual root cause was Spark's default of 200 shuffle partitions.**
  - Every trigger, the two windowed monitoring queries ran 200 stateful tasks each, starving the
    staging writes of CPU.
  - It was reproduced locally (512/sec against 594/sec in production) before any fix was chosen.
- **The fix:**
  - 8 shuffle partitions;
  - a 50,000-record cap per micro-batch;
  - a COPY-based insert with unchanged duplicate handling;
  - per-phase timing logs.
- **Result:** 2.4× like-for-like and 6.1× pipeline capacity, verified on the real stack, with zero
  data loss.
- **Compared with M4:** the like-for-like streaming figure now exceeds M4's batch-mode 1,135.05
  events/sec. Before the fix it was below it.

**Why the bar is still missed (measured, per 50,000-row batch):**
- The time splits into insert 6.9 s (~55%), `enforce()` 4.2 s (~33%) and collect 1.5 s (~12%),
  ~12.6 s in total. Reaching the bar needs ~5 s.
- All services share 8 CPUs, and the generator itself tops out at ~7,250 events/sec when running
  alone.
- Next steps are logged in `open_items_m5.md`: insert diagnostics, parallel writers, and generator
  scaling.

**Status: FAIL, root-caused and substantially improved, gap open.** This is M5's real throughput
verdict. It supersedes M4's batch-mode measurement, as the roadmap intends.

---

## 5. End-to-end latency

**Source:** read-only SQL on `raw_sensor_events_staging`, run 25 September 2026.

**What is measured:**
- **Definition:** the producer's event creation (`timestamp_ms`) to the Spark writer stamping the
  batch (`load_timestamp`).
- **Scope:** Kafka transit, trigger wait, collect and `enforce()`. It excludes the final insert,
  which takes ~30 ms per batch at the default rate.
- **Clock:** both timestamps come from the same Docker host clock.
- **Streams:** sensor only. ALICE's `timestamp_ms` is historical 2010 time and cannot be used.

| Period | Rows | p50 | p95 | p99 | Max |
|---|---|---|---|---|---|
| Default producer rate (24 Sep, 17:37–17:49 +03:00) | 3,578 | 3.4 s | **5.7 s** | 6.0 s | 6.6 s |
| Saturated, M5W20T2 Run 3 (17:10–17:15 +03:00) | 493,528 | 78 s | 148 s | 153 s | 155 s |

| Metric | Bar | Result | Status |
|---|---|---|---|
| Latency, p95 end-to-end | ≤ 500 ms | **5.7 s** (default rate) | **FAIL** |

**Why:**
- **The failure is structural, not load-driven.** With a 5-second processing trigger, a record waits
  up to 5 s for the next micro-batch before any work starts. The p50 of 3.4 s and p95 of 5.7 s match
  that wait plus ~1 s of processing.
- **Under saturation latency grows further:** producers outpace the pipeline, so the Kafka backlog
  and waiting time grow throughout the run.
- **Meeting ≤500 ms needs a design change:** a much shorter trigger (sub-second), or a different
  processing mode. This trades off against per-batch overhead and throughput. Logged in
  `open_items_m5.md` as an input to M10's performance validation.
- **Not comparable to M4's 0.1334 ms.** That figure was per-record processing time inside the
  adaptation layer, not end-to-end latency, as its own methodology note says.

**Status: FAIL (first end-to-end measurement), cause identified, design change needed.**

---

## 6. Schema-versioning continuity: batch to streaming

`schema_evolution_policy.md` defines the versioning contract. M4 showed it enforced by running
pipeline code. This section confirms the streaming writers use the same enforcement rather than a
reimplementation.

| Aspect | M4 (batch) | M5 (streaming) |
|---|---|---|
| Enforcement module | `services/adaptation-layer/schema_versioning.py` | **The same file**, mounted read-only into the Spark container (`docker-compose.yml`: `./services/adaptation-layer/schema_versioning.py:/app/src/schema_versioning.py:ro`). One source, no copy. |
| Call site | `enforce()` in `_write_partition_to_avro()`, per partition | `enforce()` in each `foreachBatch` staging writer, per micro-batch |
| Checks | Version drift + Avro serialize → deserialize → compare | Identical: same function, unmodified |
| Rejected records | Excluded and counted in `data_loss_pct` | Excluded and counted in `data_loss_pct`; since M5W20T1 the rejection reason is also logged |
| Staging target | `raw_*_staging` via `staging_ingestion_script.py` | Same tables and column shape; `test_staging_columns_match_init_db_sql` fails on drift from `init-db.sql` |
| Producer-side checks | n/a (batch read) | ALICE producer: full round-trip before publishing. Sensor producer: Avro serialization against the schema |

**Runtime evidence, from normal pipeline execution:**
- **M5W19T1:** 40+ ALICE and 29 sensor micro-batches, 0 rejected.
- **M5W20T2:** 2,635,383 sensor records (Run 3 + drain test), 0 rejected, 0 version drift.
- **25 September:** 26 ALICE micro-batches, 0 rejected.

**Test evidence** (`services/streaming/spark/src/test_spark_consumer.py`, runs in CI):
- A version-drift batch is rejected and never reaches the database.
- In M5W20T1's equality test, a NaN record was rejected by the round-trip check on both the old and
  new writers.

**Downstream promotion:** streamed rows have the same shape as batch-loaded rows, so promotion logic
needs no change by design. Promotion of streamed rows is part of Beyza's M5 database contribution and
is not re-exercised here.

**Status: PASS.** Schema-versioning enforcement carries from batch into streaming as the same
executable code, running on every streamed record.

---

## 7. Correction to M5W19T1 §5 (checkpointing risk)

M5W19T1 §5 states that at-least-once redelivery is protected by `ON CONFLICT` "for ALICE only", with
sensor events at risk of duplication. **This is incorrect:**
- Both staging tables declare `event_id … UNIQUE`.
- Both inserts use `ON CONFLICT (event_id) DO NOTHING`, both at the Week 20 carry-in commit
  (`10cf013`) and now.
- Redelivered sensor events are therefore deduplicated exactly like ALICE.

**The real risk of having no checkpoint is the opposite: skipped events.**
- On restart the consumer starts from the `latest` offset.
- Anything published while it was down is never consumed.
- M5W20T2's drain test demonstrated this: it needed the replay timestamp
  (`SPARK_STARTING_TIMESTAMP_MS`, added in M5W20T1) precisely because a plain restart would have
  skipped the backlog.

The open item stands, with its impact restated in `open_items_m5.md`.

---

## 8. Summary

| Area | Status |
|---|---|
| Live producers + Spark consumption, all 4 topics | PASS |
| Watermark/window correctness | PASS (2 documented operational caveats) |
| Throughput vs. prototype bar | FAIL: 1,417/sec like-for-like, ~3,650/sec capacity; root-caused, 2.4×/6.1× improved, gap open |
| Data loss | PASS (0.0%) |
| Latency, p95 end-to-end | FAIL: 5.7 s at default rate; structural (5 s trigger), design change needed |
| Schema-versioning continuity, batch → streaming | PASS |

M5's streaming pipeline is validated as functionally correct, loss-free and schema-compliant across
all four streams. Two prototype-bar metrics remain open:
- **Throughput:** now measured as a per-phase cost breakdown rather than a single number.
- **Latency:** measured end to end for the first time, and failing for a structural reason that needs
  a design decision.

Both are carried into the M5 package and `open_items_m5.md` exactly as measured, consistent with the
project's practice of reporting gaps plainly.
