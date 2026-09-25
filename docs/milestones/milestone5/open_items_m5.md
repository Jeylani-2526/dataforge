# DataForge — M5 Open Items Log

**Originating Task ID:** M5W20T4
**Owner:** Abdullah
**Milestone:** M5 · Week 20
**Status:** Open — nine items tracked. Items 4–5 are pending Beyza's M5W20T8/T9, which are in
progress at the time of writing.
**GitHub Path:** `/docs/milestones/milestone5/open_items_m5.md`

**Amendment history:**
- M5W20T4 — Document created; Items 1–9 logged.
  - Items 1–5 were scoped by the Week 20 plan.
  - Items 6–9 surfaced during M5W20T1–T3.

---

> **Why this document exists**
> The M5 milestone document lists an open items log as both a Key Output and a Success Criterion,
> and no M5 equivalent of `open_items_m4.md` existed. It follows the same convention:
> - each item is logged explicitly, with an honest scope and a stated resolution path;
> - nothing is smoothed into a single line or left only in a code comment.
>
> **Relationship to `open_items_m4.md`:**
> - M4 Items 1, 3 and 4 (zero-track ALICE events, net-momentum outlier, fused-event stub) remain
>   open and are tracked there, deferred to M6/M7. They are not duplicated here.
> - M4 Item 2 was closed by M5W19T8.
> - M4 Item 5 (batch throughput) is superseded by Item 1 below.
> - Both changes are recorded in that log's amendment history.

---

## Item 1 — Streaming Throughput Below Prototype Bar

**Finding:** The real streaming benchmark misses the locked ≥10,000 events/sec bar.

| Measurement | Result | Source |
|---|---|---|
| M5W19T2 baseline | 594 events/sec | `m5w19t2_throughput_benchmark.md` |
| M5W20T2 like-for-like (after the M5W20T1 fix) | 1,417 events/sec | `m5w20t2_throughput_benchmark.md` |
| M5W20T2 pipeline capacity (backlog drain) | ~3,650 events/sec | `m5w20t2_throughput_benchmark.md` |

- **Root cause found and removed (M5W20T1):** Spark's default of 200 shuffle partitions made the
  windowed monitoring queries starve the staging writes.
- **What limits throughput now is measured per record.** Per 50,000-row micro-batch:
  - insert: 6.9 s;
  - `enforce()`: 4.2 s;
  - collect: 1.5 s;
  - ~12.6 s in total, against the ~5 s needed for the bar.
- **Data loss is 0.0%.** Throughput is the only data-path metric outside the bar (see Item 6 for
  latency).

**Interim decision (this week):** **Logged as a known gap.** The measured improvement is kept, and
M5 closes with the figures above reported exactly as measured.

**Deferred to:** M6 (planning), then M10 (final performance validation against the prototype bar).

**Rationale for deferring:** The remaining levers are design-level changes rather than same-week
fixes:
- parallel writers, which would change the per-micro-batch write design;
- database-side tuning, which is Beyza's domain;
- generator capacity (Item 7).

Each is aimed at a specific measured cost, so the next step is choosing among them, not guessing.

**What would trigger resolution:**
1. Insert diagnostics explain the 6.9 s insert cost.
2. A parallel-writer design is decided.
3. A benchmark with a generator that can exceed 10,000 events/sec (Item 7).

**Action items:**
- [ ] Abdullah: insert diagnostics, read-only (staging table/index sizes, TimescaleDB `shared_buffers`, COPY timing against table size)
- [ ] Abdullah: parallel-writer design proposal (per-partition `enforce()` + insert), for a team decision before implementation
- [ ] Beyza: review the staging indexes and DB settings against the insert cost; agree how the ~3.5M synthetic benchmark rows now in `raw_sensor_events_staging` are cleaned up
- [ ] Omer: generator scaling (see Item 7)

---

## Item 2 — No Checkpointing on the Spark Streaming Queries

**Finding:** Originally logged in `m5w19t1_spark_consumer_verification.md` §5. None of the four
queries sets a `checkpointLocation`, so a container restart loses Kafka offsets and streaming state.

**Impact, corrected (M5W20T3, `m5_validation_report.md` §7):**
- **Redelivery is safe for both streams.** Both staging tables have a unique `event_id`, and both
  inserts use `ON CONFLICT (event_id) DO NOTHING`, so redelivered events are deduplicated.
- **The real risk is skipped events.** On restart the consumer starts from `latest`, so events
  published while it is down are never consumed.
- **This was demonstrated, not assumed.** M5W20T2's drain test needed the replay setting
  `SPARK_STARTING_TIMESTAMP_MS` (added in M5W20T1) because a plain restart would have skipped the
  backlog.

**Interim decision (this week):** **Kept open, no change.** Acceptable for local verification. The
replay setting is a test tool, not a substitute for checkpointing.

**Deferred to:** Post-M5 hardening, before M6's stream-stream join. The join is stateful, so it
needs checkpointed state to survive restarts.

**Rationale for deferring:** Adding checkpointing is not a one-line change:
- It needs a persistent volume in `docker-compose.yml`.
- It needs a restart/recovery test.
- It needs an agreed checkpoint-reset procedure: once a checkpoint exists, Spark locks the shuffle
  partition count (M5W20T1) for stateful queries.

That is best designed together with M6's stateful join rather than twice.

**What would trigger resolution:** Start of M6 join design, or any use beyond local
dev/verification.

**Action items:**
- [ ] Abdullah (M6): add `checkpointLocation` on a named volume for all queries; verify with a kill-and-restart test that offsets resume and no events are skipped
- [ ] Abdullah (M6): document the checkpoint-reset procedure, including the shuffle partition lock

---

## Item 3 — Dead `EVENTS_PER_SECOND` Configuration

**Finding:** From `m5w19t4_docker_infra_verification.md`, re-confirmed this week.
- `EVENTS_PER_SECOND` is declared in `docker-compose.yml` (`${EVENTS_PER_SECOND:-100}`) and
  `.env.example`.
- It is never read anywhere in `sensor_producer.py` or its Dockerfile.
- The actual rate control is `SENSOR_PUBLISH_INTERVAL_MS`.
- The unused setting implies a records/sec control that does not exist.

**Interim decision (this week):** **Logged, not changed.** It is not blocking, and its right
resolution depends on Item 7.

**Deferred to:** The generator-scaling work in Item 7.

**Rationale for deferring:** Two resolutions are possible, and Item 7 decides between them:
- **Wire it up** as a real rate target. That is useful if the scaled generator needs a precise
  target, for example 10,000/sec.
- **Remove it.**

Deciding before Item 7 risks doing the work twice.

**What would trigger resolution:** An Item 7 generator design decision.

**Action items:**
- [ ] Omer: as part of Item 7, either implement `EVENTS_PER_SECOND` as a real rate limiter or remove it from `docker-compose.yml` and `.env.example`

---

## Item 4 — `sensor_id` Documentation / DB-Type Mismatch (Pending M5W20T8)

**Finding:** From `m5w19t1_spark_consumer_verification.md` §3.
- M5W19T6's conformance note (`docs/database/sensor_streamed_record_erd_api_conformance.md`) marked
  `sensor_id` as "varchar ✅" after validating only the Avro round-trip, which cannot catch a UUID
  format violation.
- The real constraint is UUID v4, enforced by `init-db.sql` and documented in
  `sensor_schema_v1.avsc`.
- The gap caused a live crash of `sensor_staging_write` until the producer was fixed the same day
  (stable UUID v4 per sensor instance).

**Interim decision (this week):** **Code fixed (M5W19T1); documentation correction in progress.**
M5W20T8 (Beyza) re-validates against the fixed producer and corrects the field type and validation
method in the conformance table.

**Status:** **Pending.** M5W20T8 was in progress when this log was created.

**What would trigger resolution:** M5W20T8 committed. This entry is then amended to **Resolved**,
citing that commit.

**Action items:**
- [x] Abdullah: producer fix (M5W19T1)
- [ ] Beyza: M5W20T8 — correct the conformance note; amend this entry to Resolved with the commit reference

---

## Item 5 — Sustained Multi-Hour Load Not Yet Verified (Pending M5W20T9)

**Finding:**
- Both M5W19T6 and `repeat_generation_device_diversity_closure.md` (M5W19T8) flagged that the
  producer has not been verified under sustained multi-hour load.
- M5W20T9 (Beyza) runs that soak test against the fixed pipeline, watching for:
  - connection degradation;
  - memory growth;
  - record-loss drift over time.

**Context from this week, for the soak test:**
- The consumer now holds one persistent DB connection per writer and caps micro-batches at 50,000
  records.
- Under unthrottled load producers outpace the pipeline (Item 1), so a Kafka backlog grows. At the
  default rate the pipeline keeps up.
- Staging holds ~3.5M synthetic rows from Week 20 benchmarks.

**Status:** **Pending.** M5W20T9 was in progress when this log was created.

**What would trigger resolution:** M5W20T9's note committed to `/docs/data/`. This entry is then
amended with its findings: closed, or precisely re-scoped.

**Action items:**
- [ ] Beyza: M5W20T9 — soak test and verification note; amend this entry with the findings

---

## Item 6 — End-to-End Latency Above Prototype Bar (New, M5W20T3)

**Finding:** First end-to-end latency measurement, reported in `m5_validation_report.md` §5.
- **Definition:** event creation (`timestamp_ms`) to the Spark writer's batch stamp
  (`load_timestamp`).
- **Default producer rate:** p50 3.4 s, **p95 5.7 s**, p99 6.0 s.
- **Saturated:** p95 148 s, because the backlog grows.
- **Bar:** p95 ≤ 500 ms.
- **The cause is structural.** The 5-second processing trigger alone makes a record wait up to 5 s
  before any work starts. The numbers match that wait plus ~1 s of processing.
- **Not comparable to M4's 0.1334 ms.** That was per-record processing time, not end-to-end.

**Interim decision (this week):** **Logged as a known gap; no trigger change in M5.** Shortening the
trigger trades against per-batch overhead and throughput (Item 1). Changing it without a combined
design would likely worsen Item 1.

**Deferred to:** M6 (design decision, together with the stateful join's latency needs), then M10
(final validation).

**Rationale for deferring:** Meeting ≤500 ms needs a sub-second trigger or a different processing
mode, plus a write path fast enough to keep up at that cadence. It is one design problem with
Item 1, not a separate fix.

**What would trigger resolution:** A combined throughput/latency design decision (trigger interval,
write path) at M6 planning.

**Action items:**
- [ ] Abdullah: include trigger-interval options in the Item 1 parallel-writer design proposal, and measure p95 with the same SQL method for each option tested
- [ ] Abdullah: keep the latency SQL (validation report §5) as the standard measurement, so later figures stay comparable

---

## Item 7 — Generator Capacity and Shared CPU (New, M5W20T2)

**Finding:** From `m5w20t2_throughput_benchmark.md` §4.
- **The generator is a single Python loop.** Unthrottled, `sensor_producer.py` publishes ~7,250
  events/sec when Spark is stopped, but only ~3,650 when Spark is running.
- **Everything shares the host's 8 CPUs:** Kafka, Spark, TimescaleDB and the producers. Spark's
  per-phase times roughly doubled while unthrottled producers ran.
- **Consequence:** the ≥10,000 events/sec bar cannot be tested end to end with the current
  generator, even with a perfect pipeline.
- Earlier reports of a ~3,400/sec "generator ceiling" were largely this CPU sharing.

**Interim decision (this week):** **Logged; no generator change in M5.** The backlog-drain method
(M5W20T2) measures pipeline capacity independently of the generator in the meantime.

**Deferred to:** Before the next throughput benchmark aimed at the bar, and no later than M10.

**Rationale for deferring:** Scaling the generator is Omer's area (synthetic data generation, per
the roadmap). Doing it before Item 1's pipeline work lands would only move the bottleneck back to
the pipeline.

**What would trigger resolution:** Item 1 pipeline capacity approaching ~10,000 events/sec, or M10
benchmark planning.

**Action items:**
- [ ] Omer: generator scaling design (for example, several producer processes or replicas), including a precise rate target (see Item 3)
- [ ] Team: decide the CPU allocation for benchmark runs (Docker Desktop resources, or running producers on separate hardware), so producers and the pipeline don't compete

---

## Item 8 — Watermark Operational Caveats (New, M5W20T3)

**Finding:** Analytical, not observed in any run. Reported in `m5_validation_report.md` §3.
Both caveats affect the windowed monitoring counts only; staging writes are never affected.

1. **Restarting `alice-ingestion` while Spark keeps running.**
   - The producer's timestamp-rebasing offset resets to zero, so ALICE event time jumps back behind
     Spark's watermark.
   - The windowed ALICE counts drop those records as late until event time catches up.
2. **One shared watermark for the three sensor topics.**
   - If one topic's event time falls more than 5 s behind the others, for example through an
     uneven backlog, its records drop from the windowed counts.
   - The per-trigger cap is split proportionally across topics, which kept them aligned in the drain
     test (windowed count equal to stored count, 2,191,854).

**Interim decision (this week):**
- **Documented, with an operating rule:** restart `spark-processor` after restarting
  `alice-ingestion`.
- No code change.

**Deferred to:** M6. The stream-stream join makes watermark behaviour correctness-critical, not
monitoring-only.

**Rationale for deferring:** In M5 the effect is limited to monitoring counts. In M6, a record
dropped as late from the join means a missing fused event. The design choices belong to the join
design:
- persisting the producer's loop offset across restarts;
- per-topic streams;
- the watermark delay.

**What would trigger resolution:** M6 join design.

**Action items:**
- [ ] Abdullah: add the restart-order rule to the operations notes / README run instructions (with T6's README update)
- [ ] Abdullah (M6): re-evaluate both caveats as correctness requirements in the join design

---

## Item 9 — Spark Container Does Not Stop Within Docker's Grace Period (New, M5W20T2)

**Finding:** From `m5w20t2_throughput_benchmark.md` §5.
- `docker compose stop spark-processor` took 11.6 s, longer than Docker's default 10 s grace period,
  so Docker force-kills the container (exit code 137).
- The container also exited with code 137 when the stack stopped on 24 September.
- Running out of memory cannot be ruled out after the fact, because the restart reset the container
  state.

**Interim decision (this week):** **Logged; no change.** No data impact was observed:
- inserts are transactional per batch;
- redelivery is deduplicated (Item 2).

**Deferred to:** Item 2's checkpointing work. A clean shutdown matters once checkpoints must be
written consistently.

**Rationale for deferring:** A forced kill currently loses nothing that a clean stop would keep,
because there are no checkpoints. Once checkpointing lands, it can.

**What would trigger resolution:** Item 2's implementation.

**Action items:**
- [ ] Abdullah / Omer: set `stop_grace_period` for `spark-processor` (for example 30 s) and confirm the shutdown handler stops all queries within it (check `docker inspect` for `OOMKilled=false` after a stop)

---

## Summary

| Item | Status | Deferred to | Trigger for resolution |
|---|---|---|---|
| 1. Streaming throughput below bar (1,417 like-for-like / ~3,650 capacity vs. ≥10,000) | Open, root cause fixed, gap measured per phase | M6 planning → M10 | Insert diagnostics + parallel-writer decision + Item 7 generator |
| 2. No checkpointing (risk: skipped events on restart) | Open, impact corrected | Post-M5, before M6 join | M6 join design |
| 3. Dead `EVENTS_PER_SECOND` config | Open | Item 7 | Generator design decision |
| 4. `sensor_id` doc / DB-type mismatch | **Pending M5W20T8** (code fixed M5W19T1) | M5 Week 20 | M5W20T8 committed |
| 5. Sustained multi-hour load | **Pending M5W20T9** | M5 Week 20 | M5W20T9 note committed |
| 6. End-to-end latency p95 5.7 s vs. ≤500 ms | Open, structural (5 s trigger) | M6 design → M10 | Combined throughput/latency design |
| 7. Generator capacity + shared CPU | Open | Before the next bar-level benchmark / M10 | Pipeline capacity nearing the bar |
| 8. Watermark operational caveats (monitoring-only in M5) | Open, operating rule documented | M6 | M6 join design |
| 9. Spark exceeds the stop grace period (exit 137) | Open, no data impact observed | With Item 2 | Checkpointing implementation |

**Two prototype-bar metrics are open (Items 1 and 6)**, both measured end to end with a named cause.
Data loss (0.0%) and schema-versioning enforcement pass.

**Items 4 and 5 close this week** once Beyza's M5W20T8/T9 are committed. Items 2, 3 and 7–9 are
each tied to the downstream work that has the information or infrastructure needed to decide them
properly.
