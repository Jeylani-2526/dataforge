# DataForge — Labeled Training Data Specification



---

> **Why this document exists**
> This spec defines what "training-ready" means for the M7 anomaly-detection model: required fields, class-balance target, and train/test split convention. It is the direct input Omer's first labeled batches (M3W10T8) must satisfy, and the reference Abdullah's label-assignment verification (M3W10T3) checks against.

---

## 1. Required Fields Per Record

Every training-ready record must contain:

| Field | Source | Notes |
|---|---|---|
| `label` | Generator-assigned | int, `0` (normal) or `1` (anomalous). Never null. |
| `anomaly_type` | Generator-assigned | string, one of the nine locked anomaly types (Section 3) when `label=1`; **null when `label=0`**. Never populated for normal records. |
| All `sensor_schema_v1.avsc` fields | Generator-assigned | `event_id`, `sensor_id`, `sensor_type`, `timestamp_ms`, plus the subtype-specific fields for the record's `sensor_type` (RADAR: `target_id`, `range_m`, `bearing_deg`, `elevation_deg`, `velocity_ms`, `signal_strength_db`; LIDAR: `scan_id`, `point_count`, `centroid_x/y/z_m`, `max_range_m`, `avg_intensity`, `min_intensity`; TELEMETRY: `device_id`, `parameter_name`, `value`, `unit`, `sequence_number`), and `schema_version`. |

**Rule:** `label` and `anomaly_type` are additive to the locked `sensor_schema_v1.avsc` field set — they are not schema fields themselves (they live in the generator's labeled output file, not the Avro wire schema, since inference-time production sensor data has no ground-truth label). No schema version bump is implicated by this spec.

**Validation rule carried from M3W9T1 design:** `anomaly_type` populated ⟺ `label=1`. Any record with `label=0` and a non-null `anomaly_type`, or `label=1` and a null `anomaly_type`, is a label-assignment defect — flagged in M3W10T3, not silently corrected.

---

## 2. Class-Balance Target

Consistent with the locked 3% injection rate and 50,000-record-per-stream volume (Week 9, confirmed unchanged):

| Stream | Total Records | Normal (`label=0`) | Anomalous (`label=1`) | Anomalous % |
|---|---|---|---|---|
| Radar | 50,000 | 48,500 | 1,500 | 3.0% |
| LIDAR | 50,000 | 48,500 | 1,500 | 3.0% |
| Telemetry | 50,000 | 48,500 | 1,500 | 3.0% |

**Per-type breakdown** (uniform 1% weighting per anomaly type, locked at Week 9 kickoff):

| Stream | Anomaly Type | Target Count (1% of 50,000) |
|---|---|---|
| Radar | Ghost target | 500 |
| Radar | Velocity spike | 500 |
| Radar | Sensor dropout | 500 |
| LIDAR | Noise burst | 500 |
| LIDAR | Point-cloud dropout | 500 |
| LIDAR | Ghost point | 500 |
| Telemetry | Out-of-range value | 500 |
| Telemetry | Sensor freeze | 500 |
| Telemetry | Missing reading | 500 |

**Tolerance:** M3W10T3 verification checks the *realized* injection rate is "close to" the configured 3% target (per Week 10 plan wording) — this spec sets a tolerance band of **±0.3 percentage points** (i.e., 2.7%–3.3% realized anomalous rate per stream) as passing. Anything outside that band is flagged back to Omer per the plan's existing rule (fix at the source, don't patch labels).

---

## 3. Train/Test Split Convention

| Parameter | Decision |
|---|---|
| **Split ratio** | 80% train / 20% test |
| **Stratification** | Stratified by `anomaly_type` (and implicitly by `label`, since `anomaly_type` is null only when `label=0` — normal records are stratified as their own "no-anomaly" class) |
| **Split scope** | **Per-stream** — radar, LIDAR, and telemetry are split independently, not pooled into one combined corpus before splitting |

### Resulting record counts per stream (50,000 total)

| Split | Normal | Ghost target / Noise burst / Out-of-range (500 each) | Velocity spike / PC dropout / Sensor freeze (500 each) | Sensor dropout / Ghost point / Missing reading (500 each) | Total |
|---|---|---|---|---|---|
| Train (80%) | 38,800 | 400 each (×3 types) = 1,200 | — | — | 40,000 |
| Test (20%) | 9,700 | 100 each (×3 types) = 300 | — | — | 10,000 |

(Table collapses to: **per stream**, train = 38,800 normal + 1,200 anomalous across the three types at 400 each; test = 9,700 normal + 300 anomalous across the three types at 100 each.)

**Rationale for per-stream (not combined) splitting:** Radar, LIDAR, and telemetry have structurally different fields (only the subtype-specific columns are populated per `sensor_type`) and will very likely be modeled with stream-aware features or even separate model instances at M7 — pooling before splitting risks an uneven per-stream test set if one stream's records happen to cluster differently in a combined shuffle. Per-stream splitting guarantees each stream independently hits the 80/20 target with clean anomaly-type stratification.

**Correction to a Week 9 approximate figure:** The Week 9 kickoff note estimated "~450 held out for testing" per stream as an illustrative figure only, not a locked convention. With the 80/20 split now finalized, the actual test-set anomaly count is **300 per stream** (1,500 × 20%), not 450. This spec's figures supersede the earlier illustrative estimate.

---

## 4. Downstream Use — M7 AUC / FPR Targets

The test set (300 anomalous + 9,700 normal per stream = 10,000 records/stream) is what M7 model evaluation measures AUC ≥0.85 and FPR ≤5% against, per the locked Prototype Performance Bar. 300 anomalous test examples per stream (900 total across all three streams) is the sample size available for that evaluation — worth flagging now, not discovering at M7, in case a larger anomalous test sample becomes necessary for statistically stable AUC/FPR estimates.

---

## 5. Summary — Definition of "Training-Ready"

A record is training-ready when:
1. It conforms to `sensor_schema_v1.avsc` for its `sensor_type`.
2. It carries valid `label` (0/1) and `anomaly_type` (populated iff `label=1`, one of the nine locked types) fields.
3. It has been assigned to train or test per the 80/20, per-stream, anomaly-type-stratified split above.

This is the acceptance criterion M3W10T3 (label-assignment verification) checks Omer's first labeled batches (M3W10T8) against.

---


