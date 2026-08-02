# DataForge — Data Quality Validation Report — Outline



---

> **Why this document exists**
> This scopes the structure and metrics of the final Data Quality Validation Report ahead of receiving Omer's raw check results (M3W11T8, due Thursday 23 July). Drafting the skeleton now — rather than waiting for the raw results to arrive — means Week 12 finalization is a fill-in-and-write-up exercise, not a from-scratch design exercise under a tighter deadline.

---

## Planned Report Structure

### 1. Executive Summary
- One-paragraph verdict: does the M3 data (ALICE + synthetic) meet the standard needed to proceed to M4?
- Pending Week 12: written last, once all four sections below are complete.

### 2. Completeness
**Purpose:** Confirm no unexpected nulls, missing records, or truncated streams across the full corpus (ALICE + radar/LIDAR/telemetry).

**Inputs required:**
- Omer's raw completeness check results (M3W11T8) — *pending*.

**Planned content:**
- Per-stream record counts vs. expected volume (50,000/stream for synthetic; 287 raw / 68 filtered for ALICE).
- Null-rate table per field, per stream — flag any field with unexpected nulls (e.g., a RADAR-only field appearing null on a RADAR record, vs. expected null on a LIDAR/TELEMETRY record where that field doesn't apply).
- Cross-reference against the M3W11T1 finding that all 50,000 committed TELEMETRY records share a single `device_id` — note this here as a completeness *characteristic*, not a defect, with a pointer to the fuller discussion in the labeled training data validation (M3W11T1).

### 3. Schema Pass Rate
**Purpose:** Confirm `validate_schema.py` passes cleanly against sample batches from every stream (ALICE + all three synthetic).

**Inputs required:**
- Omer's `validate_schema.py` run results across all streams (M3W11T8) — *pending*.

**Planned content:**
- Pass/fail rate per stream, with any failures itemized by field and record.
- Explicit note confirming the `label`/`anomaly_type` fields are correctly treated as generator-output metadata, not Avro schema fields (per `anomaly_injection_design.md` §4) — schema pass rate should not be measuring these two fields against `sensor_schema_v1.avsc`, since they were deliberately never added to it.

### 4. Label Distribution
**Purpose:** Report class balance and per-type anomaly distribution across all three synthetic streams, and document the `sensor_freeze` → `timestamp_stall` substitution as a reasoned, disclosed scope decision.

**Inputs required:**
- Already available — this section can be substantially pre-filled from M3W11T1 (`labeled_training_data_validation_scale.md`), completed this week.

**Planned content:**
- Class balance table (3% ± 0.3pp target, realized 2.96%–2.97% across all three streams — confirmed in M3W11T1).
- Per-type breakdown across all nine locked anomaly types.
- **`sensor_freeze` → `timestamp_stall` substitution**, stated plainly:
  - What was originally specified (`sensor_freeze`, cross-record consecutive-value check).
  - Why it couldn't be implemented (stateless per-record generator architecture; also not currently learnable by Module 7's per-record Isolation Forest without a derived temporal feature).
  - What replaced it (`timestamp_stall`, derivable from the record's own `sequence_number` via the generator's deterministic timestamp formula — no cross-record state needed).
  - Disposition of `sensor_freeze`: **deferred to M4/M7 planning, not cancelled**, pending the temporal-feature work it depends on.
  - This is reported as a documented design decision, not smoothed over — consistent with the M3W10T3 failure and its resolution.

### 5. ALICE Conformance Summary
**Purpose:** Summarize the full ALICE Run 1 schema conformance audit (M3W11T2).

**Inputs required:**
- Already available — this section can be substantially pre-filled from M3W11T2 (`alice_conformance_audit_full.md`), completed this week.

**Planned content:**
- Confirmation that all three locked discrepancy-resolution decisions (run 139465, 287 raw / 68 filtered `PHYSICS_EVENT` entries, acquisition-stage filtering) hold across the full file.
- Confirmation that all per-event aggregate fields (`net_momentum_x/y/z`, `max_energy_gev`, `total_energy_gev`, `track_count`) derive cleanly across the entire 68-event filtered set, with 0 domain errors and 0 NaN/Inf values.
- **New finding to carry forward:** 24 of 68 `PHYSICS_EVENT` entries (35.3%) have `track_count = 0` — flagged in M3W11T2 as a data-characteristic observation, not a defect, but worth noting here since it affects how much of the already-small ALICE sample carries usable momentum/energy signal for M7.

### 6. Overall Verdict & Recommendation
- Pending Week 12: synthesizes Sections 2–5 into a single go/no-go recommendation for proceeding to M4 (Data Adaptation Layer).
- Any open items or team decisions still outstanding at that point (e.g., the zero-track-event finding, the `sensor_freeze` deferral) are carried forward explicitly into the M3 package cover note, not resolved silently in this report.

---

## What's Blocking Full Report Completion

| Section | Status | Blocking on |
|---|---|---|
| 2. Completeness | Not started | Omer's M3W11T8 raw results (due Thu 23 July) |
| 3. Schema Pass Rate | Not started | Omer's M3W11T8 raw results (due Thu 23 July) |
| 4. Label Distribution | **Substantially drafted** | Nothing — ready to finalize from M3W11T1 output |
| 5. ALICE Conformance Summary | **Substantially drafted** | Nothing — ready to finalize from M3W11T2 output |
| 1. Executive Summary / 6. Verdict | Not started (depends on all above) | Sections 2–3 |

Two of four content sections are effectively ready ahead of schedule since M3W11T1 and M3W11T2 were completed earlier this week. The report's critical path now runs entirely through Omer's M3W11T8 output.


