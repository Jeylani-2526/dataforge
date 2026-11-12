# M7W27T1 — Feature Assembly

**Owner:** Abdalla
**Milestone:** M7 · Week 27
**Date:** 12 November 2026
**Built to:** M6W26T5 (signed 5 November) — features from staging, labels from the M3 corpus
**Code:** `services/ml/feature_assembly.py`, `services/ml/test_feature_assembly.py`,
`services/ml/artifacts/telemetry_value_stats.json`
**Status:** Complete on the corpus path. Scoring-path row count **pending** — see Section 6.

---

## 1. What this task delivers

One feature function, `featurize(stream, record)`, used by **both** paths:

| Path | Input | Used by |
|---|---|---|
| Training | `data/synthetic/{stream}.jsonl` + the fixed split in `data/splits/` (M7W27T4) | M7W27T2, M7W27T3 |
| Scoring | `fused_events` joined to `raw_sensor_events_staging` on `sensor_event_id` | M7W28T3 |

Because both paths call the same function, training and scoring cannot drift apart in code.
Section 3 covers the case where they drifted apart in **data**.

---

## 2. Two decisions taken during T1

| # | Decision | Rationale |
|---|---|---|
| D1 | The live sensor producer now generates the **same normal ranges** as the corpus generators | Section 3: without it, 94% of normal live LIDAR rows were flagged |
| D2 | Telemetry sequence anomalies are caught by **two integrity rules**, alongside Isolation Forest | Section 5: two of three telemetry anomaly types never change `value` |

Option chosen for D2 over leaving the types out of M7 (telemetry recall capped near 33%) and over
window-level scoring (breaks the 1 fused row = 1 score design).

---

## 3. Finding: the live stream and the corpus had different "normal"

The project has two independent generators: `scripts/generators/` produced the M3 corpus;
`sensor_producer.py` produces the live stream. Their normal ranges differed:

| Field | Corpus | Live (before) |
|---|---|---|
| LIDAR `point_count` | 10,000 – 200,000 | 500 – 5,000 |
| LIDAR `centroid_x/y_m` | ±100 | ±500 |
| LIDAR `centroid_z_m` | −10 – 50 | 0 – 200 |
| LIDAR `max_range_m` | 50 – 500 | 10 – 200 |
| LIDAR `min_intensity` | 20 – min(100, avg) | 0 – avg |
| RADAR `elevation_deg` | −30 – 30 | −90 – 90 |
| RADAR `velocity_ms` | −100 – 300 | −100 – 100 |
| RADAR `signal_strength_db` | −90 – −20 | −80 – −20 |
| TELEMETRY parameters | 3, corpus ranges | 5, incl. `altitude_m`, `signal_rssi`, wider ranges |

**Measured effect** — Isolation Forest trained on the corpus, scoring 10,000 **normal** live records:

| Stream | Before | After alignment |
|---|---|---|
| RADAR | 4.1% flagged | **0.3%** |
| LIDAR | **93.9%** flagged | **0.1%** |
| TELEMETRY | — (unknown parameters) | **2.2%** |

This also makes M6W26T5's statement — "train on the corpus that feeds the fused stream" — true.
Before this change it was not.

**Change:** `sensor_producer.py` ranges set to the corpus values; telemetry reduced to the three
corpus parameters. The live stream still carries no anomalies and `label = 0`, as before.

**Guard:** `test_live_producer_matches_corpus_normal` generates 3,000 live records per stream and
checks every feature against the corpus's normal min/max. Run against the old producer, it fails on
all three streams, so a future divergence is caught by CI.

---

## 4. Features

### RADAR — 5 features

`range_m`, `bearing_deg`, `elevation_deg`, `velocity_ms`, `signal_strength_db` — unchanged.

### LIDAR — 8 features

| Feature | Change | Why |
|---|---|---|
| `log_point_count` | log(1 + `point_count`) | A dropout has 0–10 points; normal is 10,000–200,000. On a raw scale it sits in the first 5% of the range and is hard to isolate |
| `centroid_x_m`, `centroid_y_m`, `centroid_z_m`, `max_range_m`, `avg_intensity`, `min_intensity` | unchanged | |
| `centroid_range_ratio` | new: distance of the centroid ÷ `max_range_m` | A centroid beyond the sensor's own max range is geometrically impossible — the definition of `ghost_point` |

`scan_id` is **dropped**: it is an identifier, not a measurement (M7W27T4 had listed it).

### TELEMETRY — 1 feature + 2 rules

| Feature | Definition | Why |
|---|---|---|
| `value_z` | (`value` − mean) ÷ std, **per `parameter_name`** | `cpu_temp_c`, `voltage_v` and `battery_pct` have different units. Mixing them in one column made a normal battery reading look like an abnormal voltage |

Mean and std come from **normal training rows only**, and are saved in
`telemetry_value_stats.json` so scoring uses exactly the same values:

| Parameter | Mean | Std | Rows |
|---|---|---|---|
| `battery_pct` | 59.761 | 22.858 | 12,863 |
| `cpu_temp_c` | 55.126 | 11.586 | 12,997 |
| `voltage_v` | 12.007 | 0.577 | 12,953 |

### ALICE

Excluded, per M6W26T5 Section 4.

---

## 5. Telemetry integrity rules

`timestamp_stall` and `missing_reading` leave `value` untouched. They are only visible by comparing
a record with the previous record from the same device.

| Rule | Fires when | Catches |
|---|---|---|
| `sequence_gap` | `sequence_number` jumps forward by more than 1 | `missing_reading` |
| `timestamp_not_advancing` | `timestamp_ms` is not later than the previous record's | `timestamp_stall` |

Both are **one-sided**, so the record after an anomaly is not flagged.

**Results on the full corpus (50,000 records):**

| Type | Rules fire |
|---|---|
| `missing_reading` | **465 / 465 (100%)** |
| `timestamp_stall` | **506 / 522 (96.9%)** |
| `out_of_range_value` | 0 / 496 (left to Isolation Forest) |
| normal | **0 / 48,517** |

**Scoring requirement for M7W28T3:** the previous record must come from **staging**, which holds
every telemetry record. Fused rows hold only ~1 in 2.5 sensor events, so checking fused rows alone
would see false gaps constantly. `raw_sensor_events_staging` has no index on `device_id`; one will
be needed for the per-row lookup in W28T3.

---

## 6. Assembled matrices

### Training path — complete

| Stream | Features | Train | Train anomalies | Test | Test anomalies |
|---|---|---|---|---|---|
| RADAR | 5 | 40,000 | 1,185 | 10,000 | 297 |
| LIDAR | 8 | 40,000 | 1,189 | 10,000 | 297 |
| TELEMETRY | 1 + 2 rules | 40,000 | 1,187 | 10,000 | 296 |

### Scoring path — pending

The plan asks for the assembled-row count against total fused rows. This needs the live database:

```bash
python services/ml/feature_assembly.py db
```

| Measure | Result |
|---|---|
| Fused rows | *pending* |
| Assembled | *pending* |
| Not assembled, by reason | *pending* |

M6W26T2 measured 100% reference resolution on Beyza's database. Rows fused before the D1 change
carry the old live ranges, so they will assemble but score as out-of-distribution. Scoring in W28
should run on rows fused **after** this change.

---

## 7. Preview — not the T2 result

A quick Isolation Forest run on these features, to check they help. M7W27T2 owns the official
figures, threshold and reporting.

| Stream | AUC (IF only) | Weakest type | Before T1 features |
|---|---|---|---|
| RADAR | 0.998 | `velocity_spike` 69% | 68% |
| LIDAR | 1.000 | `point_cloud_dropout` **88%** | 49% |
| TELEMETRY | 0.687 IF only — rules add the sequence types | `timestamp_stall` 97% (rules) | ~0% |

`velocity_spike` changes only one feature; it is a **threshold** question for T2, not a feature one.

---

## 8. Corrections to earlier documents

| Document | Statement | Actual |
|---|---|---|
| M6W26T5 | "train on the corpus that feeds the fused stream" | Not true until D1 — Section 3 |
| M7W27T4 Section 2 | RADAR test anomalies 296, TELEMETRY 297 | Swapped: RADAR **297**, TELEMETRY **296** (her own per-type table sums to these) |
| M7W27T4 Section 4 | `scan_id` used for training; "identical column sets" | `scan_id` dropped; each stream fills only its own columns |

---

## 9. Tests

`services/ml/test_feature_assembly.py` — 15 tests: feature shapes, the LIDAR transforms, per-parameter
standardisation, staging and corpus rows giving identical features, all rule cases including the
record after an anomaly and per-device separation, scoring-row failure reasons, and the live/corpus
alignment guard.
