# M7W27T3 — Baseline Comparison

**Owner:** Abdalla
**Milestone:** M7 · Week 27
**Date:** 12 November 2026
**Code:** `services/ml/baseline.py`, `services/ml/test_baseline.py`
**Record:** `services/ml/artifacts/baseline_comparison.json`
**Result:** Neither detector wins outright. Each misses one anomaly type the other catches in full.
Combining them, inside the same 1% false-alarm budget, catches both. Recommended as model v2 —
Section 5.

---

## 1. Why a baseline

The roadmap names a baseline comparison as an M7 deliverable. Without one, the Isolation Forest's
AUC of 0.996 has nothing to be better than — and on a corpus this easy (M7W27T2 Section 6), a
simple method might do as well. This task checks.

## 2. The baseline

A per-feature **robust z-score**: for each feature, how many normal spreads a value sits from the
normal median; the record's score is its **worst** feature.

- Median and MAD (median absolute deviation) per feature, from **normal training rows only**.
- No model, no randomness, a few lines of code.

**Held equal with M7W27T2**, so only the detector differs: same features (M7W27T1), same fixed
split, same risk-score definition, same alarm line (1% of normal training rows), and the same two
telemetry integrity rules.

---

## 3. Results on the test set

| Stream | Detector | AUC | FPR | Recall | Precision |
|---|---|---|---|---|---|
| RADAR | Isolation Forest | 0.9980 | 0.92% | 93.6% | 75.7% |
| RADAR | **Baseline** | **0.9999** | 0.94% | **100%** | 76.5% |
| LIDAR | **Isolation Forest** | **0.9996** | 1.07% | **100%** | 74.1% |
| LIDAR | Baseline | 0.9972 | 1.11% | 90.9% | 71.4% |
| TELEMETRY | Isolation Forest | 0.9920 | 1.09% | 99.0% | 73.4% |
| TELEMETRY | Baseline | 0.9925 | 1.08% | 99.0% | 73.6% |

Both meet the prototype bar (AUC ≥ 0.85, FPR ≤ 5%) on every stream.

### Where they differ — recall by anomaly type

| Stream | Type | Isolation Forest | Baseline |
|---|---|---|---|
| RADAR | `ghost_target` | 103 / 103 | 103 / 103 |
| RADAR | `sensor_dropout` | 100 / 100 | 100 / 100 |
| RADAR | **`velocity_spike`** | **75 / 94** | 94 / 94 |
| LIDAR | `ghost_point` | 100 / 100 | 100 / 100 |
| LIDAR | **`noise_burst`** | 100 / 100 | **73 / 100** |
| LIDAR | `point_cloud_dropout` | 97 / 97 | 97 / 97 |
| TELEMETRY | all three | identical | identical |

Seven of nine types: no difference. The two that differ point in opposite directions.

---

## 4. Why each one has a blind spot

**`velocity_spike` — one feature, far out. The baseline's home ground.**
It changes only `velocity_ms`, to ±800–1,500 against a normal −100–300. A per-feature check sees
that instantly. Isolation Forest picks a random feature at each split, so a record unusual in one
of five dimensions is isolated more slowly, and 19 of 94 fall below the alarm line
(M7W27T2 Section 5).

**`noise_burst` — several features, each only a little off. Isolation Forest's home ground.**
It multiplies `point_count` by 1.5–3, `max_range_m` by 1.2–2 and `avg_intensity` by 1.1–1.5. No
single value is extreme, so the worst-feature score misses 27 of 100. Isolation Forest scores the
**combination** and catches all of them.

**Telemetry — a tie, and neither does the work.** Without the integrity rules both detectors
catch 35% (AUC 0.69): only `out_of_range_value` is visible in `value`. The rules account for the
rest, for either detector.

**What this says about the model choice.** The corpus's normal features are independent — there
is no relationship between, say, range and velocity for a detector to learn. That is the
situation in which a simple per-feature check is hardest to beat, and it still lost on
`noise_burst`. Real sensor data has relationships between features; that is where a multivariate
model earns its place. This corpus cannot show that advantage beyond one anomaly type, and the
report should not claim more.

---

## 5. Combining them

"Alarm if **either** detector fires." Run naively, each detector spends its own 1% and the total
rises:

| Stream | Either, 1% each | FPR | Precision |
|---|---|---|---|
| RADAR | recall 100% | 1.78% | 63.2% |
| LIDAR | recall 100% | 1.44% | 68.0% |

So the fair version gives each detector **half** the budget (alarm line 0.995 each), keeping the
total near 1%:

| Stream | Detector | FPR | Recall | Precision |
|---|---|---|---|---|
| RADAR | Isolation Forest alone (T2) | 0.92% | 93.6% | 75.7% |
| RADAR | **Combined, half budget each** | 0.94% | **100%** | 76.5% |
| LIDAR | Isolation Forest alone (T2) | 1.07% | 100% | 74.1% |
| LIDAR | **Combined, half budget each** | **0.80%** | 100% | **79.2%** |
| TELEMETRY | Isolation Forest alone (T2) | 1.09% | 99.0% | 73.4% |
| TELEMETRY | **Combined, half budget each** | **0.90%** | 99.0% | **77.1%** |

Better or equal on every figure, on every stream: `velocity_spike` goes from 75 / 94 to 94 / 94,
`noise_burst` stays at 100 / 100, and false alarms fall.

**Is this choice made on the test set?** No. The same comparison on the **training** split gives
the same answer, and that is the evidence the recommendation rests on:

| Stream (training split) | IF alone | Baseline alone | Combined, half budget |
|---|---|---|---|
| RADAR recall / FPR | 94.1% / 1.00% | 100% / 1.00% | **100% / 0.98%** |
| LIDAR recall / FPR | 100% / 1.00% | 90.2% / 1.00% | **100% / 0.71%** |
| TELEMETRY recall / FPR | 98.9% / 1.00% | 98.9% / 1.01% | **98.9% / 0.78%** |

The test figures above are reported as a check on that choice, not as its basis.

### Recommendation

Adopt the combined detector as **model v2** in M7W28T1, before live scoring is wired in M7W28T3:
Isolation Forest plus per-feature robust z-score, either one raising the alarm, each at risk
≥ 0.995, with the telemetry rules unchanged. `risk_score` becomes the higher of the two.

Isolation Forest stays the model, as Module 7 locks. The per-feature check sits beside it the way
the telemetry rules already do, and it brings the same benefit for M8: an alarm it raises names
the feature and how far out it was.

**Cost:** one more score per record, a few arithmetic operations. No new dependency.
**Decision:** the lead's, with M7W28T1.

---

## 6. Limits

- The limits in M7W27T2 Section 6 apply in full: synthetic anomalies, train and test from one
  generator, ~100 records per anomaly type.
- A difference of 19 or 27 records is well clear of noise at these sizes. The differences in
  precision (a point or two) are not.
- A baseline that performs this well is partly a statement about the corpus. An evaluation set
  with subtler and correlated anomalies (`open_items_m6.md` Item 14, M10) is what would separate
  the two methods properly.

## 7. Also in this task

`model_card.json` and `telemetry_value_stats.json` are now written with LF line endings on every
platform, so regenerating them on Windows leaves the committed files byte-identical.

## 8. Tests

`services/ml/test_baseline.py` — 4 tests: median and MAD ignore an outlier, a constant feature does
not divide by zero, the score is the worst feature, and the committed comparison covers every
stream, split and detector.
