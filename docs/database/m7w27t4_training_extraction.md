@'
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

Split applied per stream: 80% train, 20% test, stratified by label.

| Stream | Train (80%) | Train Anomaly | Test (20%) | Test Anomaly |
|---|---|---|---|---|
| RADAR | 40,000 | 1,186 | 10,000 | 296 |
| LIDAR | 40,000 | 1,189 | 10,000 | 297 |
| TELEMETRY | 40,000 | 1,186 | 10,000 | 297 |

Test anomaly counts (296-297 per stream) match the spec's stated ~300 figure. The spec's own warning is noted: this is a small sample for a stable AUC; M7W27T2 reports confidence intervals alongside point figures.

---

## 3. Feature Columns

All three streams carry identical column sets.

**Features used for training (sensor measurement columns only):**  
`range_m`, `bearing_deg`, `elevation_deg`, `velocity_ms`, `signal_strength_db`, `scan_id`, `point_count`, `centroid_x_m`, `centroid_y_m`, `centroid_z_m`, `max_range_m`, `avg_intensity`, `min_intensity`, `value`

**Excluded from training:**  
- `event_id`, `sensor_id`, `sensor_type`, `timestamp_ms`, `device_id`, `parameter_name`, `unit`, `sequence_number`, `schema_version` -- identifiers and metadata  
- `label`, `anomaly_type` -- target columns (not features)  
- ALICE features -- excluded per M6W26T5 Decision C (68 distinct vectors, no labels, no physical relationship to sensor streams)

---

## 4. Conformance with Spec & Sign-Off

| Requirement | Source | Status |
|---|---|---|
| Per-stream corpus, 50,000 records each | `labeled_training_data_spec.md` s1 | PASS |
| Anomaly rate ~2.96-2.97% per stream | M6W26T5 E6 | PASS |
| 80/20 stratified split | `labeled_training_data_spec.md` s4 | PASS |
| Test set ~296-297 anomalies per stream | M6W26T5 s4 bar | PASS |
| Labels sourced from corpus, not live stream | M6W26T5 Decision B1 | PASS |
| ALICE excluded from training features | M6W26T5 Decision C | PASS |
| No database extraction required | M6W26T5 s8 re-scope | PASS |

---

## 5. Gate Status

**PASS** — M3 corpus class balance confirmed. 80/20 stratified split counts match spec. Feature columns identified and scoped. M7W27T2 (Isolation Forest training) is unblocked.
'@ | Out-File -Encoding utf8 docs\database\m7w27t4_training_extraction.md