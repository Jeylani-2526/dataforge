# M6W26T2 — Fused-Reference Resolution Check

## Objective

Determine whether fused rows in `fused_events` resolve to live feature-bearing
rows in the source tables. This is the gate on Milestone 7 being buildable:
the feature assembly pipeline (M7W27T1) joins back through `sensor_event_id`
and `alice_event_id` to retrieve feature values and M3 ground-truth labels.
A low resolution rate would change the Week 27 approach and invalidate the
feature-access decision.

## Method

Full-table LEFT JOIN from `fused_events` to `raw_sensor_events_staging` on
`sensor_event_id` and to `raw_alice_events_staging` on `alice_event_id`.
Counts: total fused rows, resolved sensor rows, resolved alice rows, sensor
rows carrying a label, sensor rows carrying anomaly_type, sensor rows carrying
at least one feature value (range_m, centroid_x_m, or value).

Run via `docker exec` against the live TimescaleDB container (port 5434 on
host). Adminer not used — it misreports hypertable counts.

## Schema Notes

- `raw_sensor_events_staging.label` — integer, NOT NULL, default 0 (M3
  ground-truth: 0 = normal, 1 = anomalous). Present on all rows.
- `raw_sensor_events_staging.anomaly_type` — VARCHAR(50), nullable. NULL on
  normal rows; populated only on anomalous rows.
- `raw_alice_events_staging` — no anomaly label column. ALICE events carry
  physics measurements only (track_count, momentum, energy).
- Both join columns (`sensor_event_id`, `alice_event_id`) are UUID type in
  `fused_events`; source tables store `event_id` as UUID with a UNIQUE
  constraint — joins are exact and lossless.

## Results

| Metric | Count | Pct of Total |
|---|---|---|
| Total fused rows | 34,560 | 100% |
| sensor_event_id resolved to raw_sensor_events_staging | 34,560 | 100.00% |
| alice_event_id resolved to raw_alice_events_staging | 34,560 | 100.00% |
| Sensor rows carrying label (label IS NOT NULL) | 34,560 | 100.00% |
| Sensor rows carrying anomaly_type (non-NULL) | 0 | 0.00% |
| Sensor rows carrying at least one feature value | 34,560 | 100.00% |

**Note on anomaly_type = 0:** `anomaly_type` is NULL on normal rows (label=0)
by design. Its absence does not indicate missing data — it indicates that the
fused rows in this run are all normal-class events. The M3 label (`label`
column) is present on every row and is sufficient for Isolation Forest
training.

## Conclusion

**Resolution rate: 100% on both join paths.**

All 34,560 fused rows resolve to live source rows carrying feature values and
M3 ground-truth labels. The soft reference concern raised in open_items_m6.md
Item 10 (orphan risk after the M6W22T7 450,000-row staging truncation) is not
realised: no orphaned fused rows exist in the current dataset.

Milestone 7 feature assembly (M7W27T1) can proceed by joining back to source
tables at scoring time. The join-at-scoring-time route (Option A under
schema_evolution_policy.md) is confirmed viable without a schema bump to
fused_event_schema_v2.

**Executed:** 2026-11-05
**Method:** Full-table LEFT JOIN via psql in docker exec
**Gate status:** PASS — M7 feature assembly is unblocked
