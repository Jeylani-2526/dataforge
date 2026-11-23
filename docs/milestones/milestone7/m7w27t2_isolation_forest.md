# M7W27T2 — Isolation Forest Baseline

**Owner:** Abdalla
**Milestone:** M7 · Week 27
**Date:** 12 November 2026
**Model version:** `iforest-m7w27t2-v1`
**Code:** `services/ml/isolation_forest.py`, `services/ml/test_isolation_forest.py`
**Record:** `services/ml/artifacts/model_card.json` (settings and every figure below)
**Result:** Prototype bar **met** — pooled AUC 0.996, FPR 1.03% — on **synthetic** anomalies. Read Section 6 before quoting it.

---

## 1. What was built

| Part | Choice | Decided in |
|---|---|---|
| Model | One Isolation Forest per sensor stream; each record scored by its own stream's model | M6W26T5 |
| Training data | M3 corpus training split at its natural ~3% anomaly rate. No SMOTE, no rebalancing | 9 November |
| Features | From M7W27T1: RADAR 5, LIDAR 8, TELEMETRY 1 + 2 integrity rules | M7W27T1 |
| Alarm line | Tightest line that flags at most **1% of normal training rows** | 12 November (option C) |
| Common risk score | Share of normal training scores at or below the record's score, 0–1 | M6W26T5 Level 2 |
| Test set | The fixed 20% split in `data/splits/`, measured **once**, never used to tune | M7W27T4 |

Parameters: `n_estimators=200`, `max_samples=256` (default), `random_state=42`,
scikit-learn 1.7.2. `contamination` is not used; the alarm line replaces it.

**Reproducible:** `python services/ml/isolation_forest.py train` rebuilds the models and the
model card. Two consecutive runs produce an identical card. Model files are not committed —
they are rebuilt by this command, with scikit-learn pinned in `services/ml/requirements.txt`.

---

## 2. The three outputs per record

These are the columns M7W28T3 writes to `fused_events`, inside the CHECK ranges added on
12 November.

| Column | Definition |
|---|---|
| `risk_score` | Share of normal training records whose score is at or below this one. 0.50 = as unusual as a typical normal record; 0.99 = more unusual than 99% of them. A telemetry rule hit sets it to 1.0 |
| `anomaly_label` | 1 when `risk_score` ≥ 0.99, otherwise 0 |
| `confidence` | Distance from the alarm line, scaled 0–1 on each side: 0 at the line, 1 at the far end |

Because all three streams use the same definition, a RADAR 0.995 and a LIDAR 0.995 mean the same
thing, which is what allows one ranked alert list and pooled figures.

---

## 3. Results on the test set

10,000 records per stream, ~297 anomalous. Brackets are 95% bootstrap intervals, 1,000 resamples.

| Stream | AUC | FPR | Recall | Precision |
|---|---|---|---|---|
| RADAR | 0.998 [0.997–0.999] | 0.92% [0.75–1.12] | 93.6% [90.8–96.1] | 75.7% [71.1–79.6] |
| LIDAR | 1.000 [0.999–1.000] | 1.07% [0.88–1.28] | 100% | 74.1% [69.6–78.4] |
| TELEMETRY | 0.992 [0.982–1.000] | 1.09% [0.91–1.31] | 99.0% [97.7–100] | 73.4% [68.9–77.6] |
| **Pooled** | **0.996 [0.993–0.999]** | **1.03% [0.91–1.15]** | **97.5% [96.5–98.5]** | **74.4% [71.9–77.0]** |

| Bar | Target | Pooled | Worst stream |
|---|---|---|---|
| AUC | ≥ 0.85 | 0.996 | 0.992 (TELEMETRY) — **met** |
| FPR | ≤ 5% | 1.03% | 1.09% (TELEMETRY) — **met** |

The alarm line was set at 1.00% on training normals and measured 0.92–1.09% on the test set, so it
transferred without drift.

**Counts, pooled:** 868 anomalies caught, 22 missed, 299 false alarms, 28,811 normal records
correctly passed.

### Recall by anomaly type

| Stream | Type | Caught |
|---|---|---|
| RADAR | `ghost_target` | 103 / 103 (100%) |
| RADAR | `sensor_dropout` | 100 / 100 (100%) |
| RADAR | **`velocity_spike`** | **75 / 94 (80%)** |
| LIDAR | `ghost_point` | 100 / 100 (100%) |
| LIDAR | `noise_burst` | 100 / 100 (100%) |
| LIDAR | `point_cloud_dropout` | 97 / 97 (100%) |
| TELEMETRY | `missing_reading` | 93 / 93 (100%) — by rule |
| TELEMETRY | `out_of_range_value` | 99 / 99 (100%) |
| TELEMETRY | `timestamp_stall` | 101 / 104 (97%) — by rule |

---

## 4. What the figures mean in use

**Precision 74%: about 1 alarm in 4 is false.** At a 1% false-alarm rate and a 3% anomaly rate,
false alarms from the large normal class are a visible share of all alarms. In real operation
anomalies are rarer than 3%, so precision would be lower still. This is arithmetic, not a model
defect, and it is the main reason the alarm line sits at 1% and not at the 5% the bar allows:
at 5%, precision measured 35–40% in the M7W27T2 preview.

**Telemetry depends on the rules.** Isolation Forest alone scores AUC 0.687 on telemetry, because
two of its three anomaly types never change `value`. With the two integrity rules it reaches
0.992. The telemetry figure is a model-plus-rules result and is reported as one.

---

## 5. Weak spot: RADAR `velocity_spike`

19 of 94 missed. The cause is structural: this anomaly changes **one** of five features. Isolation
Forest picks a random feature at each split, so a record unusual in only one dimension takes
longer to isolate than one unusual in four, as `ghost_target` is. It scores above most normal
records — the AUC shows that — but not always above the 99th percentile.

Not tuned in this task: adjusting the model against the test set would spend the test set. Carried
to M7W28T1 with two candidates, both tunable on training data only: `max_features` below 1.0, or
a per-feature range check alongside the forest. M7W27T3's baseline is expected to catch this
type easily, which is itself worth showing.

---

## 6. Limits on these results

1. **The anomalies are synthetic and easy.** Every injected anomaly sits far outside the normal
   range by construction (`velocity_spike` ±800–1,500 m/s against a normal range of −100–300).
   AUC 0.996 measures separation on this corpus. It is not a forecast for real sensor faults,
   which will be subtler.
2. **Train and test come from the same generator.** The test set is held out, but it is not
   independent data. A model can only be wrong here about patterns the generator produces.
3. **Per-sensor detection only.** No cross-sensor detection — `open_items_m6.md` Item 14.
4. **~297 anomalies per stream.** Intervals are reported for that reason. Per-type recall rests on
   ~100 records each.
5. **Risk scores saturate.** A record more unusual than every normal training record gets exactly
   1.0, so the strongest alarms tie and cannot be ranked against each other.
6. **The dashboard's `critical_count` (risk_score > 0.7) does not fit this scale.** Every alarm has
   risk ≥ 0.99, so every alarm would count as critical. To be redefined with Beyza before M9 —
   for example on `confidence`.

---

## 7. Live traffic — preview

Scored against 20,000 simulated normal records per stream from the aligned live producer
(M7W27T1 D1): RADAR 1.10% flagged, LIDAR 1.05%, TELEMETRY 0.95%. In line with the 1% budget.
The measured figure on real fused rows is M7W28T3's.

---

## 8. Changes shipped with this task

| Change | Why |
|---|---|
| `services/ml/requirements.txt`, scikit-learn pinned to 1.7.2 | Saved models load only with the version that trained them. 1.7.2 supports the CI's Python 3.10 and local 3.12 |
| CI installs `services/ml/requirements.txt` before `pytest` | The model tests need numpy and scikit-learn |
| `services/ml/artifacts/*.joblib` git-ignored | Rebuilt by `train`; the committed record is `model_card.json` |
| `summary_5min.anomaly_rate` corrected, with a migration | It counted rows that had **any** label, so it would read 100% once scoring began. Now the share of scored rows labelled 1. Needed before M7W28T8 |
| M7W27T4 document | Title encoding repaired; Section 3 in English; RADAR/TELEMETRY test counts un-swapped; feature list replaced by a pointer to M7W27T1 |

## 9. Tests

`services/ml/test_isolation_forest.py` — 8 tests: the risk-score definition, the alarm line at the
boundary, rule hits, outputs inside the database CHECK ranges, confidence behaviour, input not
modified, and two that read the committed model card: its settings match the code, and every
stream meets the prototype bar.
