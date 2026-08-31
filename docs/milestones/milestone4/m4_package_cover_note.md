# DataForge — Milestone 4 Package Cover Note

**Milestone:** M4 — Data Adaptation Layer
**Task:** M3W16T8
**Owner:** Abdullah
**Date:** 29 August 2026
**Package status:** Draft — throughput gap open, pending final team sign-off

---


---

## 1. What M4 Covers

Milestone 4 builds the Data Adaptation Layer: reading validated ALICE and sensor records
out of TimescaleDB staging tables, serializing them to Avro against the three locked M2
schemas, converting to Parquet, enforcing schema-versioning on every record, and
promoting validated staging rows into the `events` production hypertable that M9's
dashboard API reads from.

---

## 2. What's Complete — Per Person

### Abdullah

| Artifact | Task | Path | Status |
|---|---|---|---|
| ALICE staging load verification + loader bug fixes | M4W13T3 | `scripts/ingestion/staging_ingestion_script.py`, `infrastructure/scripts/init-db.sql` | Complete (`a1da2ee`) |
| Open items log established (Items 1–3) | M4W13T7 | `docs/milestones/milestone4/open_items_m4.md` | Complete (`723d54c`) |
| Avro adaptation job — JDBC read, Avro write, schema-versioning enforcement | M4W14T2/T3 | `services/adaptation-layer/avro_adaptation_job.py`, `schema_versioning.py` | Complete (`df715ec`) |
| Local Docker execution environment for adaptation-layer | M4W14T5 | `infrastructure/docker/adaptation-layer.Dockerfile`, `docker-compose.yml` | Complete (`7731771`) |
| Fused-event stub scope decision formalized (Item 4) | M4W15T2 | `docs/milestones/milestone4/open_items_m4.md` | Complete (`c9f5922`) |
| Full-volume pipeline run (68 ALICE + 150,000 sensor) | M4W15T4 | `docs/data/full_volume_run_m4w15t4.md` | Complete — data integrity passed; throughput gap surfaced as Item 5 (`e28cbae`) |
| Throughput root-cause investigation + cache fix; second port-mismatch fix + missing `addPyFile()` fix in `avro_adaptation_job.py` | M4W16T3 | `docs/milestones/milestone4/throughput_root_cause_m4w16t3.md`, `services/adaptation-layer/{avro_adaptation_job.py,parquet_writer.py}` | Complete — investigation and fixes committed; **throughput gap not closed** (`daa82cc`) |
| Format-conversion test results backfilled | M4W16T4 | `docs/schemas/format_conversion_test_results_m4w15t3.md` | Complete (`daa82cc`) |
| M4 validation report | M4W16T7 | `docs/milestones/milestone4/m4_validation_report.md` | Complete (`daa82cc`) |
| M4 package cover note | M3W16T8 | `docs/milestones/milestone4/m4_package_cover_note.md` *(this document)* | This task's commit |

### Beyza

| Artifact | Task | Path | Status |
|---|---|---|---|
| `PHYSICS_EVENT` filter (`fEventType=7`) — 287 → 68 ALICE records | M4W13T2 | `scripts/ingestion/extract_alice_fields.py`, `data/synthetic/alice.jsonl` | Complete (`cdb5179`, `a2eb689`) — resolves M3 cover note's Open Item 4 |
| Staging schema fixes — `label`/`anomaly_type` columns, content-based stream-type detection | M4W13T3 | `infrastructure/scripts/init-db.sql`, `scripts/ingestion/staging_ingestion_script.py` | Complete (`afab8da`, `d250ff8`) |
| Restored PyROOT-derived momentum/energy values in ALICE records | M4W13T6 | `data/synthetic/alice.jsonl` | Complete (`8ea6f3d`) — resolves M3 cover note's Open Item 3 (placeholder `0.0` values) |
| Staging → production promotion design and contract | M4W14T6/T7 | `docs/database/promotion_contract.md`, `docs/database/staging_to_production_promotion_design.md` | Complete (`4eaf13c`, `250ebec`) |
| Staging → production promotion script and validation | M4W15T5/T6 | `scripts/ingestion/promote_to_production.py` | Complete (`62a7345`) |
| Port fix: `promote_to_production.py` 5432 → 5433 | M4W16T1 | `scripts/ingestion/promote_to_production.py` | Complete (`4dcf172`) |
| Promotion validation note + T1 sensor dataset path-mismatch resolution | M4W16T2 | `docs/database/promotion_validation_note.md`, `docs/database/t1_sensor_dataset_path_mismatch.md` | Complete (`47f0907`, `eb89d58`) |
| M4 database contribution section (promotion results, ERD/API implications) | M4W16T6 | `docs/milestones/milestone4/m4_database_contribution.md` | Complete, incl. correction to 150,068 total (`ef0755a`, `5dd2038`) |

### Ömer

| Artifact | Task | Path | Status |
|---|---|---|---|
| M5 pre-work scoping note: telemetry `device_id` diversity | M4W13T8 | `docs/data/m5_prework_device_diversity_scope.md` | Complete (`a5e39e5`) — scoping only; implementation deferred to M5 per Open Item 2 |
| Parquet writer — Avro → Parquet conversion, per-sensor-type split | M4W14T4 | `services/adaptation-layer/parquet_writer.py` | Complete (`6337c35`); later modified by Abdullah (M4W16T3 cache fix) without changing Ömer's original directory-layout design |
| Sensor staging dataset trimmed/aligned to 150,000-record spec | M4W15T1 | `data/synthetic/*` staging inputs | Complete (`ab25174`, `524f976`) |

No commit was found for Ömer against `docs/milestones/milestone4/` validation, cover-note, or close-out tasks — none are claimed here on his behalf.

---

## 3. Throughput — OPEN, Not Resolved

**This is not closed.** Per the M4 validation report (`m4_validation_report.md`, M4W16T7):

| Metric | Bar | Result | Status |
|---|---|---|---|
| Throughput | ≥ 10,000 events/sec | **1,135.05 events/sec** (post-fix, full-volume run) | **FAIL** |
| Latency (p95) | ≤ 500 ms | 0.1334 ms | PASS |
| Data loss | ≤ 1% | 0.0% | PASS |

Two throughput figures exist in the record and should not be conflated:

- **1,665.56 events/sec** — the original M4W15T4 baseline, measured *before* this week's
  port fix, `addPyFile()` fix, or cache fix existed.
- **1,135.05–1,142.5 events/sec** — the M4W16T3 measurement *with* those fixes applied.
  The cache fix alone is a real, measured ~45% improvement over an uncached control run
  in the same environment (1,142.5 vs. 788.11 events/sec) — but the `addPyFile()` fix
  needed to make the pipeline runnable at all from arbitrary working directories adds
  overhead the original baseline never paid, so the *net* current figure is lower than
  the original baseline, not higher. Neither number is close to the ≥10,000 bar.

**Root cause** (per `throughput_root_cause_m4w16t3.md`): architectural, not a
partition-count problem. `parquet_writer.py` materializes the full sensor record set as
a Python list via `fastavro` before handing it to `spark.createDataFrame()` — an
inherently serial, driver-side step regardless of downstream partitioning, and one shown
to be fragile at this row count during this week's diagnostics.

**Disposition:** carried forward as `open_items_m4.md` Item 5, unresolved. Per that
document's own framing, M5's Kafka + Structured Streaming benchmark is the roadmap's
actual throughput deliverable and will supersede this M4 batch-mode number — this figure
is a baseline for that comparison, not a final verdict.

---

## 4. The Two Port Bugs

Both were instances of the same TimescaleDB host-port (5433) vs. container-port (5432)
mismatch, found and fixed independently in different files:

| File | Fixed by | Task | Commit |
|---|---|---|---|
| `scripts/ingestion/promote_to_production.py` (host script) | Beyza | M4W16T1 | `4dcf172` |
| `services/adaptation-layer/avro_adaptation_job.py` (`DB_PORT` default, host execution) | Abdullah | M4W16T3 | `daa82cc` |

Both fixes were independently verified live (containers up, real `psql`/TCP checks both
directions) in M3W16T5 — see
`docs/milestones/milestone4/docker_port_verification_m3w16t5.md`. No remaining port
mismatch was found in that verification. One unrelated gap surfaced there: the `events`
table is absent from the current local Docker volume because that volume predates the
table being added to `init-db.sql` and Postgres only runs init scripts against a fresh
volume — flagged in that document, not fixed, not a port issue.

---

## 5. What Feeds M5

- **The adaptation layer is functionally complete and schema-compliant**: Avro
  serialization, Parquet conversion, and schema-versioning enforcement all pass, per the
  M4 validation report. M5's streaming pipeline can build on this format layer directly.
- **Staging → production promotion is built, tested, and live**: 150,068 records
  promoted (68 ALICE + 150,000 sensor), 0 failed, 0 skipped, per Beyza's M4 database
  contribution section. The `events` hypertable is the confirmed single production
  source for M9's dashboard API (`GET /api/v1/events/live`, `GET /api/v1/alerts/recent`).
- **The ALICE momentum/energy placeholder gap flagged at M3 close is resolved**: PyROOT
  derivation is now wired into the pipeline (M4W13T1, M4W13T6); `alice.jsonl` carries
  real derived values, not `0.0` placeholders.
- **Throughput is the one deliverable M5 must actually solve**, not just re-measure.
  M5's own roadmap-scheduled Kafka + Structured Streaming benchmark is where the
  ≥10,000 events/sec bar is meant to be met — M4's 1,135.05 events/sec batch-mode number
  is the carried-forward baseline, and the root cause (driver-side Python-list
  materialization in `parquet_writer.py`) is a specific, named pattern for M5 to design
  around from the outset rather than repeat.
- **Telemetry device diversity remains deferred to M5** (Ömer's M4W13T8 scoping note),
  to be addressed alongside M5's own repeat-generation mode.

---

## 6. Open Items (carried forward, none resolved here)

All five items below are logged in full in `docs/milestones/milestone4/open_items_m4.md`
and are restated here only for package visibility — that document remains the
authoritative record.

| # | Item | Status | Deferred to |
|---|---|---|---|
| 1 | 24 of 68 ALICE records have `track_count = 0` | Open — keep all 68 through M4 | M7 |
| 2 | Telemetry `device_id` single-value across all 50,000 records | Open — no M4 change | M5 |
| 3 | Net-momentum outlier, event `c1cc2e42…` | Open — logged as observation | M7 |
| 4 | `write_fused_events()` stub — out of scope for M4, confirmed | Open — stub remains | Module 6 build |
| 5 | Full-volume throughput below prototype bar (1,135.05 vs. ≥10,000 events/sec) | **Open — investigated, root-caused, not closed** | M4W16T3 done; M5 streaming benchmark is the actual deliverable |

**Additionally pending, not yet reflected as resolved anywhere:**

- **This cover note itself** was claimed as delivered in commit `daa82cc`'s message
  (M4W16T8) but no file was ever committed for it until this task. Flagging the
  discrepancy rather than silently treating the earlier claim as if it had happened.
- **No Beyza/Ömer sign-off on this document exists yet** — the commit that will land
  this cover note is this task's own; per the task brief, this draft is presented for
  review before that commit, and both teammates' review remains **PENDING**.

---

## 7. Package Status

Core M4 deliverables — adaptation layer, schema-versioning enforcement, format
conversion, staging-to-production promotion, and both port-bug fixes — are complete and
committed to `develop`, each traced to a specific commit above. The validation report
(M4W16T7) confirms correctness and data integrity pass cleanly.

**Recommendation: M4 is NOT ready to close on throughput.** The ≥10,000 events/sec bar
is missed by roughly 9x on the current, fix-applied measurement (1,135.05 events/sec),
root-caused but not resolved. Per the open items log's own framing, this is expected to
carry forward rather than block M5 kickoff, since M5's Kafka + Structured Streaming
benchmark is the roadmap's actual throughput deliverable — but it should not be
represented as closed in any downstream summary. All other M4 success criteria are met.

*End of `m4_package_cover_note.md` — draft, pending Abdullah's sign-off on wording and Beyza/Ömer review.*
