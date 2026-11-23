# M6W22T6 — Fused-Record Conformance Check

## Objective

Verify that rows written to `fused_events` by `fused_writer.py` conform to the
`fused_event_schema_v1.avsc` field contract. Checks run field-by-field against
the first batch of live rows.

---

## Fields Under Check

| Field | Type | Constraint | Check |
|---|---|---|---|
| `fused_event_id` | UUID | NOT NULL, unique per row | valid UUID4, no duplicates in sample |
| `alice_event_id` | UUID | NOT NULL | valid UUID format |
| `sensor_event_id` | UUID | NOT NULL | valid UUID format |
| `timestamp_ms` | BIGINT | NOT NULL | > 0, within ±1h of now at write time |
| `fusion_window_ms` | INTEGER | DEFAULT 500 | == 500 (env default) |
| `sensor_type` | VARCHAR(20) | NOT NULL | one of RADAR, LIDAR, TELEMETRY |
| `data_loss_pct` | REAL | NOT NULL, DEFAULT 0.0 | 0.0 ≤ x ≤ 100.0 |
| `latency_ms` | BIGINT | NOT NULL, DEFAULT 0 | ≥ 0 |
| `schema_version` | VARCHAR(10) | NOT NULL, DEFAULT '1.0' | == '1.0' |

M7 nullable columns (`anomaly_label`, `risk_score`, `confidence`) are expected NULL — flagged if non-null.

---

## How to Run

```bash
python services/fusion/check_fused_conformance.py
```

---

## Results

| Check | Result | Detail |
|---|---|---|
| Row count | PASS | 34,560 rows in fused_events |
| UUID validity — fused_event_id | PASS | all 1,000 sampled rows valid UUID |
| UUID validity — alice_event_id | PASS | all 1,000 sampled rows valid UUID |
| UUID validity — sensor_event_id | PASS | all 1,000 sampled rows valid UUID |
| timestamp_ms range | PASS | all 1,000 rows > 0 |
| fusion_window_ms value | PASS | all 1,000 rows == 500 |
| sensor_type enum | PASS | all 1,000 rows in {RADAR, LIDAR, TELEMETRY} |
| data_loss_pct range | PASS | all 1,000 rows in [0.0, 100.0] |
| latency_ms non-negative | PASS | all 1,000 rows >= 0 |
| schema_version value | PASS | all 1,000 rows == '1.0' |
| M7 columns null — anomaly_label | PASS | all 1,000 rows NULL (M7 not yet run) |
| M7 columns null — risk_score | PASS | all 1,000 rows NULL (M7 not yet run) |
| M7 columns null — confidence | PASS | all 1,000 rows NULL (M7 not yet run) |
| Duplicate fused_event_id | PASS | 0 duplicates across full table (34,560 rows) |

**Executed:** 2026-11-05
**Row sample size:** 1,000 (of 34,560 total)
**Pass / Fail:** PASS
