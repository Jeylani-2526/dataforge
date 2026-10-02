# DataForge — Milestone 5 Package Cover Note

**Milestone:** M5 — Streaming Pipeline
**Task:** M5W20T5
**Owner:** Abdullah
**Date:** 27 September 2026 (updated 1 October 2026, M6W21T4)
**Package status:** Assembled.
- All seven M5 success criteria are met. The M5 review with Emrah was held on 30 September 2026
  (Section 6).
- **Both prototype-bar metrics measured in M5 are missed** (throughput and latency); they are
  carried forward with named causes.
- One teammate item was pending at assembly: Ömer's M5W20T11, committed on 1 October (Section 6).
  Review comments on Beyza's M5W20T10 were raised and resolved (`1dcd0ea`).

---

## 1. What M5 Covers

Milestone 5 builds the Streaming Pipeline:
- live Kafka (KRaft) producers for ALICE and three synthetic sensor streams;
- Spark Structured Streaming consumers with event-time watermark/window logic;
- the same schema-versioning enforcement as M4, now running on every streamed record;
- writes into the TimescaleDB staging tables;
- the roadmap's real streaming throughput benchmark against the ≥10,000 events/sec prototype bar.

---

## 2. What's Complete — Per Person

### Abdullah

| Artifact | Task | Path | Status |
|---|---|---|---|
| Kafka migration ZooKeeper → KRaft (M5 preparation) | — | `docker-compose.yml` | Complete (`887ddaa`, `a2c9798`, `0b2c44a`) |
| ALICE Kafka producer + Dockerfile; watermark/window design note | M5W17T1/T2 | `services/data-sources/alice-ingestion/`, `docs/milestones/milestone5/watermark_window_design_note.md` | Complete (`316f181`) |
| Spark Structured Streaming consumer + Spark Dockerfile | M5W18T8/T9 | `services/streaming/spark/src/spark_consumer.py`, `infrastructure/docker/spark.Dockerfile` | Complete (`37ce516`) |
| Consumer verification on all four topics, incl. same-day `sensor_id` producer fix | M5W19T1 | `docs/milestones/milestone5/m5w19t1_spark_consumer_verification.md` | Complete (`fb26fc9`) |
| First streaming throughput benchmark (594 events/sec) | M5W19T2 | `docs/milestones/milestone5/m5w19t2_throughput_benchmark.md` | Complete (`fb26fc9`); corrected in M5W20T2 |
| M4 GitHub tags + README (M4 carry-in) | M5W19T3 | README; tags `M4-W16-*` | Complete (`fb26fc9`, 20 September) |
| Docker infrastructure audit | M5W19T4 | `docs/milestones/milestone5/m5w19t4_docker_infra_verification.md` | Complete (`fb26fc9`) |
| Throughput root cause + fix (shuffle partitions, batch cap, COPY insert, persistent connections, phase timing, 13 tests) | M5W20T1 | `docs/milestones/milestone5/m5w20t1_write_path_root_cause.md`, `services/streaming/spark/src/` | Complete (`59080e9`) |
| Post-fix benchmark + backlog-drain capacity test | M5W20T2 | `docs/milestones/milestone5/m5w20t2_throughput_benchmark.md` | Complete (`59080e9`) |
| M5 validation report | M5W20T3 | `docs/milestones/milestone5/m5_validation_report.md` | Complete (`59080e9`) |
| M5 open items log (+ `open_items_m4.md` Items 2/5 amended) | M5W20T4 | `docs/milestones/milestone5/open_items_m5.md` | Complete (`59080e9`); amended in this task's commit |
| M5 package cover note | M5W20T5 | this document | This task's commit |

### Beyza

| Artifact | Task | Path | Status |
|---|---|---|---|
| Sensor Kafka producer schema conformance design | M5W17T3 | `docs/database/sensor_kafka_producer_schema_conformance.md` | Complete (`3790871`) |
| Sensor Kafka producer (RADAR/LIDAR/TELEMETRY) | M5W18T4 | `services/data-sources/sensor-generators/src/sensor_producer.py` | Complete (`329fb02`) |
| Sensor-generators Dockerfile | M5W18T5 | `infrastructure/docker/sensor-generators.Dockerfile` | Complete (`79f62e1`) |
| Design note language cleanup | M5W18T7 | `docs/database/` | Complete (`9c203a3`) |
| ERD/API conformance note; DB contribution draft | M5W19T6/T7 | `docs/database/sensor_streamed_record_erd_api_conformance.md` | Complete (`da0ddee`, `33f0f90`) |
| Repeat-generation mode + device diversity closure (closes M4 Item 2) | M5W19T8 | `docs/data/repeat_generation_device_diversity_closure.md` | Complete (`da0ddee`) |
| `sensor_id` conformance correction, `varchar` → `uuid` | M5W20T8 | `docs/database/sensor_streamed_record_erd_api_conformance.md` | Complete (`2c3c2c8`); closes M5 Item 4 |
| KRaft CONTROLLER listener bind fix | — | `docker-compose.yml` | Complete (`9f3db08`); see M5 Item 10 on the voter address |
| 4.5-hour sustained-load soak test | M5W20T9 | `docs/data/m5w20t9_soak_test.md` | Complete (`3de3ce2`) at the default producer rate; resolves M5 Item 5 for stability, high-load scope re-opened |
| M5 database contribution section (final) | M5W20T10 | `docs/milestones/milestone5/m5_database_contribution.md` | Complete (`07d3b6c`; corrections `1dcd0ea`) |

### Ömer

| Artifact | Task | Path | Status |
|---|---|---|---|
| Docker build-context path fix, `../../` → `../../../` (sensor-generators, spark) | — (commit labelled `M3W18T1`) | `docker-compose.yml` | Complete (`5708621`) |
| Kafka (KRaft) / kafka-ui verification note, incl. the `m5-and-above` build-failure report | M5W19T9 (commit labelled `M3W19T9`) | `docs/milestones/milestone3/verification_note_carry_on.md` → moved to `docs/milestones/milestone5/m5w19t9_kafka_verification_note.md` in the T6 commit | Complete (`10cf013`), after three weeks' carry-in; was misfiled and mislabelled |
| Diagnose and resolve the `m5-and-above` build failure on his machine | M5W20T11 | — | **Not started** |

For M5W20T11, the committed history points to a likely cause (M5 Item 10). At `10cf013` the repo's
alice and spark paths were already correct. The failing path (`...\services\infrastructure`) matches
only the old `../../` spark path, which Ömer's own `5708621` fixed. A stale or locally modified
checkout is the likely explanation. **Unconfirmed.**

---

## 3. Prototype Bar — Throughput and Latency Missed; Data Loss Passes

Per the M5 validation report (`m5_validation_report.md`, M5W20T3):

| Metric | Bar | Result | Status |
|---|---|---|---|
| Throughput, like-for-like | ≥ 10,000 events/sec | **1,417 events/sec** (was 594) | **FAIL** |
| Throughput, pipeline capacity (backlog drain) | ≥ 10,000 events/sec | **~3,650 events/sec** | **FAIL** |
| Latency, p95 end-to-end | ≤ 500 ms | **5.7 s** (default rate) | **FAIL** |
| Data loss | ≤ 1% | 0.0% | PASS |

Four throughput figures exist in the record and should not be conflated:

| Figure | What it is |
|---|---|
| 594 events/sec | M5W19T2, before any fix |
| ~471 events/sec | Planned fix only (persistent DB connection). Worked as designed, did not help. |
| 1,417 events/sec | Full M5W20T1 fix, same method as the baseline. **The official comparison.** |
| ~3,650 events/sec | Pipeline capacity with producers not competing for CPU |

**Root cause found and removed:** Spark's default of 200 shuffle partitions made the windowed
monitoring queries starve the staging writes. It was reproduced locally before being fixed. The
remaining gap is measured per phase (insert ~55%, `enforce()` ~33%, collect ~12%). The generator
itself tops out at ~7,250 events/sec alone, so the bar cannot yet be tested end to end.

**Latency is the first end-to-end measurement**, and the failure is structural. The 5-second
trigger alone makes a record wait up to 5 s. It is not comparable to M4's 0.1334 ms, which was
per-record processing time.

**Disposition:** carried forward as `open_items_m5.md` Items 1 (throughput), 6 (latency) and
7 (generator), with M6/M10 resolution paths. M5's streaming figures supersede M4's batch figure
(`open_items_m4.md` Item 5, marked superseded).

---

## 4. M5 Success Criteria

| Criterion (M5 milestone document) | Status | Evidence |
|---|---|---|
| Kafka in Docker Compose with live producers on all four topics | Met | M5W19T1; `alice-ingestion` restart verified 25 Sep |
| Spark consumes all four topics with correct watermark/window logic | Met | Validation report Section 2–3; drain test: windowed count = stored count (2,191,854) |
| Real streaming throughput benchmark reported against the bar, whatever the result | Met | M5W19T2, M5W20T2; bar missed, reported plainly |
| Device diversity + repeat-generation mode, closing M4 Item 2 | Met | M5W19T8; `open_items_m4.md` Item 2 amended |
| M4 carry-ins closed: tags applied and confirmed | Met | `M4-W16-*` tags, 20 September (`fb26fc9`) |
| M5 open items log with resolution paths | Met | `open_items_m5.md`, 10 items |
| Package assembled, cover note written, M5 review scheduled with Emrah | Met | This note; review held Wed 30 September 2026, package accepted as presented (Section 6) |

The prototype bar is not an M5 exit criterion. Consistent with the M4 precedent, README keeps M5
**In Progress** while the bar is missed (T6).

---

## 5. What Feeds M6 (Data Fusion & Synchronization)

- **Four live, schema-enforced event-time streams.**
  - ALICE (with timestamps rebased per loop) and RADAR/LIDAR/TELEMETRY on their own topics.
  - A per-topic event-time watermark (`WATERMARK_DELAY_SECONDS`) and 5 s windows, both verified.
  - M6's stream-stream join can subscribe to the same topics directly.
- **One enforcement point.** `schema_versioning.enforce()`, the same code as M4, runs on every
  streamed record. `fused_event_schema_v1.avsc` is ready for a join to feed.
  `write_fused_events()` remains a deliberate stub (`open_items_m4.md` Item 4).
- **Streaming engine settings a stateful join needs:**
  - explicit shuffle partitions (`SPARK_SHUFFLE_PARTITIONS`), to be sized ≈ cores for the join too;
  - a bounded micro-batch (`SPARK_MAX_OFFSETS_PER_TRIGGER`);
  - a replay point for testing (`SPARK_STARTING_TIMESTAMP_MS`);
  - per-phase timing logs.
- **Carried-in constraints M6 must design for:**
  - **Checkpointing (Item 2):** a stateful join needs it. Set it up before relying on the join, and
    note that Spark then locks the shuffle partition count into the checkpoint.
  - **Watermark caveats (Item 8):** they become correctness requirements, because a late record
    means a missing fused event.
  - **Latency (Item 6) and throughput (Item 1):** they share one design problem (trigger interval,
    write path), best decided with the join's own latency needs.
  - **Build paths (Item 10):** `fusion-engine`'s Compose entry is wrong and needs fixing when its
    Dockerfile is written.

---

## 6. Open Items and Pending Reviews

The ten items are logged in full in `docs/milestones/milestone5/open_items_m5.md`, which remains the
authoritative record.

| # | Item | Status | Deferred to |
|---|---|---|---|
| 1 | Streaming throughput below bar | Open — root cause fixed, gap measured per phase | M6 → M10 |
| 2 | No checkpointing (risk: skipped events on restart) | Open — impact corrected | Before M6 join |
| 3 | Dead `EVENTS_PER_SECOND` config | Open | With Item 7 |
| 4 | `sensor_id` doc / DB-type mismatch | **Resolved** (M5W20T8) | — |
| 5 | Sustained multi-hour load | **Resolved at default rate**; high load re-scoped | After Item 1/7 progress |
| 6 | Latency p95 5.7 s vs. ≤500 ms | Open — structural | M6 → M10 |
| 7 | Generator capacity + shared CPU | Open | Next bar-level benchmark / M10 |
| 8 | Watermark operational caveats | Open — operating rule documented | M6 |
| 9 | Spark exceeds the stop grace period (exit 137) | Open — no data impact | With Item 2 |
| 10 | Latent Compose issues for M6–M9 | Open — no M5 impact | M6 onwards |

M4 Items 1, 3 and 4 remain open in `open_items_m4.md` (deferred to M6/M7).

**Additionally pending, or resolved during package assembly:**

- **Review comments on Beyza's M5W20T10: resolved.** Five statements conflicted with the committed
  record: the write path, two swapped commit references, the API table, the "All M5 Open Items
  Closed" heading, and an unsupported memory claim.
  - Beyza corrected all five in `m5_database_contribution.md` (`1dcd0ea`, 27 September).
  - The same memory/load wording in `docs/data/m5w20t9_soak_test.md` was aligned in the follow-up
    commit to this note.
- **Ömer's M5W20T11 has not been started.** A likely cause is identified from the committed history
  (Section 2); confirmation is his.
- **No Beyza/Ömer sign-off on this document exists yet.** It is presented for their review, and both
  reviews are **PENDING**.

### Update, 1 October 2026 (M6W21T4)

The table and bullets above are the 27 September snapshot. Changes since then:

**M5 review outcome.** The review with Emrah was held on Wednesday 30 September 2026.
- **Result:** Emrah accepted the M5 package as presented. No changes were requested.
- **Bar gaps:** throughput (1,417 events/sec like-for-like, ~3,650 capacity, against ≥10,000) and
  latency (p95 5.7 s against ≤500 ms) are to be reported as measured, with their named causes, and
  fixed by M10. The prototype bar is unchanged.
- **New requests or deadlines:** none.
- **Record:** no written minutes were taken. This entry records the outcome as recalled by the
  project lead on 1 October 2026.

**Open items changed since 27 September:**
- **Items 2 and 9 are resolved** (M6W21T2): checkpointing on a named volume, `stop_grace_period`,
  and a shutdown-handler fix. The live restart test published 904 sensor events while Spark was
  down and staged exactly 904 after the restart. Details are in
  `docs/milestones/milestone6/m6w21t2_checkpoint_restart_test.md`.
- **Item 8's operating rule was corrected** (M6W21T3): a restarted `spark-processor` now restores
  its saved watermark, so the README "Restart order" section also deletes the `alice_throughput`
  checkpoint.

**Teammate items:**
- **Ömer's M5W20T11 is committed** (`bb7ec81`, 1 October,
  `docs/milestones/milestone5/m5w20t11_build_verification.md`). A clean `--no-cache` rebuild fixed
  the build, and the full `m5-and-above` stack came up healthy on his machine. His note calls the
  cause consistent with stale local Docker build state. The `git status` and `git log -1` check
  that the plan asked for is not recorded, so the cause is likely, not proven.
- **Sign-offs on this note** are not updated here and remain shown as **PENDING** above.

---

## 7. Package Status

Core M5 deliverables are complete and committed to `develop`, each traced to a commit above:
- live producers on four topics and the four-query Spark consumer;
- watermark/window logic;
- schema-versioning continuity;
- the throughput benchmark, root-cause fix and capacity test;
- the validation report and the open items log.

The validation report confirms the pipeline is functionally correct, loss-free and schema-compliant
across all four streams.

**Recommendation: M5 is ready for review, but not closed on the prototype bar.**
- **Throughput** is missed, at 1,417 events/sec like-for-like and ~3,650 capacity. It is
  root-caused, improved 2.4×/6.1×, and measured per phase.
- **Latency** is missed, at p95 5.7 s, for a structural reason.
- Neither should be represented as closed in any downstream summary.
- All M5 success criteria are met. The M5 review was held on 30 September 2026 and the package
  was accepted as presented (Section 6).

M6 kickoff is not blocked, provided checkpointing (Item 2) is planned into the join design from the
start.

*End of `m5_package_cover_note.md` — pending Beyza/Ömer review of this note.*