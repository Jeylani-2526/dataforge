# DataForge — M4 Open Items Log

**Originating Task ID:** M4W13T7
**Owner:** Abdullah
**Milestone:** M4 · Week 13 (originated) — amended M4 · Week 15, Week 16
**Status:** Open — six items tracked; five open, one resolved (Item 6)
**GitHub Path:** `/docs/milestones/milestone4/open_items_m4.md`

**Amendment history:**
- M4W13T7 — Document created; Items 1–3 logged (zero-track-count ALICE events, telemetry `device_id` scope, net-momentum outlier).
- M4W15T2 — Item 4 added: `write_fused_events()` stub scope, formally closing the carry-in flagged (but never committed) at Week 14's M4W14T8 checkpoint.
- M4W15T4 — Item 5 added: full-volume run throughput (1,665.56 events/sec) below the locked prototype bar (≥10,000 events/sec), surfaced by the M4W15T4 full-volume pipeline run.
- M3W16T5 — Item 6 added and resolved same-day: missing `events` production table in the local dev Docker volume, found during Docker execution environment & port consistency verification.

---

> **Why this document exists**
> Items surfaced during M4 work that require a decision at a later milestone rather than now — either because they need input the team doesn't have yet (Prof. Uysal's physics interpretation), because the right fix depends on work not yet started (M5's per-device grouping, M6's fusion join), or because a provisional team decision was made verbally/in a code comment but never formally committed. Consistent with how prior ALICE discrepancies were handled (`alice_discrepancy_resolution.md`), each is logged explicitly here rather than resolved unilaterally or left undocumented.

---

## Item 1 — Zero-Track-Count ALICE Events (24 of 68)

**Finding:** 24 of the 68 `PHYSICS_EVENT`-tagged ALICE records have `track_count = 0` — zero reconstructed charged tracks despite being tagged as genuine physics collision events. First surfaced in the M3W11T2 full conformance audit; reconfirmed unchanged in the M4W13T1/T3 PyROOT re-derivation and staging load.

**Interim decision (this week):** **Keep all 68 records through M4** — do not filter out the zero-track events. No change from the position established at M3W11T2.

**Deferred to:** M7 (Anomaly Detection), for an evidence-based filter-vs-keep comparison.

**Rationale for deferring:** A zero-track `PHYSICS_EVENT` is plausibly a legitimate low-multiplicity or peripheral collision outcome, not necessarily a data-quality defect — but roughly a third of the already-small 68-event ALICE sample carries no momentum/energy signal at all, which matters for any model trained on those features. Resolving this now, before M7's modeling work defines what "useful signal" actually means for anomaly detection, risks discarding data that turns out to matter or keeping data that turns out to be pure noise. Prof. Uysal's physics interpretation (coordinated via Emrah) is also still pending and directly bears on whether these are genuine physics outcomes.

**What would trigger resolution:** Prof. Uysal's interpretation, and/or M7's initial model results showing whether these 24 records help, hurt, or are neutral to anomaly-detection performance.

**Action items:**
- [ ] Abdulla: continue tracking Prof. Uysal's physics interpretation status via Emrah's weekly channel
- [ ] M7 owner: run filter-vs-keep comparison before finalizing the training dataset

---

## Item 2 — Telemetry `device_id` Scope (Single `SENSOR-UNIT-01`)

**Finding:** All 50,000 synthetic TELEMETRY records carry the same `device_id` value, `SENSOR-UNIT-01` — no per-device variation across the generated corpus.

**Interim decision (this week):** **Confirmed as M5 pre-work** — no change from the position established when this was first flagged. Not addressed in M4.

**Deferred to:** M5, since Module 5's `data_loss_pct` computation is the first real consumer of per-device grouping — there's no functional reason to fix generator-level device diversity before the module that would actually use it exists.

**Rationale for deferring:** Fixing this in M4 would front-load generator changes for a feature (per-device data-loss tracking) that has no consumer yet in the current pipeline. M5 is also where the generator's continuous/repeat generation mode is being planned, so device-diversity and multi-run generation are naturally addressed together rather than as two separate generator changes in two different milestones.

**What would trigger resolution:** Start of M5 planning work on Module 5 (`data_loss_pct`) and the generator's repeat-generation mode.

**Action items:**
- [ ] Omer: scope multi-device generation alongside repeat-generation mode at M5 kickoff

---

## Item 3 — Net-Momentum Outlier, Event `c1cc2e42…` (New This Week)

**Finding:** During M4W13T3 staging verification, event `c1cc2e42…` (10,706 tracks) showed a net-momentum-to-total-energy ratio of ≈17.5% — 3–10x higher than comparably high-multiplicity events in the same 68-event set (≈6% and ≈1.6% for the next two largest events). In a symmetric Pb-Pb collision, net momentum is expected to trend toward zero as multiplicity grows; this event doesn't follow that pattern.

**Interim decision (this week):** **Logged as an observation, not investigated further.** Flagged for team awareness in the M4W13T3 verification note (`docs/data/alice_staging_verification_m4w13.md`); no filtering, correction, or exclusion applied.

**Deferred to:** M7, as a candidate feature/input for anomaly detection rather than a data-quality problem to fix.

**Rationale for deferring:** This is plausibly a genuine physics signal — a hard-scattering or jet-dominated event can carry real directional momentum imbalance even at high track multiplicity — not necessarily a derivation defect. Given the M7 pipeline's purpose is anomaly detection, an event that already looks anomalous on a physics basis is more useful as a labeled or reference case for that work than as something to normalize away now.

**What would trigger resolution:** M7's anomaly-detection model design work, where this event can be evaluated as a candidate feature/label case rather than resolved in isolation.

**Action items:**
- [ ] M7 owner: consider `c1cc2e42…` as a reference case when defining anomaly-detection features/labels

---

## Item 4 — Fused-Event Stub Scope Sign-Off (`write_fused_events()`)

**Finding:** `write_fused_events()` in `avro_adaptation_job.py` (design note 4, lines 43–52; function stub, lines 212–219) is an intentional stub that raises `NotImplementedError`. `fused_event_schema_v1.avsc` requires a matched ALICE+sensor pair produced by a Module 6 stream-stream join, and `services/fusion/` is still an empty scaffold (`.gitkeep` only) — there is no join logic in the repo to build the fusion output against. The stub was written to fail loudly rather than silently produce empty or fabricated fused records, and its in-code comment flags the scope question for "M4W14T8 (Tuesday checkpoint)."

**Interim decision (this week):** **Confirmed out of scope for M4.** The scope question raised in the code comment was discussed and provisionally agreed at Week 14's M4W14T8 field-mapping checkpoint, but the decision was never written into a committed document — it existed only as the code comment referenced above. This entry formally closes that gap.

**Deferred to:** Whichever week Module 6 stream-stream join logic is actually built (not yet scheduled as of M4W15).

**Rationale for deferring:** Implementing `write_fused_events()` now would mean building fusion output against a join stage that doesn't exist yet in `services/fusion/`. The stub's current behavior — raising `NotImplementedError` instead of writing empty or synthetic fused records — is the correct M4 posture: it keeps the schema contract documented and enforced without fabricating data the pipeline isn't yet equipped to produce honestly.

**What would trigger resolution:** Start of Module 6 planning/build work, once `services/fusion/`'s stream-stream join logic exists for `write_fused_events()` to call.

**Action items:**
- [ ] Module 6 owner: implement `write_fused_events()` against the stream-stream join once Module 6 is built, replacing the stub
- [ ] Abdullah: reference this entry (not the code comment) as the authoritative scope record in future M4/M5 documents

---

## Item 5 — Full-Volume Run: Throughput Below Prototype Bar

**Finding:** M4W15T4's full-volume pipeline run (68 ALICE + 150,000 sensor records, using M4W15T1's trimmed staging data) measured **1,665.56 events/sec** throughput — the locked prototype bar requires **≥10,000 events/sec**, roughly a 6x gap. Data loss (0.0%) and p95 latency (0.127ms, measured as per-record round-trip processing time — see `docs/data/full_volume_run_m4w15t4.md` for the full methodology note) both passed their respective bars with wide margin; throughput is the only metric outside spec.

Tracing the run's log timestamps stage by stage, the majority of wall-clock time (~40 of ~90 seconds total) was spent converting the 150,000 sensor records to Parquet, and Spark logged repeated `TaskSetManager: Stage X contains a task of very large size` warnings during that conversion — an indication the sensor batch was processed as a single large task rather than split across multiple parallel partitions, which would defeat much of Spark's intended parallelism for a batch this size. `parquet_writer.py`'s sensor conversion (M4W14T4, unmodified by M4W15T3/T4) also reads the full 150,000-record set from Avro once per sensor subtype (RADAR/LIDAR/TELEMETRY) — three full passes over the same input rather than one filtered split — which likely compounds the single-partition issue.

**Interim decision (this week):** **Logged as a known gap, not investigated or fixed this week.** The full-volume run itself is complete and its data-integrity results (0% loss, schema_version propagation confirmed) stand; only the throughput figure misses the bar. Per the Week 15 plan's own "Looking Ahead" note, a bar miss surfaced by T4 is explicitly meant to become a Week 16 open item rather than something resolved or smoothed over under this week's time pressure.

**Deferred to:** M4 Week 16 (Finalization & M4 Package) at the earliest — root-causing and fixing this is real diagnostic/engineering work (confirming actual Spark partition count during the run, and evaluating whether `parquet_writer.py`'s three-pass sensor-type split can become a single partitioned write), not a same-day fix.

**Rationale for deferring:** The likely causes (single-partition processing, redundant three-pass sensor conversion) are specific enough to investigate properly rather than guess-and-patch under this week's deadline. This is also explicitly a batch-pipeline measurement — M5 (Streaming Pipeline) is where the project's own roadmap schedules the real "throughput benchmarks against prototype bar" deliverable using Kafka + Structured Streaming, so M4's batch-mode number, while informative, is not necessarily the final word on whether the prototype bar is reachable.

**What would trigger resolution:** M4 Week 16 root-cause investigation (partition count during the M4W15T4 run, evaluating a single-pass sensor Parquet write), and/or M5's streaming throughput benchmarks superseding this batch-mode measurement.

**Action items:**
- [ ] Abdullah / Week 16 owner: confirm actual Spark partition count used during the M4W15T4 run (`df.rdd.getNumPartitions()` on the sensor DataFrame) to verify the single-task hypothesis
- [ ] Week 16 owner: evaluate splitting `parquet_writer.py`'s sensor conversion into one partitioned write instead of three full-dataset passes
- [ ] M5 owner: treat this M4 batch-mode figure as a baseline, not a final throughput verdict — M5's streaming benchmarks are the roadmap's actual throughput deliverable

---

## Item 6 — Missing `events` Production Table in Local Dev Volume (New This Week, Resolved)

**Finding:** During M3W16T5's Docker execution environment & port consistency
verification, `docker exec dataforge-timescaledb psql -U dataforge -d dataforge -c '\dt'`
showed only `raw_alice_events_staging` and `raw_sensor_events_staging` — the `events`
production hypertable, defined in `infrastructure/scripts/init-db.sql` and required by
`promote_to_production.py`'s promotion writes, was absent from the live database.

**Root cause:** `docker volume inspect dataforgerepo_timescaledb-data` shows the named
volume was created **2026-08-11T08:31:27Z**. The `events` table definition was not added
to `infrastructure/scripts/init-db.sql` until commit `62a7345` (**2026-08-20**,
M4W15T5-T6, Beyza) — nine days after the volume's first initialization. Postgres's
official image runs `docker-entrypoint-initdb.d/*.sql` only against a fresh, empty data
directory; on every subsequent `up` it is skipped entirely regardless of what
`init-db.sql` currently contains. This volume was therefore never running the `events`
statement, independent of anything port-related.

**Interim decision (this week): Resolved, not deferred.** Unlike Items 1–5, this is a
mechanical schema-drift gap with a known-safe fix, not something requiring team input —
so it was corrected directly rather than logged and carried forward.

**Resolution applied:** the exact `events`-table block from
`infrastructure/scripts/init-db.sql` (lines 63–89: `CREATE TABLE IF NOT EXISTS events`,
`SELECT create_hypertable(...)`, both `CREATE INDEX IF NOT EXISTS` statements) was run
directly against the live database via `docker exec -i dataforge-timescaledb psql`. All
statements are idempotent (`IF NOT EXISTS` / `if_not_exists => TRUE`), so this is safe to
re-run and does not risk the existing staging data. Full commands, real output, and
schema/hypertable verification are recorded in
`docs/milestones/milestone4/docker_port_verification_m3w16t5.md` §5.

**Verification:** `\d events` confirms all 17 columns, the `(event_id, timestamp_ms)`
primary key, and both indexes match `init-db.sql`'s definition exactly.
`timescaledb_information.hypertables` confirms `hypertable_name=events`,
`primary_dimension=timestamp_ms`, `num_chunks=0` (expected — no data has been written to
`events` yet; promotion has not been re-run since this fix). Staging row counts were
re-checked before and after: `raw_alice_events_staging` = 68, `raw_sensor_events_staging`
= 150,000, unchanged — **no staging data was dropped or modified.**

**What would trigger further action:** none expected — this is closed. Flagging only
that `promote_to_production.py` has still not been executed against this now-complete
schema as of this entry; a first real promotion run (writing rows into `events`, not just
confirming the table exists) remains a natural follow-up but is not blocking anything and
is not logged here as an open item.

**Action items:**
- [x] Abdullah: root-cause the missing `events` table (volume-vs-init-script timing, confirmed via `docker volume inspect` and `git log`)
- [x] Abdullah: apply `init-db.sql`'s `events` DDL against the live volume, idempotently
- [x] Abdullah: verify schema, hypertable status, and staging-data integrity post-fix
- [ ] Team: run a real `promote_to_production.py` pass against the now-complete schema (not blocking, no owner/date assigned yet)

---

## Summary

| Item | Status | Deferred to | Trigger for resolution |
|---|---|---|---|
| 24 zero-track-count ALICE events | Open, keep all 68 through M4 | M7 | Prof. Uysal's interpretation + M7 model results |
| Telemetry `device_id` scope (single value) | Open, no M4 change | M5 | Module 5 (`data_loss_pct`) + generator repeat-mode planning |
| Net-momentum outlier, event `c1cc2e42…` | Open, logged as observation | M7 | M7 anomaly-detection feature/label design |
| Fused-event stub scope (`write_fused_events()`) | Open, confirmed out of scope for M4 | Module 6 (stream-stream join build) | Start of Module 6 planning/build work |
| Full-volume run throughput below bar (1,665.56 vs. ≥10,000 events/sec) | Open, logged as known gap | M4 Week 16 / M5 | Week 16 root-cause investigation; M5 streaming benchmarks |
| Missing `events` production table in local dev volume | **Resolved** (M3W16T5) | — | N/A — fixed directly, see Item 6 |

**Five of six items remain open by design**, each tied to a specific downstream milestone where the team will have the information or infrastructure needed to decide properly, rather than being resolved prematurely or left untracked. **Item 6 is the one exception**, closed directly this week because it was a mechanical schema-drift bug with a known-safe, idempotent fix rather than a question requiring team input.