# M8 Kickoff Notes — Explainable AI Layer

**Task:** M7W28T6 · **Owner:** Abdalla · **Written:** 19 November 2026
**Kickoff:** Monday 23 November 2026 · **Milestone:** 23 November – 20 December 2026, Weeks 29–32

---

## 1. Goal

From the roadmap: integrate SHAP for feature attribution, and build the explanation pipeline that
outputs human-readable reasoning for every alert.
**Key deliverables:** XAI module, explanation outputs, cause-effect chain logic.

**By 20 December:** every alarm the model raises carries a stored explanation — which features
drove it, in which direction, and a sentence an operator can read — in the tables the dashboard
contract already reads from. The explanation is evaluated, not just produced.

---

## 2. Decisions taken before kickoff (Abdalla, 19 November 2026)

| # | Decision | Chosen | Why |
|---|---|---|---|
| D1 | Where explanations are stored | `anomaly_alerts` + `xai_explanations`, per `erd_final.md` | Matches the final API contract (`GET /api/v1/xai/{fused_event_id}`); `fused_event_schema_v1` stays locked |
| D2 | Which rows are explained | Alarms only (`anomaly_label = 1`, ~1% of rows) | What an operator opens in the XAI panel; ~100× less work and storage |
| D3 | Live scoring inside the fusion stream | Built in M8, Weeks 29–30 | Carried from M7W28T3; it touches the same write path as the explanations. `batch_score.py` stays as the backfill tool |
| D4 | Where XAI code lives | `services/ml/`, next to M7 | One module, one test suite; the empty `services/ai-ml/` stubs are retired |

**D1 and the roadmap wording.** The roadmap says "explanation outputs in fused schema". D1 meets
the intent — explanations keyed by `fused_event_id` — without bumping the locked fused schema.
Recorded here so the difference is a decision, not a drift.

---

## 3. What M8 starts from

| From M7 | State on 19 November |
|---|---|
| Model v2 — Isolation Forest + per-feature z-score, one pair per stream | On `develop` (#72); pooled AUC 0.997, FPR 0.88% on synthetic anomalies |
| `featurize()` — the same features for training and scoring | 5 RADAR, 8 LIDAR, 1 TELEMETRY + 2 integrity rules |
| `V2Scorer` with a `reason` per alarm | Already names the z-score's feature (`zscore:velocity_ms`) and the rule (`rule:sequence_gap`) |
| `batch_score.py` | 12,123 fused rows scored on Abdalla's machine; second-machine run is M7W28T8 |

### SHAP feasibility — checked 19 November, before committing to it

- `shap` 0.54.1 runs against the pinned scikit-learn 1.7.2 and numpy 2: `TreeExplainer` supports
  `IsolationForest` directly.
- **~1.7 ms per record** (RADAR, 50 records). At ~1% alarms, explanation cost is negligible.
- On 50 RADAR `velocity_spike` anomalies, the top SHAP feature was `velocity_ms` in **50 / 50**.
- **Units — the design point Week 29 must settle.** For an Isolation Forest, SHAP values add up
  exactly (error ~4×10⁻¹⁵) to the **expected path length**, not to `risk_score`. A shorter path
  means more anomalous, so a **negative** SHAP value pushes toward an alarm. Showing raw values
  with the contract's `direction: positive` would read backwards.

### What the other two parts of v2 need

| Alarm source | Explanation | SHAP needed? |
|---|---|---|
| Isolation Forest | SHAP over the forest | Yes |
| z-score | Per-feature z is already an exact, additive attribution | No — reuse it |
| Telemetry rules | The rule itself (`sequence_gap`, `timestamp_not_advancing`) | No — templated text |

---

## 4. Gaps found while preparing this note

| Gap | Where | Who / when |
|---|---|---|
| `anomaly_alerts` and `xai_explanations` are in `erd_final.md` and the API contract, but **not in `init-db.sql`** | Database | Beyza, Week 29 |
| The contract's XAI example uses features the model doesn't have (`data_loss_pct`, `fusion_quality`, `event_count_1m`) | `api_contracts_final.md` Section 10 | Beyza, Week 29 |
| `critical_count` = `risk_score > 0.7` counts 32–41% of **normal** rows on the v2 scale | M7 evaluation report, Limit 7 | Beyza proposes, Week 29; implemented M9 |
| No writer for `anomaly_alerts` — `batch_score.py` writes scores to `fused_events` only | Scoring path | Abdalla, Week 30 |
| `anomaly-detection` and `xai-service` compose blocks point to empty `services/ai-ml/` folders, use `../../` from three levels deep, and name Dockerfiles that don't exist | `docker-compose.yml` | Omer, Week 30 |
| The plan's closure command `--profile m6-and-above up -d --build` starts fusion with no inputs — profiles don't cascade | `open_items_m6.md` Item 12.1 | Omer's README section, Week 29 |

---

## 5. Carried into M8

| Item | From | Owner | M8 action |
|---|---|---|---|
| Live scoring in the fusion stream | M7W28T3 | Abdalla | Build, Week 30 (D3) |
| Effective watermark 12–13 s vs 5 s configured | `open_items_m6.md` Item 1 | Abdalla | Decision, Week 29; implementation M10 |
| Silent mis-pairing, unquantified | Item 4 | Abdalla | Measure with payload timestamps under injection, Week 31 |
| Checkpoint lost after > 7-day pause; crash exits 0; topic race | Item 11 | Abdalla | Retention, non-zero exit + restart policy, topics pre-created, Week 30 |
| Compose and environment operability | Item 12 | Omer | README "Running the stack", Week 29 |
| 37,060 orphaned fused rows on Abdalla's machine | M7W28T3 | Abdalla | Matches Item 12.3 (fusion ran without `spark-processor`); confirm and close, Week 29 |
| Saturated risk scores can't be ranked | M7 Limit 5 | Abdalla | SHAP magnitude or raw detector score as the tie-break, Week 31 |
| Omer's capacity | Item 13 | Abdalla | Reviewed weekly |

Stays where it is: heartbeat mismatches and the alignment side table (Beyza, M9); throughput,
batch lag and fused-path latency (M10); cross-sensor detection (M10); PyTorch model (M10).

---

## 6. Week plan

| Week | Dates | Focus |
|---|---|---|
| 29 | 23 – 29 Nov | Design and foundations — XAI design note, alert and XAI tables, contract fixes, watermark decision, README |
| 30 | 30 Nov – 6 Dec | Build — XAI module, live scoring + explanation in the fusion path, write-path conformance, compose clean-up |
| 31 | 7 – 13 Dec | Evaluate — explanation fidelity, cause-effect text, mis-pairing measurement, live DB verification |
| 32 | 14 – 20 Dec | Close — evaluation report, package, `open_items_m8.md`, merge, M9 kickoff, closing report to Emrah |

**Workload:** back to the nominal 40 / 40 / 20 after M7's 50% catch-up. Omer: one or two
technical tasks a week, reviewed weekly against Item 13's trigger.

---

## 7. Descope triggers

| Candidate | Trigger | If missed |
|---|---|---|
| Live scoring in the fusion stream | Working by **Wednesday 2 December** | Stays batch (`batch_score.py` + explanation backfill); live wiring moves to M9 with the dashboard |
| Mis-pairing measurement (Item 4) | Injection run done by **Friday 11 December** | Moves to M10 with Item 1's implementation |

---

## 8. M8 is complete when

1. Every alarm row in the scoring window has an `anomaly_alerts` row and an `xai_explanations` row
   with populated `shap_values`, `top_features`, `explanation_text` and `model_version`.
2. The direction in stored explanations means "pushes toward alarm", whatever the model's units.
3. Explanation fidelity is measured on the M3 test set: how often the top feature matches the
   feature each anomaly type was injected into — reported as measured.
4. Explanation latency per alarm is measured.
5. Live scoring runs in the fusion stream, or is formally deferred to M9 against the 2 December
   trigger.
6. Rows written are verified by SQL through `docker exec`, never Adminer.
7. The watermark specification decision (Item 1) is recorded with its rationale.
8. `open_items_m8.md` records everything incomplete with owner, target and trigger.
9. `develop` is merged into `main` with a CI run link; M9 kickoff notes committed.

---

## 9. Kickoff agenda — Monday 23 November

1. M7 result in five minutes: what v2 is, what the figures mean, and what they don't (synthetic anomalies).
2. The four decisions above — questions now rather than in Week 30.
3. Beyza: the two tables — hypertable on `time`, soft reference to `fused_events` as in M6 Option C?
4. Omer: Week 29 README task and the compose clean-up; Item 13 check-in.
5. Agree the 2 December trigger.
