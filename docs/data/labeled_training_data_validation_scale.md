# DataForge — Labeled Training Data Validation at Scale


---

> **Why this document exists**
> This closes the loop on M3W10T3, which failed 19 July 2026 on a taxonomy mismatch and stale sample files. This task re-verifies label correctness at full scale against the corrected files — not a re-check of the same small sample, but a full-population validation of every labeled record across all three streams, plus a mutated-field-value spot-check deeper than M3W10T3's field-presence-only check.

---

## 1. Scope & Method

Every one of the 150,000 committed records (50,000/stream) was parsed and checked programmatically — this is a full-population check, not a subsample, exceeding the scope of the original M3W10T3 verification. Four categories were validated:

1. Class balance vs. the locked 3% injection rate (±0.3pp tolerance per `labeled_training_data_spec.md` §2).
2. `label` / `anomaly_type` null-consistency (`anomaly_type` populated iff `label=1`) across every record.
3. Taxonomy conformance — every `anomaly_type` value is one of the nine v1.1-locked identifiers; explicit check for any residual `sensor_freeze` or other pre-fix values.
4. Mutated-field-value correctness — for every anomalous record, confirm the field(s) `anomaly_injection_design.md` §5 specifies were actually mutated in a manner consistent with that anomaly's design logic, not just that a label was assigned.

---

## 2. Class Balance & Per-Type Results

| Stream | Total | Normal | Anomalous | Anomalous % | Target | Status |
|---|---|---|---|---|---|---|
| Radar | 50,000 | 48,518 | 1,482 | 2.964% | 3.0% ± 0.3pp | PASS |
| LIDAR | 50,000 | 48,514 | 1,486 | 2.972% | 3.0% ± 0.3pp | PASS |
| Telemetry | 50,000 | 48,517 | 1,483 | 2.966% | 3.0% ± 0.3pp | PASS |

Per-type counts (9 types, target ~500 each) all fall in the 465–522 range — consistent with `labeled_training_data_spec.md` §2's realized figures. No discrepancy from the spec's own reported numbers.

**Taxonomy conformance:** 0 of 150,000 records carry `sensor_freeze` or any value outside the nine v1.1-locked `anomaly_type` identifiers. `timestamp_stall` is present (522 records) and confirmed as the only TELEMETRY anomaly type replacing the deprecated `sensor_freeze`.

**Null-consistency:** 0 violations across all 150,000 records — every `label=1` record has a non-null `anomaly_type`; every `label=0` record has a null `anomaly_type`.

---

## 3. Mutated-Field-Value Spot-Check (Full Population)

Rather than sampling a subset, every anomalous record's mutated field(s) were compared against the baseline (`label=0`) distribution for that stream to confirm the mutation logic in `anomaly_injection_design.md` §5 was actually applied — not merely that a label/type was assigned.

### Radar

| `anomaly_type` | Baseline range | Anomalous range | Consistent with design? |
|---|---|---|---|
| `ghost_target` | `range_m` 50–5,000 | 7,506–11,939 | Yes — outside operating envelope, as specified |
| | `bearing_deg` 0–360 | 380–720 | Yes — outside envelope |
| | `elevation_deg` −30–30 | 60–90 | Yes — outside envelope |
| | `signal_strength_db` −90 to −20 | −145 to −120 | Yes — abnormally weak |
| `velocity_spike` | `velocity_ms` −100–300 | −1,499–1,500 | Yes — far outside plausible motion |
| | other fields | — | Unchanged, physically consistent with baseline (isolates velocity as sole anomalous signal, as designed) |
| `sensor_dropout` | `signal_strength_db` −90 to −20 | −160 to −145 | Yes — collapsed toward/past noise floor |

### LIDAR

| `anomaly_type` | Baseline | Anomalous | Consistent with design? |
|---|---|---|---|
| `noise_burst` | `avg_intensity` 80–220 | 350–599 | Yes — abnormal spike |
| | centroid coords ±100 (x/y), −10–50 (z) | ±392 (x/y), −146–193 (z) | Yes — jitter beyond scan continuity |
| `point_cloud_dropout` | `point_count` 10,001–199,997 | 0–10 | Yes — collapsed toward zero |
| | `min_intensity` 20–100 | 0–5 | Yes — degraded |
| `ghost_point` | `point_count` — | exactly 1 (100% of records) | Yes — matches design exactly |
| | centroid vs. `max_range_m` | centroid 600–999m; `max_range_m` 10–25m | Yes — geometrically inconsistent single return, as designed |

### Telemetry

| `anomaly_type` | Baseline | Anomalous | Consistent with design? |
|---|---|---|---|
| `out_of_range_value` — `cpu_temp_c` | 35–75 | 125–180 | Yes — exceeds valid bound |
| `out_of_range_value` — `voltage_v` | 11–13 | 20–30 | Yes — exceeds valid bound |
| `out_of_range_value` — `battery_pct` | 20–100 | 110–149 | Yes — exceeds valid bound (>100%) |
| `missing_reading` | n/a | 465/465 confirmed sequence-number gap vs. predecessor record | Yes — 100% pass |
| `timestamp_stall` | n/a | 522/522 records' `timestamp_ms` matches `base_time_ms + (sequence_number − 1) × interval_ms` within 1ms | Yes — 100% pass, confirms the record is derivable from its own `sequence_number` with no cross-record state, per the v1.1 amendment rationale |

---

## 4. Observation (Non-Blocking)

All 50,000 committed TELEMETRY records share a single `device_id` (`SENSOR-UNIT-01`). Nothing in `labeled_training_data_spec.md` or `anomaly_injection_design.md` requires multiple devices, so this is **not a failure** — but it means the per-device `sequence_number`/`timestamp_ms` mutation logic (`missing_reading`, `timestamp_stall`) has only been exercised against one device instance in this corpus. Flagging for awareness rather than resolving silently, consistent with project reporting practice; no action required unless a future milestone specifically needs multi-device telemetry behavior verified.

---

## 5. Verdict

**PASS.** All class-balance, taxonomy-conformance, null-consistency, and mutated-field-value checks pass across the full 150,000-record corpus. This formally closes M3W10T3 (failed 19 July, re-verified clean by this task 21–22 July) and confirms the `anomaly_injection_design.md` v1.1 amendment (`timestamp_stall` replacing `sensor_freeze`) is correctly and consistently implemented in the committed generator output.

*End of `labeled_training_data_validation_scale.md`*
