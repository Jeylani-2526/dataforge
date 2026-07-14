# DataForge — ALICE Discrepancy Resolution — Decision Record


---

> **Why this document exists**
> The M3W9T2 spot-check (`alice_conformance_spotcheck.md`) surfaced three discrepancies between the ALICE Run 1 sample Omer acquired from the CERN Open Data Portal and the values documented in `alice_event_schema_v1.avsc` and related M1/M2 documentation. This is a team decision, not a unilateral fix, per the note carried forward from Week 9. All three are resolved below, with rationale and required follow-up actions.

---

## Decision 1 — Run Number (139465 vs. 139038)

**Finding:** The acquired file's run number, read directly from `AliESDRun.fRunNumber`, is **139465**. Existing documentation (schema doc string, M1 exploration notes) states **139038**.

**Decision:** Update documentation to match the acquired sample. **139465 is authoritative going forward.**

**Rationale:** The acquired file is the actual dataset the pipeline is built and tested against. Re-acquiring against 139038 would discard a verified, already-integrated sample for no functional gain — the M1 scoping intent was "an LHC10h Pb-Pb run suitable for prototyping," not a specific run number with unique significance to the prototype's goals. Correcting the documentation is faster, lower-risk, and keeps Omer's acquisition (M3W9T5) valid rather than triggering a re-download and re-verification cycle.

**Schema impact:** The `run_number` field's `doc` annotation in `alice_event_schema_v1.avsc` hardcodes the value 139038. This is a **documentation-only change** — no type, structure, or field-order change. Per `schema_evolution_policy.md` Section 2, doc-only changes do not bump `schema_version`. Per Section 5, the full post-lock change process still applies:

| Step | Action | Status |
|---|---|---|
| 1. Raise change request | Documented in this record, raised at Tuesday 14 July team meeting | Done |
| 2. Abdullah sign-off | Approved — doc-only, backward-compatible, no serialization impact | Done |
| 3. Version bump | None required (doc-only per Section 2) | N/A |
| 4. Run validation | `validate_schema.py` re-run against `alice_event_schema_v1.avsc` test record | Pending — see Action Items |
| 5. Migration log entry | Appended to `schema_evolution_policy.md` | Done (this session) |
| 6. Commit and tag | Commit schema file + policy doc together | Pending — see Action Items |
| 7. Notify Emrah | Not required — internal doc-only change, not visible in API/dashboard | N/A (mentioned in Week 10 update for transparency only) |

**Action items:**
- [ ] Abdullah: update `run_number` doc string in `alice_event_schema_v1.avsc` (see accompanying file edit)
- [ ] Abdullah: update `alice_run1_field_inventory.md` and M1 `cern_exploration_notes.md` references to 139038 → 139465
- [ ] Omer: re-run `validate_schema.py` against the updated schema before commit
- [ ] Abdullah: commit schema file + `schema_evolution_policy.md` migration log together, tag `schema-doc-fix-alice-run-number`

---

## Decision 2 — Entry Count (287 vs. 228)

**Finding:** The acquired file contains **287** entries in the `esdTree`. Documentation states **228**.

**Decision:** **287 is authoritative going forward.**

**Rationale:** Same logic as Decision 1 — the acquired, verified file is ground truth for this prototype. 228 was a documentation estimate from earlier scoping (M1) that was never re-confirmed against the actual downloaded file. There is no evidence 228 reflects a different, deliberately-targeted dataset; treating it as a stale placeholder is consistent with how Decision 1 was resolved.

**Schema impact:** None — entry count is not an Avro field, it's descriptive metadata about the sample file. No version bump, no migration log entry needed.

**Downstream consequence:** Combined with Decision 3 (physics-event filtering), the *effective* dataset size for downstream ALICE-dependent work is **287 × 23.7% ≈ 68 genuine physics events** — not 287, and not 228. This must be stated explicitly anywhere entry counts are referenced (M1 notes, field inventory, Week 11 conformance audit scope) so nobody downstream assumes 287 usable events.

**Action items:**
- [ ] Abdullah: correct entry-count references in `alice_run1_field_inventory.md` and M1 exploration notes to 287 (raw) / ~68 (post-filter, genuine physics events)

---

## Decision 3 — Physics-Event Filtering (23.7% PHYSICS_EVENT)

**Finding:** Only 23.7% of the 287 entries have `AliESDHeader.fEventType == 7` (`PHYSICS_EVENT`). The remaining ~76.3% are `END_OF_RUN` or `CALIBRATION_EVENT` markers — run-control artifacts, not collision data. This explains the ~84.7% zero-track-count rate flagged in the spot-check.

**Decision:** **Filter to `PHYSICS_EVENT` only.** Filtering happens **at acquisition** — non-physics events are dropped before any data enters the staging layer or downstream pipeline.

**Rationale:** Filtering at the earliest possible stage (acquisition) means:
- Beyza's staging tables (`raw_alice_events_staging`) never see run-control noise, so her Week 10 load test (M3W10T6) validates against clean data from the start rather than needing a later filter added retroactively.
- No schema change is required — the Avro schema has no `event_type` field (it was never a modeled field; per-event aggregates like `track_count` are what the schema captures). Filtering is a pipeline/acquisition-script concern, not a schema concern.
- Avoids duplicating filter logic across multiple stages (acquisition, staging, M4 adaptation) — a single, early filter point is easiest to audit and least likely to silently diverge.

**Trade-off acknowledged:** Filtering at acquisition means the raw run-control/calibration events are discarded and not retained anywhere in the pipeline for future reference (e.g., if a later milestone wants to analyze data-taking conditions). If this is ever needed, it would require re-acquiring the raw file rather than recovering it from a later pipeline stage. The team accepts this trade-off for prototype scope.

**Schema impact:** None — no field addition or change to `alice_event_schema_v1.avsc`. This is a pre-ingestion filtering step, not a schema change, so no version bump, no migration log entry.

**Action items:**
- [ ] Omer: add a `fEventType == 7` filter step to the ALICE acquisition process (M3W9T5 output), re-verify the filtered file only before any Week 11 conformance audit work builds on it
- [ ] Abdullah: note in the Week 11 conformance audit scope that it audits the **filtered (~68-event)** dataset, not the raw 287

---

## Summary of Outcomes

| Discrepancy | Decision | Schema Change? | Version Bump? |
|---|---|---|---|
| Run number (139465 vs 139038) | Update docs to 139465 | Doc string only | No (doc-only, no bump per policy) |
| Entry count (287 vs 228) | 287 is authoritative (raw); ~68 post-filter | None | N/A |
| Physics-event filtering (23.7%) | Filter to PHYSICS_EVENT only, at acquisition | None | N/A |

**No breaking or field-level schema changes result from this decision.** The Week 11 full conformance audit proceeds against the corrected run number (139465) and the filtered (~68-event) dataset.

---


