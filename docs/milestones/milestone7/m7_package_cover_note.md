# DataForge — Milestone 7 Package Cover Note

**Milestone:** M7 — AI/ML Anomaly Detection
**Task:** M8W29T7 (planned as M7W28T4)
**Owner:** Abdalla
**Date:** 25 November 2026
**Package status:** Closed-with-open-items. M7 closed on its original date, 22 November 2026.
- M7 ran Weeks 26–28 rather than 25–28, after the M6 pause, under the Week 26–28 catch-up plan.
- **The prototype bar is met** on every stream: pooled AUC 0.997, FPR 0.88% — on **synthetic**
  anomalies (evaluation report, Section 9).
- **Live scoring is deferred to M8.** Fused rows are scored by a batch scorer; 12,123 aligned
  rows scored and verified by SQL.
- Eleven open items in `open_items_m7.md`, each with an owner, target and trigger.
- Pending at assembly: the M7 tags and README update (M8W29T10, Omer).

---

## 1. What M7 Covers

Module 7 detects anomalies in the sensor streams:
- features joined back from fused rows to staging at scoring time, no schema bump (M6W26T5);
- training and evaluation on the M3 per-stream corpus at its natural ~3% anomaly rate;
- model v2 per stream: Isolation Forest plus a per-feature robust z-score, either one raising
  the alarm, with telemetry integrity rules alongside;
- one 0–1 `risk_score`, an alarm line at a 1% false-alarm budget, and `anomaly_label`,
  `risk_score`, `confidence` written to `fused_events`.

### The roadmap's three M7 outputs

| Output | Delivered | Where |
|---|---|---|
| Trained model | Model v2, `combined-m7w28t1-v2` | `services/ml/model_v2.py`; record in `services/ml/artifacts/model_card_v2.json` |
| Evaluation report | Yes | `docs/milestones/milestone7/m7_evaluation_report.md` |
| Baseline comparison | Yes | `docs/milestones/milestone7/m7w27t3_baseline_comparison.md` |

The trained `.joblib` files are not committed (`.gitignore`); every machine rebuilds them with
`python services/ml/model_v2.py train`. The model card is the committed record.

---

## 2. What's Complete — Per Person

### Abdalla

| Artifact | Task | Path | Status |
|---|---|---|---|
| Feature assembly, live/corpus alignment, telemetry integrity rules | M7W27T1 | `services/ml/feature_assembly.py`; `m7w27t1_feature_assembly.md` | Complete (`8af19aa`, `fb886fd`) |
| CHECK constraints on the scored columns | M7W27T5 finding | `infrastructure/scripts/` | Complete (`fe0175b`) |
| Isolation Forest (v1), common risk score; `anomaly_rate` fix | M7W27T2 | `services/ml/isolation_forest.py`; `m7w27t2_isolation_forest.md` | Complete (`5f5377e`) |
| Statistical baseline and comparison | M7W27T3 | `services/ml/baseline.py`; `m7w27t3_baseline_comparison.md` | Complete (`5734f01`) |
| Model v2 and evaluation report | M7W28T1 | `services/ml/model_v2.py`; `m7_evaluation_report.md` | Complete (`1bd79bb`, `2bc29ee`); CI Java 17 pin `8ca0d58` |
| PyTorch deep model | M7W28T2 | — | **Deferred to M10** — 15 November trigger not met |
| Batch scoring of fused rows | M7W28T3 | `services/ml/batch_score.py`; `m7w28t3_batch_scoring.md` | Complete (`3319669`, `3c89822`); live wiring → M8 |
| Plan B verification record | M7W28T8 | `m7_database_contribution.md` Section A | Complete (`2332f64`) |
| `develop` → `main` merge | M7W28T5 | `main` | Complete — PR #75 (`db4b1ba`), CI run [#360](https://github.com/Jeylani-2526/dataforge/actions/runs/45115381942) passed |
| M8 kickoff notes and charter | M7W28T6 | `docs/milestones/milestone7/m8_kickoff_notes.md`; `DataForge_Milestone_8.docx` | Complete (`108eeec`) |
| M7-closing advisor report | M7W28T9 | Emailed, not committed | Sent 22 November |
| Package, this note, open items log | M7W28T4 → M8W29T7 | `docs/milestones/milestone7/` | This task |

### Beyza

| Artifact | Task | Path | Status |
|---|---|---|---|
| Training set extraction and class balance | M7W27T4 | `docs/database/m7w27t4_training_extraction.md` | Complete (`021f594`, review corrections `f614e2f`) |
| Scored-row write path conformance | M7W27T5 | `docs/database/m7w27t5_scored_row_conformance.md` | Complete (`45e9a3f`, `f614e2f`) |
| M7 database contribution section | M7W28T7 | `docs/milestones/milestone7/m7_database_contribution.md` | Complete (`466e7c2`, PR #74) |
| Scored-row verification in the live DB | M7W28T8 | `m7_database_contribution.md` Section B | Second-machine run on pre-alignment data, reverted (`801600b`); aligned check carried — open item 4, M8W29T9 |

### Omer

No M7 tasks: reduced load under the catch-up plan. During M7's weeks he completed his M6 work —
M6W26T7 cross-machine build (`f59e78b`, updated `5cbe79a` on 13 November) and M6W26T8 README
update (`9f2e157`). M7 tags and README update are M8W29T10.

---

## 3. Results — As Measured

### Model v2, test set (evaluation report, Section 4)

| Stream | AUC | FPR | Recall | Precision |
|---|---|---|---|---|
| RADAR | 0.9999 | 0.94% | 100% | 76.5% |
| LIDAR | 0.9998 | 0.80% | 100% | 79.2% |
| TELEMETRY | 0.992 | 0.90% | 99.0% | 77.1% |
| **Pooled** | **0.997** | **0.88%** | **99.7%** | **77.6%** |

887 of 890 anomalies caught; 256 false alarms. Against v1 (Isolation Forest alone): missed
anomalies 22 → 3, false alarms 299 → 256.

### Class balance (M7W27T4)

150,000 corpus records, 2.97% anomalies, ~3% per stream — the M3 balance held. 80/20 stratified
split, seed 42.

### Scoring on the database (M7W28T3, M7W28T8 Section A — Abdalla's machine)

| Stream | Rows scored | Alarm rate |
|---|---|---|
| LIDAR | 4,077 | 1.03% |
| RADAR | 4,053 | 1.09% |
| TELEMETRY | 3,993 | 1.00% |

All six SQL checks passed: every row in the window scored, values inside the CHECK ranges, label
consistent with the alarm line, constraints present, `summary_5min.anomaly_rate` populated, and
the 37,060 rows before the window untouched.

### Prototype bar

| Metric | Bar | M7 position |
|---|---|---|
| AUC | ≥ 0.85 | **Met** — 0.997 pooled, 0.992 worst stream |
| FPR | ≤ 5% | **Met** — 0.88% pooled, 0.94% worst stream |
| Throughput | ≥ 10,000 events/sec | Not re-measured in M7; `open_items_m5.md` Item 1, M10 |
| Latency, p95 | ≤ 500 ms | Not re-measured in M7; `open_items_m6.md` Item 5, M10 |
| Data loss | ≤ 1% | Not re-measured in M7; M6 measured 0.0 |

**Read before quoting:** the anomalies are synthetic and far from normal by construction, and
train and test come from one generator. The figures show the pipeline and model work end to end;
they are not a forecast for real sensor faults (evaluation report, Section 9).

---

## 4. Corrections to Earlier Figures and Statements

| Earlier statement | Actual |
|---|---|
| M7W28T3 "Live Inference Integration" (Week 26–28 plan) | Batch scoring with `batch_score.py`; the 18 November trigger was missed and live wiring moved to M8 (decision 19 November) |
| M7W28T8 verifies scored rows on Beyza's machine (Week 26–28 plan) | Her run scored pre-alignment rows and was reverted; aligned data verified on Abdalla's machine only (plan B). Open item 4 |
| M7W28T6 output at `docs/planning/m8_kickoff_notes.md` (Week 26–28 plan, M8 charter) | Committed at `docs/milestones/milestone7/m8_kickoff_notes.md` |
| Weekly advisor reports on 6 and 13 November (Week 26–28 plan) | Weekly reports discontinued from 5 November; the M7-closing report was sent on 22 November |
| M7 package in Week 28 as M7W28T4 | Written in M8 Week 29 as M8W29T7 |
| Three M7 documents carry items "to `open_items_m7.md`" | The file did not exist until this task; all three references now resolve |
| CI "Docker Compose Build" job | Validates the compose file only (`docker compose config`); builds no image. Open item 11 |

---

## 5. Decisions Taken During M7

| Date | Decision |
|---|---|
| 9 November | Train on the natural ~3% anomaly rate; SMOTE 50/50 withdrawn, a balanced regenerated dataset rejected |
| 12 November | Alarm line at a 1% false-alarm budget (option C) |
| 12 November | Telemetry sequence anomalies handled by integrity rules alongside the model |
| 12 November | Live sensor producer aligned to the M3 corpus normal ranges (`8af19aa`) |
| 12 November | CHECK constraints on the scored columns and the `summary_5min.anomaly_rate` fix |
| 12 November | Model v2 — Isolation Forest plus per-feature z-score — on M7W27T3's training-split evidence |
| 12 November | PyTorch deep model deferred to M10 |
| 19 November | One-off batch scorer; live scoring moves to M8 with the SHAP work |
| 19 November | M7W28T8 option A: second-machine check on Beyza's machine (later plan B) |
| 19 November | M8 D1–D4: explanations in `anomaly_alerts` + `xai_explanations`; alarms only; live scoring in M8 Weeks 29–30; XAI code in `services/ml/` |
| 25 November | `open_items_m6.md` Items 8 and 13 closed; Item 10's residual moved to `open_items_m7.md` |

---

## 6. What Closes M7

- [x] Trained model, evaluation report and baseline comparison committed
- [x] AUC and FPR reported against the bar, with feature set, class balance and method stated
- [x] Scored rows written to `fused_events` and verified by SQL through `docker exec`
- [x] PyTorch decision recorded — deferred to M10
- [x] Live inference deferral recorded — moved to M8
- [x] `develop` merged into `main` with a CI run link (PR #75, run #360)
- [x] M8 kickoff notes and charter committed
- [x] M7-closing advisor report sent (22 November)
- [x] Open items log committed with owners, targets and triggers (this task)
- [ ] Tags `M7-W28-abdalla`, `M7-W28-beyza`, `M7-W28-omer` at the closing commit (M8W29T10)
- [ ] README: M7 Completed, M8 In Progress (M8W29T10)
