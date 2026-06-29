# DataForge — Data Dictionary

**Document version:** 1.0 (in progress — fused event section to be completed in Week 8)
**Scope:** All fields across all three locked DataForge Avro schemas

| Schema | File | Status in this document |
|---|---|---|
| ALICE event | `alice_event_schema_v1.avsc` | ✓ Complete (10 fields) |
| Sensor | `sensor_schema_v1.avsc` | ✓ Complete (19 fields across 3 subtypes) |
| Fused event | `fused_event_schema_v1.avsc` | ⏳ Placeholder — to be completed in Week 8 |

---

> **How to read this document**
> Each field entry records: the exact Avro field name (as it appears in the `.avsc` file and in every serialized record), the Avro type, a plain-language description written for a non-specialist reader, the unit of measurement (or "—" for dimensionless fields), and the DataForge module number that first produces or assigns the field. Module numbers follow the System Module List (Module 1 = ALICE source, Module 2 = Sensor source, Module 3 = Data Adaptation, etc.).

---

## Section 1 — ALICE Event Schema

**Schema file:** `alice_event_schema_v1.avsc`
**Namespace:** `dataforge.alice`
**Record name:** `AliceEvent`
**Granularity:** One record per ALICE collision event (per-event aggregates — not per individual particle track)
**ROOT source:** `AliESDs.root` · tree `esdTree` · run 139038 · LHC10h (Pb-Pb, 2.76 TeV)

Fields are organised as: system-assigned fields first, then ROOT-readable fields, then ROOT/PyROOT-derived fields, then schema metadata.

| Field Name | Avro Type | Unit | Description | Source Module |
|---|---|---|---|---|
| `event_id` | `string` (UUID v4) | — | Unique identifier for this ALICE collision event. Generated as a UUID v4 string by the Data Adaptation layer at ingestion time — there is no equivalent identifier in the ROOT file. Used as the primary key in the TimescaleDB `events` hypertable and as a foreign key in `fused_events`. Assignment method: `str(uuid.uuid4())` called once per event at ingestion. | 3 |
| `run_number` | `int` | — | The ALICE experimental run identifier, read directly from the ROOT file field `AliESDRun.fRunNumber`. Identifies which data-taking period this event belongs to. DataForge uses run 139038 (LHC10h, Pb-Pb collisions, 2010). All 228 prototype events share the same run number. | 1 |
| `timestamp_ms` | `long` | ms | Event timestamp in milliseconds since the Unix epoch, assigned by the Data Adaptation layer. Derived from `AliESDHeader.fTimeStamp` (a Unix timestamp in whole seconds) multiplied by 1000. Within the same second, events are ordered using `AliESDHeader.fEventNumberInFile` as a sub-second offset (`% 1000`) to ensure every event has a unique millisecond timestamp. Precision: ±1 ms (software clock; no hardware PTP synchronization is used in the prototype). | 3 |
| `track_count` | `int` | — | Number of charged particle tracks reconstructed in this collision event. Read directly from the ROOT file as the length of the per-event track array `Tracks/Tracks.fFlags`. Higher track counts indicate more energetic or more central collisions. A zero value is valid and handled: all derived momentum and energy fields are set to 0.0. | 1 |
| `net_momentum_x` | `float` | GeV/c | Sum of the x-component of momentum across all reconstructed tracks in the event, in GeV/c. Requires ROOT/PyROOT extraction — the underlying branch `Tracks/Tracks.fP[5]` uses `Double32_t` compression that uproot cannot decode. Derivation formula: `Σ ( |1/fP[4]_i| × cos(fAlpha_i + arcsin(fP[2]_i)) )` where `fP[4]` = signed inverse transverse momentum, `fP[2]` = sin(ϕ) in local frame, `fAlpha` = local-to-global frame rotation angle. In a symmetric Pb-Pb collision, this value is expected to be near zero across many events. See `root_to_avro_mapping.md §3.3` for the complete formula and `§4` for the reference extraction script. | 3 |
| `net_momentum_y` | `float` | GeV/c | Sum of the y-component of momentum across all reconstructed tracks in the event, in GeV/c. Requires ROOT/PyROOT extraction — same `Double32_t` constraint as `net_momentum_x`. Derivation formula: `Σ ( |1/fP[4]_i| × sin(fAlpha_i + arcsin(fP[2]_i)) )`. Like `net_momentum_x`, this is expected to be near zero on average across symmetric collisions. See `root_to_avro_mapping.md §3.4`. | 3 |
| `net_momentum_z` | `float` | GeV/c | Sum of the z-component of momentum across all reconstructed tracks in the event, in GeV/c. The z-axis aligns with the LHC beam direction. Requires ROOT/PyROOT extraction. Derivation formula: `Σ ( |1/fP[4]_i| × fP[3]_i )` where `fP[3]` = tan(λ) = pz / pt. Important: `fP[1]` in the ROOT parameter array is a local spatial coordinate (cm), not the z-momentum — do not confuse the two. See `root_to_avro_mapping.md §3.5`. | 3 |
| `max_energy_gev` | `float` | GeV | Energy of the single highest-energy reconstructed track in the event, in GeV. Requires ROOT/PyROOT extraction. Derivation formula: `max( sqrt(px_i² + py_i² + pz_i² + M_PION²) )` where `M_PION = 0.13957 GeV/c²`. Pion mass is applied to all unidentified tracks — the standard ALICE convention for prototype-level analysis where full particle identification is not available. See `root_to_avro_mapping.md §3.6`. | 3 |
| `total_energy_gev` | `float` | GeV | Sum of energy across all reconstructed tracks in the event, in GeV. Provides an event-level measure of total collision energy deposited in the detector. Requires ROOT/PyROOT extraction. Derivation formula: `Σ sqrt(px_i² + py_i² + pz_i² + 0.13957²)`. Uses the same pion mass convention as `max_energy_gev`. See `root_to_avro_mapping.md §3.7`. | 3 |
| `schema_version` | `string` | — | Version of the ALICE event Avro schema used to encode this record, in MAJOR.MINOR format. Hardcoded to `"1.0"` at ingestion for all records produced against the locked schema. A MINOR increment (e.g. `"1.1"`) indicates a backward-compatible addition; a MAJOR increment (e.g. `"2.0"`) indicates a breaking change and would require a new schema file and Kafka topic. See `schema_evolution_policy.md` for versioning rules. | 3 |

### ALICE Section — Notes

- **Derived fields and float32 precision:** `net_momentum_x/y/z`, `max_energy_gev`, and `total_energy_gev` are stored as Avro `float` (32-bit). The ROOT extraction computes these in 64-bit double precision; truncation to float32 occurs at serialization. Test records for these fields must use float32-safe values to avoid fastavro round-trip precision mismatches.
- **Zero-track events:** When `track_count = 0`, all five derived fields (`net_momentum_x/y/z`, `max_energy_gev`, `total_energy_gev`) are set to `0.0`. This is the defined behaviour — not a data error.
- **Cross-check:** TRD track pt values (`TrdTracks/TrdTracks.fPt`, directly uproot-readable) can be used to verify PyROOT-derived momentum magnitudes within ~5%. See `root_to_avro_mapping.md §6`.

---

## Section 2 — Sensor Schema

**Schema file:** `sensor_schema_v1.avsc`
**Namespace:** `dataforge.sensor`
**Record name:** `SensorEvent`
**Structure:** One unified schema file with a `sensor_type` enum and union fields. Subtype-specific fields are present (non-null) only for their own sensor type — all other subtype fields carry `null`.
**Data source:** Synthetic Python generators (Module 2). No physical hardware.

### 2.1 Common Fields

These four fields are present and non-null in every sensor record regardless of `sensor_type`.

| Field Name | Avro Type | Unit | Description | Source Module |
|---|---|---|---|---|
| `sensor_id` | `string` (UUID v4) | — | Unique identifier for the physical sensor device (or synthetic sensor instance) that produced this record, generated as a UUID v4 string by the synthetic data generator. Identifies which sensor unit reported this measurement. Distinct from `device_id` (Telemetry subtype) — `sensor_id` identifies the sensor hardware unit; `device_id` identifies a subsystem being monitored by that sensor. | 2 |
| `timestamp_ms` | `long` | ms | Sensor measurement timestamp in milliseconds since the Unix epoch, assigned by the synthetic data generator using a software clock. Precision: ±1 ms, consistent with the ALICE event timestamp precision to enable the stream-stream join in Module 6. | 2 |
| `sensor_type` | `enum` (`RADAR` \| `LIDAR` \| `TELEMETRY`) | — | Identifies the category of sensor that produced this record. Determines which subtype-specific fields are populated (non-null) and which carry `null` values. Used by Module 6 for fusion routing — each sensor type is matched to ALICE events independently — and by Module 7 for per-type anomaly analysis. | 2 |
| `schema_version` | `string` | — | Version of the sensor Avro schema used to encode this record, in MAJOR.MINOR format. Assigned by the Data Adaptation layer (Module 3) at serialization time. Current locked version: `"1.0"`. See `schema_evolution_policy.md` for versioning rules. | 3 |

---

### 2.2 RADAR Subtype Fields

Present (non-null) when `sensor_type = RADAR`. Set to `null` in LIDAR and TELEMETRY records.
Avro type for all subtype fields: `["null", <type>]` with `default: null`.

| Field Name | Avro Type | Unit | Description | Source Module |
|---|---|---|---|---|
| `target_id` | `["null", "string"]` | — | Identifier for the radar-detected target, assigned by the synthetic radar generator. Allows tracking of the same physical target across consecutive radar scans. Null for LIDAR and TELEMETRY records. | 2 |
| `range_m` | `["null", "float"]` | m | Estimated slant distance from the radar sensor to the detected target, in metres. Null for LIDAR and TELEMETRY records. | 2 |
| `bearing_deg` | `["null", "float"]` | degrees | Horizontal angle to the detected target measured clockwise from north, in degrees (range 0–360). Null for LIDAR and TELEMETRY records. | 2 |
| `velocity_ms` | `["null", "float"]` | m/s | Radial velocity of the detected target relative to the sensor, in metres per second. Positive values indicate the target is moving away from the sensor; negative values indicate approach. Null for LIDAR and TELEMETRY records. | 2 |

---

### 2.3 LIDAR Subtype Fields — Scan-Level Aggregates

Present (non-null) when `sensor_type = LIDAR`. Set to `null` in RADAR and TELEMETRY records.
**Granularity note:** All LIDAR fields are scan-level aggregates — individual point cloud coordinates are not stored. One record represents one complete LIDAR scan, summarised into the seven aggregate fields below.
Avro type for all subtype fields: `["null", <type>]` with `default: null`.

| Field Name | Avro Type | Unit | Description | Source Module |
|---|---|---|---|---|
| `point_count` | `["null", "int"]` | — | Total number of point returns captured in this LIDAR scan. Gives a measure of scan density. Individual point coordinates are not retained in this schema — only scan-level aggregates are stored. Null for RADAR and TELEMETRY records. | 2 |
| `centroid_x_m` | `["null", "float"]` | m | X-coordinate of the geometric centroid (average position) of all point returns in this scan, in metres. Represents the approximate horizontal centre of the scanned scene along the x-axis. Null for RADAR and TELEMETRY records. | 2 |
| `centroid_y_m` | `["null", "float"]` | m | Y-coordinate of the geometric centroid of all point returns in this scan, in metres. Represents the approximate horizontal centre of the scanned scene along the y-axis. Null for RADAR and TELEMETRY records. | 2 |
| `centroid_z_m` | `["null", "float"]` | m | Z-coordinate (height) of the geometric centroid of all point returns in this scan, in metres. Represents the approximate vertical centre of the scanned scene. Null for RADAR and TELEMETRY records. | 2 |
| `max_range_m` | `["null", "float"]` | m | Maximum distance from the sensor to any single point return in this scan, in metres. Indicates the furthest extent of the scanned scene. Null for RADAR and TELEMETRY records. | 2 |
| `avg_intensity` | `["null", "float"]` | — | Mean return intensity of all point returns in this scan. Intensity is a unitless reflectance value produced by the synthetic LIDAR generator; higher values indicate more reflective surfaces. Null for RADAR and TELEMETRY records. | 2 |
| `min_intensity` | `["null", "float"]` | — | Minimum return intensity among all point returns in this scan. Together with `avg_intensity`, provides a basic characterisation of the intensity distribution across the scan. Null for RADAR and TELEMETRY records. | 2 |

---

### 2.4 TELEMETRY Subtype Fields

Present (non-null) when `sensor_type = TELEMETRY`. Set to `null` in RADAR and LIDAR records.
Avro type for all subtype fields: `["null", <type>]` with `default: null`.

| Field Name | Avro Type | Unit | Description | Source Module |
|---|---|---|---|---|
| `device_id` | `["null", "string"]` | — | Identifier for the subsystem or device being monitored, assigned by the synthetic telemetry generator (for example, `"engine_unit_3"` or `"fuel_pump_A"`). Distinct from `sensor_id` — `sensor_id` identifies the telemetry sensor hardware; `device_id` identifies the subsystem it is monitoring. Null for RADAR and LIDAR records. | 2 |
| `parameter_name` | `["null", "string"]` | — | Name of the telemetry parameter being reported in this record (for example, `"engine_temp_c"`, `"fuel_pressure_bar"`, `"rpm"`). The unit of the corresponding `value` field is determined by this field. Null for RADAR and LIDAR records. | 2 |
| `value` | `["null", "float"]` | variable (see `parameter_name`) | Measured value of the telemetry parameter. The unit is defined by the `parameter_name` field — for example, a value of `85.0` with `parameter_name = "engine_temp_c"` means 85 degrees Celsius. Null for RADAR and LIDAR records. | 2 |
| `unit` | `["null", "string"]` | — | Unit of measurement for the `value` field, expressed as a plain string (for example, `"celsius"`, `"bar"`, `"rpm"`). Included explicitly alongside `parameter_name` so API consumers do not need to maintain a parameter-to-unit lookup table. Null for RADAR and LIDAR records. | 2 |

### Sensor Section — Notes

- **Union field test coverage:** Omer's validation suite must test each subtype with a separate test record. For each record, the current subtype's fields are populated; all other subtype fields must be explicitly set to `null`. Both the null and non-null code paths in the Avro union must be exercised to confirm round-trip integrity.
- **quality_flag is absent from this schema:** The `quality_flag` field is computed by Module 5 (Cleaning & Sync) after ingestion and stored as a pipeline-computed column on the TimescaleDB `events` table only. It is not a sensor-produced value and does not appear in the sensor Avro schema.
- **sensor_config fields deferred:** Fields such as `scan_frequency_hz`, `threshold_min`, and `threshold_max` are deferred to Milestone 4. They do not appear in this schema.

---

## Section 3 — Fused Event Schema

**Schema file:** `fused_event_schema_v1.avsc`
**Namespace:** `dataforge.fused`
**Record name:** `FusedEvent`

> ⏳ **This section is a placeholder. It will be completed in Week 8 (M2W8) once the fused event schema v1 is fully confirmed post-lock.**
>
> The fused event schema has nine fields: `fused_event_id`, `alice_event_id`, `sensor_event_id`, `timestamp_ms`, `fusion_window_ms`, `sensor_type`, `data_loss_pct`, `latency_ms`, and `schema_version`. Field-level dictionary entries — including source module assignments and plain-language descriptions — will be added here during the Week 8 data dictionary completion task (M2W8, Abdullah).

---
