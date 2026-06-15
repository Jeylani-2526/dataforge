# DataForge — Sensor Field Specification

## Sensor Types

| Sensor Type | `sensor_type` enum | Description |
|---|---|---|
| Radar | `radar` | Radio-wave target detection — range, bearing, velocity |
| LIDAR | `lidar` | Laser-based 3D point cloud — distance and mapping |
| Telemetry | `telemetry` | Remote system status — temperature, health, performance |

> ALICE data (`source_type = alice`) is in `alice_event_schema_v0.avsc` — NOT part of this spec.

---

## Common Fields (All Sensor Types)

| # | Field Name | Data Type | Unit | Dashboard Pages | Refresh |
|---|---|---|---|---|---|
| 1 | `event_id` | string (UUID) | — | Live Stream · AI Alerts · XAI Panel · Reports | real-time / 5s |
| 2 | `sensor_id` | string | — | Fusion Monitor | 10s |
| 3 | `sensor_type` | enum (radar/lidar/telemetry) | — | All 7 pages | varies |
| 4 | `timestamp_ms` | long | ms (epoch) | Live Stream · AI Alerts · XAI Panel · Reports · Fusion Monitor | real-time |
| 5 | `schema_version` | string | — | Not displayed | — |

> **Pipeline-added fields (not in sensor Avro schema):** `latency_ms` and `data_loss_pct` are written by the ingestion pipeline at processing time (Module 3 and Module 5). They exist in the `events` TimescaleDB table but are not part of the sensor Avro schema. `quality_flag` is assigned by Module 5 based on record completeness and timestamp validity — also a pipeline-computed field, not a sensor field.

---

## Radar-Specific Fields

| # | Field Name | Data Type | Unit | Dashboard Pages | Refresh | Notes |
|---|---|---|---|---|---|---|
| 6 | `target_id` | string | — | Live Stream · Fusion Monitor | real-time / 10s | Per-scan target identifier |
| 7 | `range_m` | float | metres | Live Stream · Fusion Monitor · AI Alerts | real-time / 5s | Distance to target |
| 8 | `bearing_deg` | float | degrees (0–360) | Live Stream · Fusion Monitor | real-time / 10s | Angular direction to target |
| 9 | `elevation_deg` | float | degrees (-90–+90) | Fusion Monitor | 10s | Vertical angle |
| 10 | `velocity_ms` | float | m/s | Live Stream · AI Alerts · Reports | real-time / 5s | Radial velocity (Doppler) |
| 11 | `signal_strength_db` | float | dBm | Fusion Monitor · AI Alerts | 10s / 5s | Key SHAP feature for `signal_loss` |

> **Deferred — `scan_frequency_hz`:** Static sensor configuration metadata, not per-event data. Will be stored in a `sensor_config` database table to be designed in M4. Does not appear in the sensor Avro schema.

---

## LIDAR-Specific Fields

**Granularity: per-scan.** The LIDAR schema stores one record per scan, not one record per point — identical in principle to ALICE's per-event model. Fields are scan-level aggregates computed from the full point cloud by the synthetic generator in M3. The raw point-cloud data is not stored in the DataForge pipeline at prototype scale.

| # | Field Name | Data Type | Unit | Dashboard Pages | Refresh | Notes |
|---|---|---|---|---|---|---|
| 12 | `scan_id` | string | — | Fusion Monitor | 10s | Unique identifier for this scan |
| 13 | `point_count` | int | — | Fusion Monitor | 10s | Total points captured in this scan |
| 14 | `centroid_x` | float | metres | Fusion Monitor | 10s | Mean X position across all scan points |
| 15 | `centroid_y` | float | metres | Fusion Monitor | 10s | Mean Y position across all scan points |
| 16 | `centroid_z` | float | metres | Fusion Monitor | 10s | Mean Z / altitude across all scan points |
| 17 | `max_range_m` | float | metres | Fusion Monitor · AI Alerts | 10s / 5s | Distance to farthest detected point |
| 18 | `avg_intensity` | float | 0–255 | Fusion Monitor · AI Alerts | 10s / 5s | Mean return intensity across all scan points |
| 19 | `min_intensity` | float | 0–255 | Fusion Monitor · AI Alerts | 10s / 5s | Minimum return intensity — low value indicates obstruction; key SHAP feature |

---

## Telemetry-Specific Fields

| # | Field Name | Data Type | Unit | Dashboard Pages | Refresh | Notes |
|---|---|---|---|---|---|---|
| 20 | `device_id` | string | — | Fusion Monitor · AI Alerts | 10s / 5s | Physical device identifier |
| 21 | `parameter_name` | string | — | Live Stream · AI Alerts · XAI Panel | real-time / 5s | e.g. `cpu_temp_c`, `battery_pct` |
| 22 | `value` | float | variable | Live Stream · AI Alerts · XAI Panel · Reports | real-time / 5s | Measured value |
| 23 | `unit` | string | — | Live Stream · XAI Panel | real-time | Display only — e.g. `"°C"`, `"%"` |
| 24 | `sequence_number` | long | — | Live Stream | real-time | Gap = dropped packet → data_loss_pct |

> **Deferred — `threshold_min` / `threshold_max`:** Static per-sensor configuration values, not per-reading data. Will be stored in a `sensor_config` database table to be designed in M4. Module 5 and Module 7 will load thresholds from that table at runtime. Do not appear in the sensor Avro schema.

---

## Open Questions — All Resolved

| # | Question | Decision |
|---|---|---|
| Q1 | Nullable fields — use `["null", "float"]` union for subtype fields? | **Resolved — single unified schema.** One `.avsc` file covering all three sensor types. `sensor_type` is an enum field; all subtype-specific fields use `["null", type]` union. Abdalla implements in sensor Avro schema v1 (Week 6). |
| Q2 | `scan_frequency_hz` — per-event or per-session metadata? | **Resolved — deferred to M4.** Static config metadata → `sensor_config` table. Removed from schema. |
| Q3 | Telemetry `threshold_min/max` — sensor schema or config table? | **Resolved — deferred to M4.** Static config values → `sensor_config` table. Removed from schema. |
| Q4 | `elevation_deg` — is synthetic radar generator 2D or 3D? | **Resolved — LIDAR section replaced with per-scan aggregates.** Per-point fields removed entirely. |

---

*Beyza Ülkümen · M2W5T7 · June 2026*
