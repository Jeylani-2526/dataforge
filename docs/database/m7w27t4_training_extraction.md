# M7W27T4 — Training Set Extraction & Class Balance

---

## 1. Corpus Summary

| Stream | Total Records | Normal (label=0) | Anomaly (label=1) | Anomaly % |
|---|---|---|---|---|
| RADAR | 50,000 | 48,518 | 1,482 | 2.96% |
| LIDAR | 50,000 | 48,514 | 1,486 | 2.97% |
| TELEMETRY | 50,000 | 48,517 | 1,483 | 2.97% |
| **Total** | **150,000** | **145,549** | **4,451** | **2.97%** |

---

## 2. 80/20 Stratified Split (before SMOTE)

| Stream | Train (80%) | Train Anomaly | Test (20%) | Test Anomaly |
|---|---|---|---|---|
| RADAR | 40,000 | 1,186 | 10,000 | 296 |
| LIDAR | 40,000 | 1,189 | 10,000 | 297 |
| TELEMETRY | 40,000 | 1,186 | 10,000 | 297 |

Test set is not touched by SMOTE -- it reflects the real class distribution (~2.97% anomaly).

---

## 3. SMOTE Oversampling (train set only)

SMOTE (Synthetic Minority Oversampling Technique, k=5 neighbors, random_state=42) applied to train set only. Target ratio: 1.0 (50/50). Test set unchanged.

| Stream | Train before SMOTE | Train after SMOTE | Anomaly % after |
|---|---|---|---|
| RADAR | 40,000 (1,186 anom / 38,814 normal) | 77,628 (38,814 / 38,814) | 50.00% |
| LIDAR | 40,000 (1,189 anom / 38,811 normal) | 77,622 (38,811 / 38,811) | 50.00% |
| TELEMETRY | 40,000 (1,186 anom / 38,814 normal) | 77,628 (38,814 / 38,814) | 50.00% |

Verification: 37,628 synthetic anomaly rows generated for RADAR (confirmed distinct from originals). SMOTE execution time: ~0.05s per stream (numpy matrix operation, not file I/O).

---

## 4. Feature Columns

All three streams carry identical column sets.

**Features used for training (sensor measurement columns only):**  
`range_m`, `bearing_deg`, `elevation_deg`, `velocity_ms`, `signal_strength_db`, `scan_id`, `point_count`, `centroid_x_m`, `centroid_y_m`, `centroid_z_m`, `max_range_m`, `avg_intensity`, `min_intensity`, `value`

**Excluded from training:**  
- `event_id`, `sensor_id`, `sensor_type`, `timestamp_ms`, `device_id`, `parameter_name`, `unit`, `sequence_number`, `schema_version` -- identifiers and metadata  
- `label`, `anomaly_type` -- target columns (not features)  
- ALICE features -- excluded per M6W26T5 Decision C

---

## 5. Conformance with Spec & Sign-Off

| Requirement | Source | Status |
|---|---|---|
| Per-stream corpus, 50,000 records each | `labeled_training_data_spec.md` s1 | PASS |
| Anomaly rate ~2.96-2.97% per stream | M6W26T5 E6 | PASS |
| 80/20 stratified split | `labeled_training_data_spec.md` s3 | PASS |
| Test set ~296-297 anomalies per stream | M6W26T5 s4 bar | PASS |
| Train set class-balanced via SMOTE 50/50 | `labeled_training_data_spec.md` s3, Abdalla approval 2026-11-06 | PASS |
| Labels sourced from corpus, not live stream | M6W26T5 Decision B1 | PASS |
| ALICE excluded from training features | M6W26T5 Decision C | PASS |

---

## 6. Gate Status

**PASS** -- M3 corpus class balance confirmed. 80/20 stratified split counts match spec. SMOTE applied to train set (50/50), test set reflects real distribution. M7W27T2 (Isolation Forest training) unblocked.
