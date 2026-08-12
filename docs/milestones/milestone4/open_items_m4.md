# DataForge — M4 Open Items Log

**Task ID:** M4W13T7
**Owner:** Abdulla
**Milestone:** M4 · Week 13
**Status:** Open — three items tracked, none resolved in this document
**GitHub Path:** `/docs/milestones/milestone4/open_items_m4.md`

---

> **Why this document exists**
> Three items surfaced during M4 Week 13 work require a decision at a later milestone rather than now, either because they need input the team doesn't have yet (Prof. Uysal's physics interpretation) or because the right fix depends on work not yet started (M5's per-device grouping). Consistent with how prior ALICE discrepancies were handled (`alice_discrepancy_resolution.md`), each is logged explicitly here rather than resolved unilaterally or left undocumented.

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

## Summary

| Item | Status | Deferred to | Trigger for resolution |
|---|---|---|---|
| 24 zero-track-count ALICE events | Open, keep all 68 through M4 | M7 | Prof. Uysal's interpretation + M7 model results |
| Telemetry `device_id` scope (single value) | Open, no M4 change | M5 | Module 5 (`data_loss_pct`) + generator repeat-mode planning |
| Net-momentum outlier, event `c1cc2e42…` | Open, logged as observation | M7 | M7 anomaly-detection feature/label design |

**No items are resolved in this document.** All three remain open by design, each tied to a specific downstream milestone where the team will have the information or infrastructure needed to decide properly, rather than being resolved prematurely or left untracked.

