# DataForge — ALICE Staging Verification (M4W13T3)

**Task ID:** M4W13T3
**Owners:** Beyza (staging load) · Abdulla (PyROOT derivation, joint verification)
**Milestone:** M4 · Week 13
**Status:** PASS — one observation flagged, not blocking
**GitHub Path:** `/docs/data/alice_staging_verification_m4w13.md`
**Verifies:** `data/synthetic/alice.jsonl` (regenerated M4W13T1) loaded into `raw_alice_events_staging` via `scripts/ingestion/staging_ingestion_script.py`

---

> **Why this document exists**
> M4W13T1 wired real PyROOT-derived momentum/energy values into `extract_alice_fields.py`, replacing the five fields previously hardcoded to `0.0`. M4W13T2 (Beyza) filtered ALICE extraction to `fEventType=7` only. This task confirms the two fixes **compose correctly** once loaded into the actual staging table — not just that each works in isolation on the flat file.

---

## 1. Batch Load Summary

| Check | Result |
|---|---|
| Batch ID | `b3729a06-7a36-44c7-8390-7cc3c02bee5e` |
| Rows loaded (`SELECT COUNT(*) ... WHERE batch_id = ...`) | **68** |
| Rows failed | **0** |
| Validation rejections | None — no reject log lines, 0 failed count confirms this directly against the table, not just the script's own log |

## 2. Field-Level Verification

**Non-zero-track events** — sampled the highest-multiplicity rows to confirm derived fields are real, non-placeholder values:

| `event_id` | `track_count` | `net_momentum_x` | `net_momentum_y` | `net_momentum_z` | `max_energy_gev` | `total_energy_gev` |
|---|---|---|---|---|---|---|
| `a0cb6979…` | 11,600 | -12.33 | 11.98 | 497.09 | 264.72 | 8245.30 |
| `c1cc2e42…` | 10,706 | 719.68 | -1509.29 | -58.57 | 1404.86 | 9550.69 |
| `55029a32…` | 9,624 | -104.63 | 8.22 | -13.43 | 34.03 | 6504.77 |

**Zero-track-count events** — 24 rows with `track_count = 0`. Verified via explicit `IS NULL` filter across all five derived fields (not sampling): **0 nulls** — every one of the 24 rows correctly stores literal `0.0`, consistent with the schema's `default: 0.0` convention and the M3W11T2 audit's empty-sum/empty-max derivation. Matches the file-level count from M4W13T1's independent verification exactly.

## 3. Observation — Net-Momentum Outlier (Flagged, Not Resolved)

Event `c1cc2e42…` (10,706 tracks) shows a net-momentum magnitude of √(719.68² + 1509.29² + 58.57²) ≈ **1673 GeV**, against a total energy of 9550.69 GeV — **≈17.5%** of total energy carried as net (unbalanced) momentum.

For comparison, the other two high-multiplicity samples above are far more balanced:

- `a0cb6979…` (11,600 tracks): ≈6% net-to-total ratio
- `55029a32…` (9,624 tracks): ≈1.6% net-to-total ratio

In a symmetric Pb-Pb collision, net momentum is expected to trend toward zero as track multiplicity grows (more tracks → more cancellation) — consistent with the two comparison events, but not with this one. This is plausibly a genuine physics signal (a hard-scattering or jet-dominated event can carry real directional momentum imbalance even at high multiplicity), not necessarily a derivation defect — the same reasoning the M3W11T2 audit applied to the zero-track events.

**No action taken unilaterally.** Flagged here for team awareness and available as a candidate ML feature/anomaly-detection input (M7), consistent with how prior ALICE data-characteristic observations have been handled — not something to resolve in this task.

## 4. Infrastructure Findings — Fixed Under This Task

Getting the load to run at all surfaced four issues outside this task's original scope, in files not owned by this task's author. Per team decision, all four are committed now under M4W13T3 rather than held for separate review, with Beyza and Omer notified after the fact:

| # | File | Issue | Fix |
|---|---|---|---|
| 1 | `scripts/ingestion/staging_ingestion_script.py` (Beyza, M3W10T5) | `DB_URL` hardcoded to `postgres:dataforge@.../dataforge_db`, not matching Docker Compose's actual defaults (`dataforge:dataforge_dev@.../dataforge`) | Corrected to match Compose config |
| 2 | `scripts/ingestion/staging_ingestion_script.py` | `ingest_directory()` globs only `*.ndjson`, but every file in `data/synthetic/` is `.jsonl` — **meaning no prior run of this script could ever have loaded anything, for any stream type, until this fix** | Glob extended to match both `.ndjson` and `.jsonl` |
| 3 | `scripts/ingestion/staging_ingestion_script.py` | `ingest_directory()` has no stream-type filtering — pointing it at a mixed directory (e.g. `data/synthetic/` containing RADAR/LIDAR/TELEMETRY files alongside ALICE) would validate non-ALICE records as ALICE records | **Resolved 2026-08-11** — Beyza landed content-based stream-type detection (`detect_stream_type()`) in commit `d250ff8`, routing each file to the correct staging table by peeking at its first record. See root_to_avro_mapping.md checkpoint note, M4W14T8, for verification. |
| 4 | `infrastructure/scripts/init-db.sql` | File did not exist — `raw_alice_events_staging` only ever existed as DDL prose in `docs/database/staging_table_design.md`, never as runnable SQL, which crash-looped the TimescaleDB container on first attempt | Created from the documented DDL |

**Note on process:** items 1, 2, and 4 touch files owned by Beyza and Omer respectively, and item 4 is new schema-defining SQL that would normally require sign-off before landing, per the project's schema-change convention. By explicit team decision this week, all four are committed now to unblock verification, with Beyza and Omer notified after the commit rather than before — logged here for transparency rather than presented as a clean, pre-agreed change.

Item 3 (stream-type filtering gap) is **resolved** as of commit `d250ff8` (11 Aug 2026) — content-based detection now routes each file to the correct table before validation.

## 5. Verdict

**PASS.** The M4W13T1 PyROOT derivation and M4W13T2 `fEventType=7` filter compose correctly end-to-end: 68/68 records load with 0 failures, non-zero-track events carry real derived momentum/energy values, zero-track events correctly carry `0.0` (not null) across all five fields. One data-characteristic observation (event `c1cc2e42…`'s net-momentum ratio) is flagged for team awareness, not resolved. Item 3 (stream-type filtering) was resolved 11 Aug 2026 (commit d250ff8), after this verification was originally written.


