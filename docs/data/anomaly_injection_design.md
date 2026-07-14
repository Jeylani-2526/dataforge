# DataForge — Anomaly Injection & Labeling Design

---

## 1. Purpose

This document defines, for each of the three synthetic sensor streams (RADAR, LIDAR, TELEMETRY), the anomaly types to inject, the target injection rate, and the label fields every generated record must carry. This design is the direct input to Omer's Week 10 label-assignment implementation (M3W10). It does **not** cover ALICE Run 1 data — that stream is real CERN data with no injection; its records carry `schema_version` only, per the Milestone 3 stream table.

---

## 2. Dictionary Alignment (Resolved)

`data_dictionary_v1.md` was found to be missing 5 sensor fields present in the locked `sensor_schema_v1.avsc` (`event_id`, `elevation_deg`, `signal_strength_db`, `scan_id`, `sequence_number`) — the same five-field count as the M2 schema-evolution violation already tracked and signed off by Abdalla. **This has been corrected**: `data_dictionary_v1.md` is now updated to v1.1 with all 24 sensor fields documented, including cross-references back to this design document for `signal_strength_db` (`sensor_dropout`) and `sequence_number` (`missing_reading`). This design document and the dictionary are now in agreement.

---

## 3. Locked Parameters (Ratified — Tuesday 7 July Kickoff)

| Parameter | Value | Notes |
|---|---|---|
| Target volume | 50,000 records/stream | Uniform across RADAR/LIDAR/TELEMETRY — deliberate prototype simplification |
| Anomaly injection rate | 3% per stream | ≈1,500 anomalies/stream; ≈450 held out for test per stream (train/test split convention itself is finalized in Week 10, not here) |
| Rate configurability | **Required** | Rate must be a configurable input in generator code (e.g. `anomaly_rate: float = 0.03`), never hardcoded — allows a post-kickoff adjustment without a rewrite |
| Continuous/repeat mode injection | **Enabled at the same 3% rate** | Per team decision: the continuous/repeat generation mode (M3W9T6, used for M5 throughput testing) injects anomalies at the same configurable rate as the fixed-file mode, using the same per-type logic below |

**Distinct from the Prototype Performance Bar throughput target (≥10,000 events/sec, locked M1).** The 50,000-record figure is a one-time labeled corpus size for M7 training; the throughput target is a sustained streaming rate tested separately in M5/M10. These are not the same number and are not to be conflated in any Week 9 output.

---

## 4. Label Fields (All Streams, All Modes)

Every generated sensor record — fixed-file or continuous, regardless of stream — carries two label fields:

| Field | Type | Rule |
|---|---|---|
| `label` | int (0 or 1) | `1` if this record was selected for anomaly injection, else `0` |
| `anomaly_type` | string \| null | One of the per-stream anomaly type identifiers below when `label = 1`; **`null` when `label = 0`** |

`anomaly_type` values use `snake_case`, consistent with `schema_conventions.md` field-naming style, and are stream-specific (a RADAR anomaly_type value never appears on a LIDAR or TELEMETRY record).

> **Note:** `label` and `anomaly_type` are **generator-assigned metadata for training/evaluation**, not part of `sensor_schema_v1.avsc` itself. They must not be added to the Avro schema — doing so would be a breaking/additive schema change requiring the full version-bump + migration-note + Abdalla sign-off process under `schema_evolution_policy.md`. They travel alongside the record in the generator's labeled output file (fixed-file mode) but are not part of the Kafka wire format.

---

## 5. Per-Stream Anomaly Design

### 5.1 RADAR

| `anomaly_type` | Fields Mutated | Injection Logic |
|---|---|---|
| `ghost_target` | `range_m`, `bearing_deg`, `elevation_deg`, `signal_strength_db` | Generate a target-like record with a `range_m`/`bearing_deg`/`elevation_deg` combination outside the sensor's realistic operating envelope, paired with an abnormally weak `signal_strength_db`. Mimics a spurious/clutter return rather than a real target. |
| `velocity_spike` | `velocity_ms` | `velocity_ms` set far outside plausible target motion for the domain; all other fields remain physically consistent (this isolates velocity as the anomalous signal for SHAP attribution). |
| `sensor_dropout` | `signal_strength_db` | `signal_strength_db` collapses toward the noise floor. Directly implements the schema's own doc-string on this field ("key SHAP feature for signal_loss anomaly pattern") — dropout *is* the signal-loss pattern the schema was designed around. |

### 5.2 LIDAR

| `anomaly_type` | Fields Mutated | Injection Logic |
|---|---|---|
| `noise_burst` | `avg_intensity`, `min_intensity`, `centroid_x_m`, `centroid_y_m`, `centroid_z_m` | Intensity fields spike with abnormal variance; centroid coordinates jitter beyond scan-to-scan continuity expected of a real scan sequence. |
| `point_cloud_dropout` | `point_count`, `min_intensity` | `point_count` collapses toward zero, `min_intensity` degrades. Implements the schema's own doc-string on `min_intensity` ("low values indicate obstruction; key SHAP feature"). |
| `ghost_point` | `point_count`, `centroid_x/y/z_m`, `max_range_m` | `point_count = 1` with a centroid/`max_range_m` combination geometrically inconsistent with a real single-point return. |

### 5.3 TELEMETRY

| `anomaly_type` | Fields Mutated | Injection Logic |
|---|---|---|
| `out_of_range_value` | `value` | `value` exceeds the physically valid bound for the record's `parameter_name` (e.g., an `engine_temp_c` reading beyond operational max). |
| `sensor_freeze` | `value` | `value` repeats identically across consecutive records for the same `device_id` + `parameter_name`, while `sequence_number` continues incrementing normally — the device keeps reporting but stops sensing. |
| `missing_reading` | `sequence_number` | A gap is introduced in `sequence_number`. Directly implements the schema's own doc-string ("a gap in sequence enables Module 5 to compute `data_loss_pct`"). |

---

## 6. Injection Mechanics (Applies to All Streams)

1. Generate the full base-signal record set (Omer's M3W9T6 scaffolding output).
2. For each record, sample from a Bernoulli distribution at the configured `anomaly_rate` (default 0.03) to determine `label`.
3. For records selected (`label = 1`), sample an `anomaly_type` from that stream's three types. **Default: uniform distribution across the three types** (≈1% of total records per type at the 3% overall rate) unless the team specifies non-uniform weighting at kickoff.
4. Apply the corresponding field mutation(s) from Section 5.
5. For records not selected (`label = 0`), leave `anomaly_type = null` and all fields at base-signal values.
6. This logic is identical for fixed-file and continuous/repeat modes — only the total record count and the file-vs-stream output target differ.

---

## 7. Open Items Carried to Week 10

- **Per-type weighting**: currently uniform (1% each of the 3 types per stream at 3% total) — confirmed as matching intent.
- **Train/test split convention** (what fraction of the ~1,500 anomalies/stream are held out, and how): explicitly scoped to Week 10 (`M3W10` — Abdalla finalizes the labeled training data specification), not decided here.

---

## 8. Distribution

Per the Week 9 plan, this design is shared with the full team by **Thursday 9 July**, giving a full working day before Omer's Week 10 label-assignment implementation begins.

*End of `anomaly_injection_design.md`*
