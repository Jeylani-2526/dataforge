# DataForge — ALICE Run 1 Full Schema Conformance Audit

**Task ID:** M3W11T2
**Owner:** Abdalla
**Milestone:** M3 · Week 11
**Status:** PASS (with one new finding flagged — see Section 4)
**GitHub Path:** `/docs/data/alice_conformance_audit_full.md`
**Audited file:** `AliESDs.root` (`esdTree`, run 139465)
**Validated against:** `alice_event_schema_v1.avsc`, `alice_discrepancy_resolution.md`
**Method:** PyROOT direct leaf-level access (`TLeaf.GetValue`) against the raw `Double32_t` branches (`Tracks.fP[5]`, `Tracks.fAlpha`) that `uproot` cannot decode without ALICE-specific streamer info — see Section 5 for tooling notes.

---

> **Why this document exists**
> M3W9T2 was a spot-check only, against a sample of records. This task extends that check to **every entry in the acquired file** — all 287 raw entries and all 68 filtered `PHYSICS_EVENT` records — confirming the three locked decisions in `alice_discrepancy_resolution.md` hold universally, and re-confirming whether the per-event aggregate fields are directly present or require derivation, across the full set.

---

## 1. Full-File Confirmation of Locked Decisions

| Decision (from `alice_discrepancy_resolution.md`) | Spot-check scope (M3W9T2) | Full-audit scope (this task) | Result |
|---|---|---|---|
| **Decision 1** — `run_number` = 139465 | Sample only | All 287 entries | **Confirmed** — a single unique run number (139465) across every entry in the file, no exceptions |
| **Decision 2** — 287 raw entries | N/A (file-level fact) | `tree.GetEntries()` on full file | **Confirmed** — 287 |
| **Decision 3** — `PHYSICS_EVENT` filtering | Sample only | All 287 entries, full `fEventType` breakdown | **Confirmed** — `fEventType` breakdown: `2` (unknown/other) = 210 (73.17%), `7` (`PHYSICS_EVENT`) = 68 (23.69%), `8` (unknown/other) = 9 (3.14%). 23.69% matches the ~23.7% / ~68-event figure in the discrepancy resolution exactly. |

All three locked decisions hold consistently across the entire acquired file — none are contradicted or need re-opening.

---

## 2. Per-Event Aggregate Fields — Direct Presence vs. Derivation (Full Set)

Re-confirming the open question carried since M2 Week 5 and re-flagged at M3W9T2: **no branch in the raw ROOT file directly stores `net_momentum_x/y/z`, `max_energy_gev`, or `total_energy_gev`.** A branch-name scan for aggregate-like fields across all 28 top-level branches returned zero matches. These fields **require derivation** from per-track arrays, exactly as `alice_event_schema_v1.avsc`'s doc strings specify — this holds for the full file, not just the sample.

`track_count` is likewise **not** a direct field — it is derived as `len(Tracks.fFlags)` per event, as documented.

**Derivation was executed against all 68 `PHYSICS_EVENT` entries, across every reconstructed track in each event (thousands of tracks per event in several cases):**

| Field | Derivation formula | Result across full set |
|---|---|---|
| `track_count` | `len(Tracks.fFlags)` per event | Computed cleanly for all 68 events; range 0–11,600 tracks/event |
| `net_momentum_x` | `sum(|1/fP[4]| · cos(fAlpha + arcsin(fP[2])))` | Computed cleanly for all 68 events, 0 domain errors |
| `net_momentum_y` | `sum(|1/fP[4]| · sin(fAlpha + arcsin(fP[2])))` | Computed cleanly for all 68 events, 0 domain errors |
| `net_momentum_z` | `sum(|1/fP[4]| · fP[3])` | Computed cleanly for all 68 events, 0 domain errors |
| `max_energy_gev` | `max(sqrt(px² + py² + pz² + 0.13957²))` per track | Computed cleanly for all 68 events |
| `total_energy_gev` | `sum(sqrt(px² + py² + pz² + 0.13957²))` per track | Computed cleanly for all 68 events |

**Data-quality checks on the derived values (full set):**
- 0 domain errors (`arcsin` out-of-range, division by zero on `fP[4]=0`) across every track in every physics event.
- 0 `NaN`/`Inf` values in any derived field across all 68 events.
- `timestamp_s` (`AliESDHeader.fTimeStamp`) values are well-formed and non-decreasing across entry order.
- `event_num_in_file` (`AliESDHeader.fEventNumberInFile`) values are unique across all 68 physics events — no duplicates, consistent with the sub-second timestamp derivation `alice_event_schema_v1.avsc` documents.

**Conclusion:** The schema's documented derivation formulas execute correctly and cleanly across the full filtered dataset — this was not previously confirmed at scale, only against a sample. No schema change is required; the aggregates remain derived fields, not direct ones, consistent with the current schema design.

---

## 3. Field-by-Field Conformance Summary

| `alice_event_schema_v1.avsc` field | Source | Full-set conformance |
|---|---|---|
| `event_id` | System-assigned (no ROOT source) | N/A — not a ROOT-derived field, nothing to audit |
| `run_number` | `AliESDRun.fRunNumber` | PASS — 139465 for all 287 entries |
| `timestamp_ms` | `AliESDHeader.fTimeStamp` × 1000 + software sub-second component | PASS — `fTimeStamp` present, well-formed, and monotonic for all 68 physics events; sub-second component is software-assigned per design, not independently ROOT-verifiable |
| `track_count` | `len(Tracks.fFlags)` | PASS — derives cleanly for all 68 events |
| `net_momentum_x/y/z` | Derived from `fP`/`fAlpha` (Section 2) | PASS — derives cleanly for all 68 events |
| `max_energy_gev` / `total_energy_gev` | Derived from `fP`/`fAlpha` (Section 2) | PASS — derives cleanly for all 68 events |
| `schema_version` | Hardcoded `"1.0"` | N/A — not a ROOT-derived field |

---

## 4. New Finding — Zero-Track `PHYSICS_EVENT` Entries (Flagged, Not Silently Resolved)

**24 of the 68 `PHYSICS_EVENT`-tagged entries (35.3%) have `track_count = 0`** — i.e., zero reconstructed charged tracks despite being tagged as genuine physics collision events rather than run-control/calibration markers.

This was not surfaced by the M3W9T2 spot-check (which worked from a smaller sample and would need to have specifically hit one of these 24 entries to notice it). For these 24 entries, all derived aggregate fields (`net_momentum_x/y/z`, `max_energy_gev`, `total_energy_gev`) correctly compute to `0.0` via the empty-sum/empty-max convention — which matches the schema's own `default: 0.0` on these fields, so nothing crashes or produces invalid data. But it's worth surfacing explicitly rather than letting it pass quietly, per this task's own instruction to flag new discrepancies immediately:

- This is plausibly a legitimate physics outcome (a peripheral or low-multiplicity collision can genuinely reconstruct zero charged tracks), not necessarily a data-quality defect.
- However, it means roughly a third of the already-small 68-event usable sample carries **no momentum/energy signal at all** — worth factoring into M7 planning, since these records contribute nothing distinguishing to any model trained on `net_momentum`/`energy` features, on top of the already-small ~68-event ALICE sample size flagged in `alice_discrepancy_resolution.md`.
- **No action taken unilaterally.** This is presented as a decision point for the team, consistent with how the three original discrepancies were handled — not something for Abdalla to resolve alone.

**Recommendation (not a decision):** note this explicitly in the Data Quality Validation Report (M3W11T3) and flag it to Emrah in the Week 11 update as a data-characteristic observation about the ALICE sample, not a defect requiring rework.

---

## 5. Tooling Note — `uproot` Limitation Confirmed, PyROOT Used Instead

As documented from prior sessions, `uproot` cannot resolve the streamer info for the `Double32_t`-compressed `Tracks.fP[5]` and `Tracks.fAlpha` branches in this file (raises `KeyError` on streamer lookup) — confirmed again here. `Tracks.fFlags` (a simple integer type) reads fine via `uproot`.

For this audit, PyROOT was used instead, with direct `TLeaf.GetValue()` access to the raw branches — this bypasses the need for AliRoot/AliPhysics class dictionaries (which are not installed in this environment and are not needed for raw leaf-level reads) while still correctly decompressing the `Double32_t` values. This is a viable, repeatable alternative to a full AliRoot/AliPhysics installation for this specific derivation.

---

## 6. Verdict

**PASS**, all three locked discrepancy-resolution decisions and all schema-documented derivation formulas hold across the complete acquired file — not just the Week 9 spot-check sample. One new, non-blocking finding (zero-track `PHYSICS_EVENT` entries) is flagged for team awareness and Week 11 reporting rather than resolved unilaterally.

*End of `alice_conformance_audit_full.md`*
