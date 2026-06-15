# DataForge — Sensor Field Specification


---

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
| 5 | `quality_flag` | enum (clean/incomplete/dropout) | — | Live Stream · Fusion Monitor | real-time / 10s |
| 6 | `data_loss_pct` | float | % | Fusion Monitor · Performance · Reports | 10s / 30s |
| 7 | `latency_ms` | float | ms | Fusion Monitor · Performance · Reports | 10s / 30s |
| 8 | `schema_version` | string | — | Not displayed | — |

---

## Radar-Specific Fields

| # | Field Name | Data Type | Unit | Dashboard Pages | Refresh | Notes |
|---|---|---|---|---|---|---|
| 9 | `target_id` | string | — | Live Stream · Fusion Monitor | real-time / 10s | Per-scan target identifier |
| 10 | `range_m` | float | metres | Live Stream · Fusion Monitor · AI Alerts | real-time / 5s | Distance to target |
| 11 | `bearing_deg` | float | degrees (0–360) | Live Stream · Fusion Monitor | real-time / 10s | Angular direction to target |
| 12 | `elevation_deg` | float | degrees (-90–+90) | Fusion Monitor | 10s | Vertical angle |
| 13 | `velocity_ms` | float | m/s | Live Stream · AI Alerts · Reports | real-time / 5s | Radial velocity (Doppler) |
| 14 | `signal_strength_db` | float | dBm | Fusion Monitor · AI Alerts | 10s / 5s | Key SHAP feature for `signal_loss` |
| 15 | `scan_frequency_hz` | float | Hz | Performance | 30s | Expected event rate |

---

## LIDAR-Specific Fields

| # | Field Name | Data Type | Unit | Dashboard Pages | Refresh | Notes |
|---|---|---|---|---|---|---|
| 16 | `point_id` | string | — | Fusion Monitor | 10s | Point identifier within scan |
| 17 | `x_m` | float | metres | Fusion Monitor | 10s | X coordinate, sensor frame |
| 18 | `y_m` | float | metres | Fusion Monitor | 10s | Y coordinate, sensor frame |
| 19 | `z_m` | float | metres | Fusion Monitor | 10s | Z coordinate (altitude) |
| 20 | `intensity` | float | 0–255 | Fusion Monitor · AI Alerts | 10s / 5s | Low = obstruction. Anomaly feature. |
| 21 | `scan_id` | string | — | Fusion Monitor | 10s | Groups points from one scan |
| 22 | `return_number` | int | — | Fusion Monitor | 10s | 1=first/closest, last=farthest |

---

## Telemetry-Specific Fields

| # | Field Name | Data Type | Unit | Dashboard Pages | Refresh | Notes |
|---|---|---|---|---|---|---|
| 23 | `device_id` | string | — | Fusion Monitor · AI Alerts | 10s / 5s | Physical device identifier |
| 24 | `parameter_name` | string | — | Live Stream · AI Alerts · XAI Panel | real-time / 5s | e.g. `cpu_temp_c`, `battery_pct` |
| 25 | `value` | float | variable | Live Stream · AI Alerts · XAI Panel · Reports | real-time / 5s | Measured value |
| 26 | `unit` | string | — | Live Stream · XAI Panel | real-time | Display only — e.g. `"°C"`, `"%"` |
| 27 | `threshold_min` | float | (same as `unit`) | AI Alerts · Performance | 5s / 30s | `value < threshold_min` → anomaly |
| 28 | `threshold_max` | float | (same as `unit`) | AI Alerts · Performance | 5s / 30s | `value > threshold_max` → anomaly |
| 29 | `sequence_number` | long | — | Live Stream | real-time | Gap = dropped packet → data_loss_pct |

---

## Open Questions for Abdalla

| # | Question | Impact |
|---|---|---|
| Q1 | Nullable fields — use `["null", "float"]` union for subtype fields? | Schema structure |
| Q2 | `scan_frequency_hz` — per-event or per-session metadata? | Write volume |
| Q3 | Telemetry `threshold_min/max` — sensor schema or separate config table? | ERD design |
| Q4 | `elevation_deg` — is synthetic radar generator 2D or 3D? | Field inclusion |

---

*Beyza Ülkümen · M2W5T7 · June 2026*
