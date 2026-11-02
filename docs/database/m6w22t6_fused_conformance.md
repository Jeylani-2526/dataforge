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
| Row count | — | — |
| UUID validity | — | — |
| timestamp_ms range | — | — |
| fusion_window_ms value | — | — |
| sensor_type enum | — | — |
| data_loss_pct range | — | — |
| latency_ms non-negative | — | — |
| schema_version value | — | — |
| M7 columns null | — | — |
| Duplicate fused_event_id | — | — |

**Executed:** —
**Row sample size:** —
**Pass / Fail:** —
