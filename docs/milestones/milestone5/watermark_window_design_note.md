# ALICE Watermark & Window Design Note

**Task ID:** M5W17T2
**Owner:** Abdullah
**Milestone:** M5 · Week 17
**Status:** Design complete — ready for Week 18 Spark Structured Streaming implementation
**GitHub Path:** `/docs/milestones/milestone5/watermark_window_design_note.md`
**Depends on:** M5W17T1 (ALICE Kafka producer), confirmed live and publishing to `alice-events` with the timestamp-rebasing fix described below.

---

## 1. Purpose

Documents the watermark and windowing approach Week 18's Spark Structured Streaming job should use when consuming `alice-events`, and — more importantly — the producer-side timestamp behavior that makes event-time watermarking viable at all for this stream. This isn't a purely theoretical design: it reflects a real problem found and fixed during T1's build, not an assumption carried forward untested.

## 2. Config referenced

| Value | Source | Current setting |
|---|---|---|
| `WATERMARK_DELAY_SECONDS` | `.env.example` | `5` |
| `alice-events` partition count | Confirmed via kafka-ui | `1` |
| `ALICE_REPLAY_INTERVAL_MS` | `alice_producer.py` | `500` (default) |
| `ALICE_LOOP_GAP_MS` | `alice_producer.py` | `1000` (default) |

## 3. The problem: replay loops vs. event-time watermarking

The 68 ALICE records carry real event-time (`timestamp_ms`) spanning only **~20 seconds** in the live dataset (confirmed at producer startup: `Dataset event-time span=20076ms`), all from the original 2010 detector run. But at the default pacing, one full producer loop takes **34 seconds** of wall-clock time (68 records × 500ms).

Spark's watermark is a one-way ratchet: once it observes `max(event_time) - watermark_delay`, anything timestamped earlier is treated as too late and dropped from windowed state. Without correction, every loop restart would republish `timestamp_ms` values ~20 seconds behind whatever the watermark had already advanced to — the entire loop, past loop 1, would be silently dropped from any windowed aggregation. Not a crash; a quiet correctness failure, which is worse.

## 4. The fix: per-loop timestamp rebasing (implemented in T1)

`alice_producer.py` now computes the dataset's real event-time span once at startup (`min`/`max` of `timestamp_ms` across the 68 records) and adds a per-loop offset before publishing:

```
loop_span_ms  = (max_ts - min_ts) + ALICE_LOOP_GAP_MS
loop_offset   = (loop_count - 1) * loop_span_ms
published_ts  = original_timestamp_ms + loop_offset
```

Loop 1 publishes the real, unshifted 2010 timestamps. Loop 2 onward shifts every record forward by a growing offset, so event-time keeps climbing and never repeats or goes backward at a loop boundary. Confirmed in a live run: `Loop 2 complete (timestamp offset=+21076ms)`, `Loop 3 complete (timestamp offset=+42152ms)` — strictly increasing, matching `loop_span_ms` exactly each time.

**Logged explicitly, not hidden:** past loop 1, published `timestamp_ms` values are no longer the literal 2010 ALICE timestamps — they're the real 68-record pattern (momentum, energy, track_count all unchanged), shifted forward in time. This is a deliberate scope decision for a replay-based prototype stream, consistent with how this project has handled similar batch-vs-stream tradeoffs (e.g., `schema_version` stamping from a registry rather than trusting the source verbatim).

**Within a single loop**, records are read `ORDER BY timestamp_ms` and published in that order at a fixed pace — event-time and arrival order already agree, so no lateness occurs within a loop by construction. Combined with the single-partition topic (Kafka guarantees ordering within a partition), the ALICE stream should never actually trigger the "late data" path in practice — but the watermark should still be configured correctly, both because it's the point of this task and because a future partition-count increase (not currently planned, but not ruled out) would reintroduce reordering risk that only a correctly configured watermark protects against.

## 5. Recommended Spark Structured Streaming design (Week 18)

**Event-time column:** derive a proper timestamp column from `timestamp_ms` (Avro `long`, ms since epoch) via `to_timestamp(col("timestamp_ms") / 1000)`.

**Watermark:**
```python
df.withWatermark("event_time", "5 seconds")
```
directly reusing the existing `WATERMARK_DELAY_SECONDS` value — no new config mechanism needed, per the M5 milestone doc's scope clarification.

**Windowing:** a 5-second tumbling window, grouped by source topic, for two purposes:
1. **Throughput monitoring** — a windowed count (`count("*")` per window) gives the running events/sec figure Week 19's benchmark task needs, rather than only a post-hoc total.
2. **Late-data visibility** — records that do arrive outside the watermark bound (shouldn't happen for `alice-events` per §4, but a real possibility for the sensor topics once Beyza/Omer's producers are live) show up as a measurable drop between "received" and "windowed" counts, rather than disappearing invisibly.

**Non-windowed path:** the actual per-record write into TimescaleDB staging should NOT be gated by the window/watermark — that's specifically for the aggregate throughput/lateness metrics. Every valid record still lands individually, same as the batch adaptation layer, just via `foreachBatch` instead of a JDBC batch read. Schema-versioning enforcement (`schema_versioning.enforce()`) should run per micro-batch, unchanged from its current batch-mode usage — no need to reimplement that logic for streaming.

## 6. Open items / caveats for Week 18

- This note covers `alice-events` only. The three sensor topics are Beyza's schema-conformance design (M5W17T3) and Omer's Week 18 producer build — the same `WATERMARK_DELAY_SECONDS` value applies, but their actual event-time distribution (and whether they need the same loop-rebasing treatment) is their call to make, not assumed here.
- If `alice-events`'s partition count ever increases beyond 1, re-verify this design — ordering-within-partition is currently doing real work to keep the "no lateness within a loop" claim in §4 true.
- `ALICE_LOOP_GAP_MS` (1000ms) is comfortably larger than typical network/processing jitter, but if `ALICE_REPLAY_INTERVAL_MS` is ever tuned down significantly for a future test, re-check that the gap still exceeds `WATERMARK_DELAY_SECONDS`-scale jitter.
