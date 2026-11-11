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

## 2. 80/20 Stratified Split

Fixed split, stratified by `anomaly_type`, seed=42. Test IDs saved to `data/splits/` for reproducibility.

| Stream | Train (80%) | Train Anomaly | Test (20%) | Test Anomaly |
|---|---|---|---|---|
| RADAR | 40,000 | 1,186 | 10,000 | 296 |
| LIDAR | 40,000 | 1,189 | 10,000 | 297 |
| TELEMETRY | 40,000 | 1,186 | 10,000 | 297 |

Per-type counts (make_split.py, seed=42):

| Stream | Type | Train | Test |
|---|---|---|---|
| RADAR | ghost_target | 410 | 103 |
| RADAR | normal | 38,815 | 9,703 |
| RADAR | sensor_dropout | 398 | 100 |
| RADAR | velocity_spike | 377 | 94 |
| LIDAR | ghost_point | 398 | 100 |
| LIDAR | noise_burst | 402 | 100 |
| LIDAR | normal | 38,811 | 9,703 |
| LIDAR | point_cloud_dropout | 389 | 97 |
| TELEMETRY | missing_reading | 372 | 93 |
| TELEMETRY | normal | 38,813 | 9,704 |
| TELEMETRY | out_of_range_value | 397 | 99 |
| TELEMETRY | timestamp_stall | 418 | 104 |

---

## 3. Class Balance Approach

SMOTE degerlendiridi ve reddedildi (Abdalla, 9 Kasim 2026).

Isolation Forest denetimsiz bir model ve anomalilerin nadir olmasina dayanir.
%50 dengeli egitim (SMOTE veya gercek veri) FPR'yi %13-26'ya cikariyor.

| Yaklasim | RADAR FPR | LIDAR FPR |
|---|---|---|
| Dogal ~%3 (mevcut) | %0.4 PASS | %0.5 PASS |
| SMOTE %50 | %18.3 FAIL | %25.8 FAIL |
| Gercek %50 veri | %13.5 FAIL | %24.8 FAIL |

Karar: Train seti dogal ~%3 oraninda kalir. Dengesizlik AUC/FPR ve anomaly_type basina recall ile olcularak yonetilir.

---

## 4. Feature Columns

Gecici -- kesin liste M7W27T1'de belirlenecek.

All three streams carry identical column sets.

**Features used for training (sensor measurement columns only):**
`range_m`, `bearing_deg`, `elevation_deg`, `velocity_ms`, `signal_strength_db`, `scan_id`, `point_count`, `centroid_x_m`, `centroid_y_m`, `centroid_z_m`, `max_range_m`, `avg_intensity`, `min_intensity`, `value`

**Excluded from training:**
- `event_id`, `sensor_id`, `sensor_type`, `timestamp_ms`, `device_id`, `parameter_name`, `unit`, `sequence_number`, `schema_version` -- identifiers and metadata
- `label`, `anomaly_type` -- target columns (not features)
- ALICE features -- excluded per M6W26T5 Section 4

---

## 5. Conformance with Spec & Sign-Off

| Requirement | Source | Status |
|---|---|---|
| Per-stream corpus, 50,000 records each | labeled_training_data_spec.md s1 | PASS |
| Anomaly rate ~2.96-2.97% per stream | M6W26T5 E6 | PASS |
| 80/20 stratified split, stratified by anomaly_type, seed=42 | labeled_training_data_spec.md s3 | PASS |
| Test set ~296-297 anomalies per stream | M6W26T5 s4 bar | PASS |
| Train set dogal ~%3 (SMOTE reddedildi) | Abdalla, 9 Kasim 2026 | PASS |
| Labels sourced from corpus, not live stream | M6W26T5 Decision B1 | PASS |
| ALICE excluded from training features | M6W26T5 Section 4 | PASS |
| Test IDs saved to data/splits/ | make_split.py | PASS |

---

## 6. Gate Status

**PASS** -- M3 corpus class balance confirmed. 80/20 stratified split saved to data/splits/ (seed=42, stratified by anomaly_type). SMOTE rejected -- train set retains natural ~3% anomaly rate. M7W27T2 (Isolation Forest training) unblocked.
