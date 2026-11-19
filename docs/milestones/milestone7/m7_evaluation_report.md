# M7 Evaluation Report — Model v2

**Owner:** Abdalla
**Milestone:** M7 · Week 28 · Task M7W28T1
**Date:** 19 November 2026
**Model version:** `combined-m7w28t1-v2`
**Code:** `services/ml/model_v2.py`, `services/ml/test_model_v2.py`
**Record:** `services/ml/artifacts/model_card_v2.json` (settings and every figure below)
**Result:** Prototype bar **met** on every stream — pooled AUC 0.997, FPR 0.88%, recall 99.7%,
precision 77.6% — on **synthetic** anomalies. Read Section 9 before quoting it.

---

## 1. Summary

| Bar | Target | Pooled | Worst stream | Status |
|---|---|---|---|---|
| AUC | ≥ 0.85 | 0.997 | 0.992 (TELEMETRY) | **Met** |
| FPR | ≤ 5% | 0.88% | 0.94% (RADAR) | **Met** |

Model v2 is the model M7 delivers. It replaces the Isolation Forest alone (v1, M7W27T2) after the
baseline comparison (M7W27T3) showed each detector misses one anomaly type the other catches in
full. v2 is better or equal to v1 on every figure, on every stream (Section 6).

The figures measure separation on a synthetic corpus whose anomalies are far from normal by
construction. They show the pipeline and the model work end to end. They are not a forecast for
real sensor faults.

---

## 2. What model v2 is

Two detectors per sensor stream. **Either one raises the alarm.**

| Detector | What it sees | Catches best |
|---|---|---|
| Isolation Forest | The combination of features | Several features each a little off (`noise_burst`) |
| Per-feature robust z-score | Each feature on its own; the record's worst feature | One feature far out (`velocity_spike`) |
| Telemetry integrity rules (unchanged) | Sequence numbers and timestamps per device | `missing_reading`, `timestamp_stall` |

Isolation Forest stays the model, as Module 7 locks. The z-score check sits beside it the way the
telemetry rules already do.

**Decision:** adopted 12 November 2026 on M7W27T3's evidence, which was taken on the **training**
split, not the test set (M7W27T3 Section 5).

---

## 3. How every figure was produced

### 3.1 Training data and class balance

| Item | Value | Source |
|---|---|---|
| Corpus | M3 synthetic corpus, 50,000 records per stream | M3W11T1 |
| Anomaly rate | 2.96–2.97% per stream, natural; no SMOTE, no rebalancing | M7W27T4, decided 9 November |
| Split | 80/20, stratified by `anomaly_type`, seed 42, test IDs fixed in `data/splits/` | M7W27T4 |
| Train | 40,000 per stream (1,185 / 1,189 / 1,187 anomalies) | M7W27T4 |
| Test | 10,000 per stream (297 / 297 / 296 anomalies) | M7W27T4 |

The test set was measured once for this report and was not used to choose or tune anything.

### 3.2 Features

Built by `featurize()` in `services/ml/feature_assembly.py`, the same function the scoring path
uses (M7W27T1).

| Stream | Features |
|---|---|
| RADAR (5) | `range_m`, `bearing_deg`, `elevation_deg`, `velocity_ms`, `signal_strength_db` |
| LIDAR (8) | `log_point_count`, `centroid_x_m`, `centroid_y_m`, `centroid_z_m`, `max_range_m`, `avg_intensity`, `min_intensity`, `centroid_range_ratio` |
| TELEMETRY (1 + 2 rules) | `value_z` (value standardised per parameter); rules `sequence_gap`, `timestamp_not_advancing` |

ALICE events carry no features: M6W26T5 records ALICE's role as architecture validation, not
detection.

### 3.3 Training method

| Setting | Value |
|---|---|
| Isolation Forest | `n_estimators=200`, `max_samples=256`, `random_state=42`, fitted on all training rows; `contamination` not used |
| z-score | Median and MAD per feature, from **normal training rows only**; a zero MAD is replaced by 1 |
| Risk per detector | Share of normal training scores at or below the record's score, 0–1 |
| Alarm line | Risk ≥ **0.995** for each detector — each gets half the 1% false-alarm budget (decision C, 12 November) |
| Library | scikit-learn 1.7.2, pinned in `services/ml/requirements.txt` |

### 3.4 The three outputs written to `fused_events`

| Column | Definition |
|---|---|
| `risk_score` | The higher of the two detector risks. A telemetry rule hit sets it to 1.0 |
| `anomaly_label` | 1 when `risk_score` ≥ 0.995, otherwise 0 — the same as "either detector fired" |
| `confidence` | Distance from the alarm line, scaled 0–1 on each side: 0 at the line, 1 at either end |

All three stay inside the CHECK ranges added on 12 November; `test_model_v2.py` checks this over
the whole input grid.

### 3.5 Reproduce

```bash
python services/ml/model_v2.py train     # from the repo root
pytest services/ml -q
```

Two consecutive runs produce a byte-identical `model_card_v2.json`. Model files (`*_v2.joblib`)
are git-ignored and rebuilt by `train`.

---

## 4. Results on the test set

95% bootstrap intervals in brackets, 1,000 resamples.

| Stream | AUC | FPR | Recall | Precision |
|---|---|---|---|---|
| RADAR | 0.9999 [0.9998–1.000] | 0.94% [0.75–1.12] | 100% [100–100] | 76.5% [72.2–80.4] |
| LIDAR | 0.9998 [0.9996–1.000] | 0.80% [0.64–1.00] | 100% [100–100] | 79.2% [74.8–83.3] |
| TELEMETRY | 0.992 [0.982–0.9995] | 0.90% [0.71–1.09] | 99.0% [97.7–100] | 77.1% [72.7–81.3] |
| **Pooled** | **0.997 [0.994–0.9998]** | **0.88% [0.77–0.98]** | **99.7% [99.2–100]** | **77.6% [75.4–80.0]** |

**Counts, pooled:** 887 of 890 anomalies caught, 3 missed, 256 false alarms, 28,854 normal records
correctly passed.

**Alarm line transfer:** the line was set on normal training rows and the test FPR (0.80–0.94%)
sits at or below the 1% budget on every stream. No drift.

---

## 5. Recall by anomaly type

| Stream | Type | Caught |
|---|---|---|
| RADAR | `ghost_target` | 103 / 103 |
| RADAR | `sensor_dropout` | 100 / 100 |
| RADAR | `velocity_spike` | 94 / 94 |
| LIDAR | `ghost_point` | 100 / 100 |
| LIDAR | `noise_burst` | 100 / 100 |
| LIDAR | `point_cloud_dropout` | 97 / 97 |
| TELEMETRY | `missing_reading` | 93 / 93 — by rule |
| TELEMETRY | `out_of_range_value` | 99 / 99 |
| TELEMETRY | `timestamp_stall` | **101 / 104** — by rule |

The only misses are 3 `timestamp_stall` records, all on `SENSOR-UNIT-01`. Each one comes directly
after a `missing_reading` anomaly on the same device. The rule compares a record with the one just
before it, and the stall's timestamp is still later than that anomalous record's, so time appears
to advance. Neither detector can see a stall, because it does not change `value`. Two anomalies
back to back on one device is a corpus artefact rather than a pattern the rule should be tuned
to; recorded, not fixed.

---

## 6. v1 → v2

| Figure (test set) | v1 — Isolation Forest alone | **v2 — combined** |
|---|---|---|
| Pooled AUC | 0.996 | **0.997** |
| Pooled FPR | 1.03% | **0.88%** |
| Pooled recall | 97.5% | **99.7%** |
| Pooled precision | 74.4% | **77.6%** |
| Anomalies missed | 22 | **3** |
| False alarms | 299 | **256** |
| RADAR `velocity_spike` | 75 / 94 | **94 / 94** |

Per stream, v2 is better or equal on every figure. RADAR FPR moves from 0.92% to 0.94%, which is
2 records and well inside the interval. v2's per-stream figures equal M7W27T3's "combined, half
budget" figures exactly; `test_card_reproduces_the_m7w27t3_combined_figures` checks this.

---

## 7. Which detector raised the alarms

Test set. One alarm can come from more than one source, so the sources add up to more than the
alarms.

| Stream | Source | True alarms | False alarms |
|---|---|---|---|
| RADAR | Isolation Forest | 269 | 45 |
| RADAR | z-score | 297 | 47 |
| LIDAR | Isolation Forest | 297 | 62 |
| LIDAR | z-score | 235 | 56 |
| TELEMETRY | Isolation Forest | 101 | 65 |
| TELEMETRY | z-score | 101 | 57 |
| TELEMETRY | Rules | 194 | **0** |

Both detectors earn their place: the z-score check alone catches every RADAR anomaly, and
Isolation Forest alone catches every LIDAR anomaly. The telemetry rules raise no false alarms on
the corpus.

Every alarm also carries a **reason** in the scorer's output — for example
`zscore:velocity_ms` or `rule:sequence_gap`. It is not a database column. It is the starting point
for M8's explanations: a z-score alarm already names its feature.

---

## 8. Anchors for these figures

- **Baseline comparison (M7W27T3):** a per-feature z-score alone and Isolation Forest alone both
  meet the bar, and each misses one type. v2 is their combination at the same total budget.
- **Prototype bar:** met by a wide margin. Section 9 explains why that margin says more about the
  corpus than about the model.

### Live traffic preview

20,000 normal records per stream from the aligned live producer (`sensor_producer.py`, M7W27T1
D1), timestamps spaced at the producer's default 200 ms, scored by `V2Scorer`:

| Stream | Flagged | Budget |
|---|---|---|
| RADAR | 1.04% | 1% |
| LIDAR | 0.76% | 1% |
| TELEMETRY | 0.84% | 1% |

In line with the budget. The measured figure on real fused rows is M7W28T3's.

---

## 9. Limits on these results

1. **The anomalies are synthetic and easy.** Every injected anomaly sits far outside the normal
   range by construction. AUC 0.997 measures separation on this corpus, not performance on real
   sensor faults, which will be subtler.
2. **Train and test come from the same generator.** The test set is held out, but it is not
   independent data.
3. **Per-sensor detection only.** No cross-sensor detection — `open_items_m6.md` Item 14, M10.
4. **About 100 records per anomaly type.** Per-type recall is shown as counts for that reason;
   precision differences of a point or two between v1 and v2 are not significant.
5. **Risk scores saturate.** A record more unusual than every normal training record gets exactly
   1.0, so the strongest alarms tie and cannot be ranked against each other.
6. **`confidence` is a distance, not a probability.** It says how far a record sits from the
   alarm line on the risk scale, not how likely the label is to be right.
7. **The dashboard's `critical_count` does not fit this scale.** The API contract defines it as
   `risk_score > 0.7`. On the test set, 32–41% of **normal** records score above 0.7 (RADAR 40.5%,
   LIDAR 41.4%, TELEMETRY 32.2%) — more than 30% because `risk_score` takes the higher of two
   detectors — so the count would be almost entirely non-alarms. To be redefined with Beyza before M9 — for example on
   `anomaly_label = 1` and `confidence`.
8. **The telemetry rules assume timestamps advance.** At the producer's 200 ms interval they do.
   A producer emitting several records per device in the same millisecond — as a tight-loop
   throughput benchmark would — makes `timestamp_not_advancing` fire on normal records. A
   back-to-back run of 20,000 records flagged 97.5% of them. Relevant to the M10 throughput work.

---

## 10. Carried to `open_items_m7.md`

| Item | Owner | Target |
|---|---|---|
| `critical_count` threshold incompatible with the v2 risk scale (Limit 7) | Beyza | M9 |
| Saturated risk scores cannot be ranked (Limit 5) | Abdalla | M8 — SHAP or the raw detector scores can break ties |
| Telemetry rule depends on timestamp spacing (Limit 8) | Abdalla | M10 — with the throughput benchmark |
| Subtler and correlated anomalies for a harder evaluation set | Abdalla | M10 — with `open_items_m6.md` Item 14 |
| PyTorch deep model (M7W28T2) | Abdalla | M10 — trigger of 15 November not met |

---

## 11. Tests

`services/ml/test_model_v2.py` — 8 tests: either detector crossing the line raises the alarm,
rule hits force risk 1.0, outputs stay inside the database CHECK ranges, confidence is 0 at the
line, the reason names the detector and feature, the card matches the code settings, every
stream meets the prototype bar, and the card reproduces M7W27T3's combined figures.
