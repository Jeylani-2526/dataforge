# DataForge — Milestone 6 Package Cover Note

**Milestone:** M6 — Data Fusion
**Task:** M6W26T6
**Owner:** Abdalla
**Date:** 5 November 2026
**Package status:** Closed-with-open-items, per the Week 26–28 catch-up plan.
- Lightweight package by decision: this note, `open_items_m6.md`, milestone tags and the README
  update. No separate validation report and no formal review.
- M6 ran Weeks 21–26 rather than 21–24, after an 18-day pause (15 October – 2 November).
- **The fusion engine works:** live stream-stream join, replay-safe writes, conformance PASS,
  ≈100% match rate, zero duplicates, zero watermark drops.
- **Latency is missed** (structural, carried). Fourteen open items, each with an owner, target
  and trigger.
- Pending at assembly: Omer's M6W26T7 and M6W26T8, and the `init-db.sql` restore on `develop`
  (open item 9).

---

## 1. What M6 Covers

Module 6 fuses the ALICE stream with the three sensor streams:
- a stream-stream interval join on Kafka timestamps, ±500 ms window, nearest sensor event per
  ALICE event (`fusion_join_design_note.md`);
- `fused_events` and `fusion_status` hypertables with soft references (Option C);
- every fused batch through the same `schema_versioning.enforce()` as M4 and M5;
- checkpointed, replay-safe writes;
- the synchronization validation the milestone is graded on.

---

## 2. What's Complete — Per Person

### Abdalla

| Artifact | Task | Path | Status |
|---|---|---|---|
| Fusion join design note; Spark checkpointing and shutdown fix; restart-order rule | M6W21T1–T4 | `docs/milestones/milestone6/fusion_join_design_note.md`, `services/streaming/spark/` | Complete (`c92eecd`) |
| Docs aligned with soft-reference FKs, replay unique index | — | `docs/` | Complete (`57ee7f5`) |
| Fusion engine, fused writer, Compose wiring, join spike | M6W22T1–T4 | `services/fusion/` | Complete (`176e51c`, `08f155f`) |
| Live fused run, injection mode, watermark boundary and restart safety, injection config | M6W23T1–T4, T9 | `docs/milestones/milestone6/m6w23t*.md` | Complete (`34b0b7d`) |
| Alignment persistence + `alignment_report.py` | M6W26T3 | `services/fusion/` | Complete (`70a0100`) |
| Synchronization validation run | M6W26T4 | `docs/milestones/milestone6/m6w23t2_sync_validation.md` | Complete (`386523e`); final since M6W26T1 passed |
| Feature-access decision | M6W26T5 | `docs/milestones/milestone6/m6w26t5_feature_access_decision.md` | Signed (`d04801e`) |
| Open items log + this note | M6W26T6 | `docs/milestones/milestone6/` | This task's commit |

### Beyza

| Artifact | Task | Path | Status |
|---|---|---|---|
| `fused_events` + `fusion_status` DDL | M6W21T6 | `infrastructure/scripts/init-db.sql` | Complete (`71b6d2a`) |
| FK-target decision — soft reference | M6W21T7 | `docs/database/fused_events_fk_decision.md` | Complete (`b981d57`) |
| Staging review + cleanup plan; cleanup executed | M6W21T8, M6W22T7 | `docs/database/m6w21t8_staging_review.md` | Complete (`a62348f`, `5269e81`) |
| Heartbeat writer | M6W22T5 | `services/fusion/heartbeat_writer.py` | Complete (`b6a2496`); three contract mismatches — open item 6 |
| `summary_5min` aggregate + Fusion Monitor mapping | M6W23T7 | `docs/database/m6w23t7_fusion_monitor_source_mapping.md` | Complete (`e7d429a`); aggregate currently lost from `develop` — open item 9 |
| Fusion soak test | M6W23T8 | `docs/database/m6w23t8_fusion_soak_test.md` | PASS (`6a7c688`) |
| Fused-record conformance — script rewritten and executed | M6W22T6, M6W26T1 | `docs/database/m6w22t6_fused_conformance.md` | PASS (`766b6b7`) |
| Fused-reference resolution | M6W26T2 | `docs/database/m6w26t2_fused_reference_resolution.md` | Complete (`0513fe1`) |

### Omer

| Artifact | Task | Path | Status |
|---|---|---|---|
| Fusion Dockerfile + `schema_versioning.py` mount move to `/app/` | M6W22T8 | `infrastructure/docker/fusion.Dockerfile` | Complete (`9e045b2`) |
| Cross-machine build verification | M6W22T8 → M6W26T7 | `m6w26t7_cross_machine_build.md` | **Pending** — blocked by open item 9 |
| M6 milestone tags + README update | M6W26T8 | README; tags `M6-W26-*` | **Pending** |

M6W23T3 and M6W23T9, planned for Omer, were carried out by the lead (open item 13).

---

## 3. Results — As Measured

### Synchronization (M6W26T4, 5 November, 600 s window, injection off)

| Measure | Result | Against target |
|---|---|---|
| Match rate | ≈100% (1,256 / 1,250, ±6 at window edges) | — |
| Duplicate fused pairs | 0 | Pass |
| Rows dropped by watermark | 0 | Pass |
| Sensor events used twice | 0 | Pass |
| Alignment error `abs_dt_ms` | p50 50 ms, p95 96 ms, max 105 ms | **±1 ms missed** |
| Fused-path latency | p95 19.3 s | Not the ≤500 ms bar's quantity |

**Alignment cause:** the distribution is uniform on 0–100 ms — nearest-neighbour spacing of
sensor events arriving ~every 200 ms, not clock error. ±1 ms is a clock-synchronization target;
`abs_dt_ms` measures the gap between two independent streams' events. Values are Kafka message
timestamps, not the sensors' own recorded times.

**Latency cause:** append-mode output waits for the ~13 s effective watermark (open item 1),
plus trigger and batch lag. Structural; open item 5.

### Prototype bar

| Metric | Bar | M6 position |
|---|---|---|
| Data loss | ≤1% | **Pass** — `data_loss_pct` 0.0 on every fused row measured; 0 watermark drops |
| Latency, p95 | ≤500 ms | **Missed** — 19.3 s fused path, structural (open item 5) |
| Throughput | ≥10,000 events/sec | Not re-measured in M6; M5's 1,417 events/sec stands (`open_items_m5.md` Item 1) |
| AUC / FPR | ≥0.85 / ≤5% | M7 |

### Integrity

| Check | Result |
|---|---|
| Fused-record conformance (M6W26T1) | PASS — 14 checks, 1,000-row sample of 34,560 |
| Fused-reference resolution (M6W26T2) | 100% on both references, with feature values |
| Restart safety (M6W23T1, M6W23T4) | PASS with and without injected lateness |
| Soak (M6W23T8) | PASS — no memory growth, no crashes |

---

## 4. Corrections to Earlier Figures and Statements

Stated plainly, per the project's rule of verifying against committed files:

| Earlier statement | Actual |
|---|---|
| M6W22T7 cleanup would remove ~3.5M staging rows (M6 document, Week 22 plan) | **450,000** rows truncated (`5269e81`) |
| Option A alignment logging "never built" (Week 26–28 plan, sync doc) | Built at `34b0b7d`; the document went stale against its own commit |
| `open_items_m6.md` written 2 November (Week 26–28 plan) | Not written until this task |
| `check_fused_conformance.py` only needed executing | It checked ALICE columns, not fused ones, and could not pass; rewritten in M6W26T1 |
| Fused rows "carry an M3 label" (M6W26T2 report) | Every streamed record carries a placeholder `label = 0`; no positive class |
| `--profile m6-and-above` brings up the fusion stack (Week 23 plan) | Profiles do not cascade; it starts fusion alone |

---

## 5. Decisions Taken During M6 Closure

| Decision | Record |
|---|---|
| M7 features joined back to staging, no schema bump | M6W26T5 |
| M7 trains and evaluates on the M3 per-stream corpus | M6W26T5 |
| Per-stream models + common 0–1 risk score; cross-sensor detection deferred to M10 | M6W26T5, open item 14 |
| ALICE validates the architecture; it does not take part in detection | M6W26T5 |
| Weekly reports to Emrah discontinued from 5 November; milestone-close reports continue | Week 26–28 plan, revised 5 November |

---

## 6. What Closes M6

- [ ] `init-db.sql` restored on `develop` (open item 9)
- [ ] M6W26T7 cross-machine build recorded, including any failure
- [ ] Tags `M6-W26-abdalla`, `M6-W26-beyza`, `M6-W26-omer` at the closing commit
- [ ] README: M6 Completed, M7 In Progress
- [x] Synchronization measurements recorded (M6W26T4)
- [x] Conformance gate passed (M6W26T1)
- [x] Feature-access decision signed (M6W26T5)
- [x] Open items log committed with owners, targets and triggers (this task)

Target close: Sunday 8 November 2026.
