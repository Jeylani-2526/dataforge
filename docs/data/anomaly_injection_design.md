# DataForge — Anomaly Injection & Labeling Design

**Document:** `anomaly_injection_design.md`
**Task ID:** M3W9T1 (amended M3W10 — see Section 9)
**Owner:** Abdalla
**Milestone:** M3 · Week 9 (amendment: Week 10)
**Version:** 1.1 — amended 20 July 2026 (v1.0 ratified 7 July 2026 kickoff)
**Status:** Locked — v1.1 supersedes v1.0 for Section 5.3 (TELEMETRY) only; all other sections unchanged
**GitHub Path:** `/docs/data/anomaly_injection_design.md`
**Depends on:** `sensor_schema_v1.avsc` (locked, authoritative), `data_dictionary_v1.md` (v1.1, corrected — see Section 2)

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

### 5.3 TELEMETRY — **Amended in v1.1 (see Section 9)**

| `anomaly_type` | Fields Mutated | Injection Logic |
|---|---|---|
| `out_of_range_value` | `value` | `value` exceeds the physically valid bound for the record's `parameter_name` (e.g., an `engine_temp_c` reading beyond operational max). |
| ~~`sensor_freeze`~~ → **`timestamp_stall`** *(replaced — v1.1)* | `timestamp_ms` | `timestamp_ms` is held at the value the generator's own deterministic formula (`base_time_ms + sequence_number × interval_ms`) would have produced for the *previous* `sequence_number`, while `sequence_number` itself continues incrementing normally. Because the generator computes `timestamp_ms` from this formula rather than from a stored prior record, the anomalous value is derivable within the single record being generated — no cross-record state is required. Simulates a device clock stall or reporting desync: the device keeps incrementing its internal counter but its timestamp source has stopped advancing. |
| `missing_reading` | `sequence_number` | A gap is introduced in `sequence_number`. Directly implements the schema's own doc-string ("a gap in sequence enables Module 5 to compute `data_loss_pct`"). |

---

## 6. Injection Mechanics (Applies to All Streams)

1. Generate the full base-signal record set (Omer's M3W9T6 scaffolding output).
2. For each record, sample from a Bernoulli distribution at the configured `anomaly_rate` (default 0.03) to determine `label`.
3. For records selected (`label = 1`), sample an `anomaly_type` from that stream's three types. **Default: uniform distribution across the three types** (≈1% of total records per type at the 3% overall rate) unless the team specifies non-uniform weighting at kickoff.
4. Apply the corresponding field mutation(s) from Section 5.
5. For records not selected (`label = 0`), leave `anomaly_type = null` and all fields at base-signal values.
6. This logic is identical for fixed-file and continuous/repeat modes — only the total record count and the file-vs-stream output target differ.
7. **(v1.1)** For `timestamp_stall` specifically: the generator must compute the intended (non-anomalous) `timestamp_ms` for the current `sequence_number` first using its standard formula, then substitute the formula's output for `sequence_number - 1` instead. This keeps the mutation deterministic and reproducible from the record's own `sequence_number` field, with no external state or lookback required.

---

## 7. Open Items

- **Per-type weighting**: currently uniform (1% each of the 3 types per stream at 3% total) — confirmed as matching intent.
- **Train/test split convention** (what fraction of the ~1,500 anomalies/stream are held out, and how): finalized in `labeled_training_data_spec.md` (M3W10T2).
- **`sensor_freeze` (deferred, not cancelled)** — see Section 9. To be revisited at M4 (Data Adaptation) or M7 (AI/ML feature engineering) planning, contingent on adding a derived temporal feature (e.g., a rolling "ticks/time since value last changed" feature per `device_id` + `parameter_name`) to the pipeline. This is out of scope for M3 data generation.

---

## 8. Distribution

Per the Week 9 plan, this design was shared with the full team on **Thursday 9 July**. This v1.1 amendment (Section 9) was shared with the team on **20 July 2026**, ahead of Omer's re-implementation work following the M3W10T3 verification failure.

---

## 9. Amendment Log

### v1.1 — 20 July 2026 — `sensor_freeze` replaced with `timestamp_stall` (TELEMETRY)

**Trigger:** M3W10T3 (Label-Assignment Verification) returned a **FAIL** to Omer on 19 July 2026, citing two blocking findings: (1) committed sample files contained no `label`/`anomaly_type` fields, and (2) the implemented anomaly taxonomy in `anomaly_injection.py` matched this design on only 1 of 9 locked `anomaly_type` values across all three streams. During root-cause review of finding (2), it was confirmed that `sensor_freeze` as originally specified is **not implementable** in the generator's current architecture, independent of the broader taxonomy fix.

**Root cause:** `sensor_freeze` was specified in v1.0 as "`value` repeats identically across **consecutive** records for the same `device_id` + `parameter_name`." This requires comparing a record to a previously generated record for the same device/parameter — i.e., cross-record state. Omer's generator (scaffolded M3W9T6, confirmed in the committed `anomaly_injection.py`) applies anomaly mutations through single-record, stateless functions (`f(record) -> record`) with no memory of prior output. The v1.0 design was locked without cross-checking this constraint against the scaffolding, which was already stateless at the time of the Week 9 kickoff.

**Secondary finding:** Even if the generator were modified to track per-device state, the resulting label would not currently be learnable downstream. Module 7 (AI/ML Anomaly Detection) is a scikit-learn Isolation Forest operating on single fused-event feature vectors (per the System Module List and `fused_event_schema_v1.avsc`); neither schema carries a derived temporal feature (e.g., "value unchanged for N samples") that would let a per-record model distinguish a genuinely frozen reading from an ordinary repeated value. Implementing `sensor_freeze` faithfully therefore requires schema and feature-engineering work in Module 3/5/7 — out of scope for M3 data generation — in addition to the generator change.

**Decision:** Replace `sensor_freeze` with `timestamp_stall` for M3 (Section 5.3). `timestamp_stall` preserves the intent of the original anomaly (device continues reporting but something has desynced) while being derivable from the record's own `sequence_number` via the generator's existing deterministic timestamp formula — no cross-record state needed, and no schema change required.

**Disposition of `sensor_freeze`:** Deferred, not dropped. Logged as an open item (Section 7) to be revisited at M4 or M7 planning alongside the temporal-feature work it depends on.

**Sign-off:** Abdalla — 20 July 2026.
**Communicated to:** Team (20 July 2026); to be included in the Week 10/11 update to Emrah as a documented, reasoned prototype scope decision, consistent with project reporting practice of surfacing gaps rather than resolving them silently.

*End of `anomaly_injection_design.md`*
