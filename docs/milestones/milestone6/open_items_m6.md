# DataForge — M6 Open Items Log

**Originating Task ID:** M6W26T6 (planned as M6W24T1, never written)
**Owner:** Abdalla
**Milestone:** M6 · Week 26
**Status:** Open — fourteen items. Item 10 closed for M7 by M6W26T5. Items 1–9 and 11–14 open.
**GitHub Path:** `/docs/milestones/milestone6/open_items_m6.md`

**Amendment history:**
- M6W26T6 (5 November 2026) — Document created. Items 1–7 and 13 carried from Week 23
  (`m6w23t1_live_run_verification.md`, `m6w23t2_sync_validation.md`). Items 8–12 and 14
  surfaced in Week 26 (M6W26T1–T5).

---

> **Why this document exists**
> Same convention as `open_items_m4.md` and `open_items_m5.md`: every item logged with an
> honest scope, a named owner, a target milestone and a trigger for resolution. M6 closes as
> **closed-with-open-items** under the Week 26–28 plan; this log is what makes that honest.
>
> **A correction.** The Week 26–28 plan states this file was written on 2 November with
> thirteen items. It was not. Item numbers the plan cites (1, 4, 10, 13) are kept here so the
> plan's references still resolve.

---

## Item 1 — Effective Watermark 12–13 s Against a Configured 5 s

**Finding (M6W23T4):** With `WATERMARK_DELAY_SECONDS=5`, the watermark in force measured
12.4–13.5 s behind the newest event time. Two contributors: `multipleWatermarkPolicy=min`,
and batch processing lag (Item 3).

**Why it matters:** anyone reading the config concludes data later than 5 s is dropped. In
practice the threshold is ~2.5 times that, and it moves with load. For defense and industrial
sensors, "how late is too late" is a specification question.

**Owner:** Abdalla · **Target:** M8 decision, M10 implementation
**Trigger:** decide whether an adaptive lateness threshold is acceptable, and whether
`multipleWatermarkPolicy` stays at `min`. Changing it reintroduces the M5 Item 8 caveat it fixed.

## Item 2 — Watermark Drop Boundary Not Narrowed

**Finding (M6W23T4):** 9 s shift accepted, 30 s shift dropped (160 rows). The transition
between them was not located.

**Owner:** Abdalla · **Target:** with Item 1
**Trigger:** only meaningful once Item 1's decision is taken.

## Item 3 — Batch Commit 8–10 s Against a 5 s Trigger

**Finding (M6W23T4):** `commitTimeMs` 8,033 and 9,876 ms against a 5,000 ms trigger. Feeds
both Item 1 and Item 5.

**Owner:** Abdalla · **Target:** M10
**Trigger:** the next benchmark aimed at the ≥10,000 events/sec bar. Same levers as
`open_items_m5.md` Item 1.

## Item 4 — Silent Mis-Pairing (Unquantified)

**Finding (M6W23T4):** a sensor record shifted past ±500 ms but inside the effective watermark
survives and fuses with an *older* ALICE event. Fused counts and drop counts do not reveal it.

**Correction (M6W26T3/T4):** the plan assigned detection to comparing `abs_dt_ms` with the
join window. That cannot work: the join only admits pairs within ±500 ms, so a wrong pair still
has a small `abs_dt_ms`. The M6W26T4 run had injection off, so no drift was introduced — but
that is not a measurement.

**Why it matters more now:** a mis-paired row scored in M7 gets the wrong sensor's features.

**Owner:** Abdalla · **Target:** M8
**Trigger:** compare the ALICE event time with the sensor's **payload** `timestamp_ms` (from
staging) rather than its Kafka timestamp, under the M6W23T3 injection mode.

## Item 5 — Fused-Path Latency Above the ≤500 ms Bar

**Measured (M6W26T4):** p50 16.6 s, **p95 19.3 s**, max 21.8 s, on 1,256 rows.

**Cause:** structural. A fused row is emitted only after the watermark passes (~13 s, Item 1),
plus up to 5 s trigger and batch lag. The design note already recorded that an exact
nearest-match join cannot meet ≤500 ms: it must wait at least 500 ms to know no closer event
will arrive.

**This is not the bar's quantity.** The bar describes processing latency; this figure is
event-time-to-write including a deliberate wait.

**Owner:** Abdalla · **Target:** M10
**Trigger:** the M10 framing decision (design note Section 8 options): report the floor, measure
fusion's own processing overhead separately, or adopt a non-deterministic "first match" rule.

## Item 6 — Heartbeat Contract and Semantics — Three Mismatches

| # | Mismatch | Source |
|---|---|---|
| 1 | Status vocabulary `ok/degraded/critical`; contract says `online/degraded/offline` | M6W22T5 |
| 2 | Only `alice` and `sensor` rows; contract says latest row per sensor | M6W22T5 |
| 3 | `status=critical`, `quality=0` on a run with 0.0% data loss — almost certainly reacting to Item 5's latency | M6W23T1 |

**Owner:** Beyza · **Target:** M9
**Trigger:** Fusion Monitor endpoint work. Mismatch 3 is pulled earlier if the dashboard slips —
a health endpoint that always reads critical is useless to M7 operators meanwhile.

## Item 7 — Alignment Side Table for Permanent Monitoring

**Status:** rejected for M6 — `fused_event_schema_v1` is locked and the deliverable was a
measured figure, now delivered by M6W26T3/T4 (file-based samples + `alignment_report.py`).

**Owner:** Beyza · **Target:** M9
**Trigger:** the Fusion Monitor page, which is where it would be consumed.

## Item 8 — Cross-Machine Build Not Verified

**Finding:** M6W22T8 moved `schema_versioning.py` from `/app/src/` to `/app/`. The `m6-and-above`
build has run on the lead's machine only. This is the exact gap that cost M5 a carry-in week
(M5W20T11).

**Owner:** Omer · **Target:** M6W26T7 (this week)
**Trigger:** `m6w26t7_cross_machine_build.md` committed with the result, including any failure.
**Blocked by Item 9** — a fresh database on a second machine will fail fusion writes until
Item 9 is on `develop`.

## Item 9 — `init-db.sql` Regression on `develop`

**Finding (5 November):** merge `4d90452` kept an older `init-db.sql`. Its message says
"keep upstream init-db.sql (Abdalla's version)", but the content kept is the older one. Lost:

| Object | Effect on a fresh database |
|---|---|
| `uq_fused_events_replay` | Every fused write fails — `ON CONFLICT (timestamp_ms, alice_event_id)` has no matching index |
| `set_integer_now_func` | The 90-day retention policy fails on the integer time column |
| `summary_5min` continuous aggregate | M6W23T7's aggregate is gone; `/summary` has no source |

Existing databases are unaffected — `init-db.sql` only runs on an empty volume.

**Status:** restore prepared (`git checkout eb1b8e8 -- infrastructure/scripts/init-db.sql`).
**Not on `develop` as of PR #58** (`1effffe`).

**Owner:** Abdalla · **Target:** M6W26 — before Item 8 runs
**Trigger:** `develop` carries all three objects, verified by `grep` and by a fresh-volume start.

## Item 10 — Feature Access and Ground Truth for M7 — Closed for M7

**Finding (plan, M6W26T2):** `fused_event_schema_v1` carries no measurement; features are
reachable only through soft references, after a 450,000-row staging truncation.

**Measured (M6W26T2):** 100% of 34,560 fused rows resolve to staging on both references, with
feature values. But every streamed sensor record carries `label = 0`, `anomaly_type = NULL` —
a placeholder hardcoded in `spark_consumer.py`. The fused stream has no positive class.

**Resolved by M6W26T5 (signed 5 November):**
- features joined back to `raw_sensor_events_staging` at scoring time, no schema bump;
- training and evaluation on the M3 per-stream corpus, as `labeled_training_data_spec.md`
  already specified.

**Residual — staging retention rule:** nothing in the database stops a cleanup from orphaning
fused rows. **Owner:** Beyza · **Target:** M7W27T4.
**Trigger:** the rule "no cleanup deletes staging rows referenced by `fused_events`" is written
into the staging documentation.

## Item 11 — Fusion Checkpoint Does Not Survive a Pause Longer Than Seven Days

**Finding (M6W26T4, first run):** after the 21-day pause, fusion crashed with
`OffsetOutOfRangeException` on `sensor-lidar-0`. Kafka's default 7-day retention had deleted
the offsets the checkpoint held; `docker-compose.yml` does not override it. Recovery needed a
checkpoint reset, which silently abandons unread messages.

**Compounding finding:** the crash exited with **code 0**. `run()` catches the query exception
and exits normally, so `docker ps` shows `Exited (0)` — indistinguishable from a clean stop.

`failOnDataLoss=false` was deliberately not used: it turns a visible failure into silent loss on
a project that measures data loss.

**Owner:** Abdalla · **Target:** M8
**Trigger:** (a) set an explicit Kafka retention matched to the longest expected pause, or
document the reset as the recovery procedure; (b) a terminated query exits non-zero.

## Item 12 — Compose and Environment Operability

Four small issues, one owner:

1. **Profiles do not cascade** (M6W23T9). `--profile m6-and-above` alone starts fusion with no
   producers and no spark-processor — a silently idle stack. Plans and README must give the
   stacked form.
2. **Empty `.env` values swallow trailing comments** (M6W23T9). Fixed in `.env.example`; any
   older local `.env` still carries the bug, including `SPARK_STARTING_TIMESTAMP_MS`.
3. **spark-processor must run whenever fusion runs** (M6W26T5 condition A2). Otherwise fused rows
   reference sensor events that never reach staging. Not stated anywhere a user would see it.
4. **Two documents cited but never committed:** `m6w21t2_checkpoint_restart_test.md` (cited by
   `open_items_m5.md`) and the M6W22T7 cleanup record exists only as an edit to
   `m6w21t8_staging_review.md`.

**Owner:** Omer · **Target:** M8
**Trigger:** README "Running the stack" section covers 1–3; item 4 is committed or the
references are corrected.

## Item 13 — Omer's Capacity

**Finding:** four commits in 60 days, last on 8 October (`9e045b2`). M6W23T3 and M6W23T9 were
absorbed by the lead.

**Owner:** Abdalla · **Target:** reviewed weekly
**Trigger:** two consecutive delivered weeks, or a formal redistribution of the 20 percent —
stated in the M7-closing advisor report, since weekly reports to Emrah are discontinued
(5 November).

## Item 14 — Detection Is Per-Sensor, Not Cross-Sensor

**Finding (M6W26T5):** each fused row holds one ALICE event and one sensor event, paired by time
only. Anomalies are injected into each stream independently. Nothing in the data is visible only
by combining sources, so M7 delivers per-stream detection combined into one 0–1 risk score
(late fusion), not cross-sensor detection.

ALICE's role is recorded as architecture validation, not detection.

**Owner:** Abdalla · **Target:** M10
**Trigger:** Emrah's answer on whether the advisor expects cross-sensor detection for the
project's scientific claim — raised directly, not via a weekly report. If yes, M10 needs a
shared-scene generator, linked anomalies, a join on target or location, and a fused schema
change. Labels in the live stream (M6W26T5 option B2) travel with it.

---

## Descope Triggers Carried From the Week 26–28 Plan

| Candidate | Trigger date | If missed |
|---|---|---|
| M7W28T2 PyTorch deep model | Sunday 15 November — not started | Deferred to M10 |
| M7W28T3 Live inference integration | Wednesday 18 November — not working | Deferred to M8, with the SHAP work |

## Inherited Items

- `open_items_m4.md` Items 1 and 3 (zero-track ALICE events, net-momentum outlier) were deferred
  to M7 as candidate ALICE features. M6W26T5 excludes ALICE from detection, so neither is an M7
  input any more. Proposed: close both as superseded by M6W26T5 in the next amendment to
  `open_items_m4.md`.
- `open_items_m4.md` Item 4 (fused-event stub) was closed in practice by M6W22T2's real
  `write_fused_events()`.

---

## Summary

| Item | Status | Owner | Target | Trigger |
|---|---|---|---|---|
| 1 Effective watermark | Open | Abdalla | M8 → M10 | Lateness specification decision |
| 2 Drop boundary | Open | Abdalla | With 1 | Item 1 decided |
| 3 Batch commit lag | Open | Abdalla | M10 | Next throughput benchmark |
| 4 Silent mis-pairing | Open, unquantified | Abdalla | M8 | Payload-timestamp comparison under injection |
| 5 Fused-path latency | Open, structural | Abdalla | M10 | M10 latency framing |
| 6 Heartbeat mismatches | Open | Beyza | M9 | Fusion Monitor work |
| 7 Alignment side table | Deferred | Beyza | M9 | Fusion Monitor page |
| 8 Cross-machine build | Open | Omer | M6W26T7 | Result committed |
| 9 `init-db.sql` regression | **Open — blocking** | Abdalla | M6W26 | Restore on `develop` |
| 10 Feature access | **Closed for M7** | — | — | M6W26T5 |
| 10 residual: staging retention | Open | Beyza | M7W27T4 | Rule documented |
| 11 Checkpoint vs retention | Open | Abdalla | M8 | Retention set; non-zero exit |
| 12 Compose operability | Open | Omer | M8 | README section + references fixed |
| 13 Omer's capacity | Open | Abdalla | Weekly | Two delivered weeks or redistribution |
| 14 Cross-sensor detection | Open | Abdalla | M10 | Emrah's answer |
