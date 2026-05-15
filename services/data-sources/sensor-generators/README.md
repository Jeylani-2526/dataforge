# Module 2 — Synthetic Sensor Data Generators

**Owner:** Omer  
**Milestone:** M3 (implementation)  
**Status:** 🔲 Not started

## Purpose

Generate synthetic radar, LIDAR, and telemetry sensor streams that simulate realistic field conditions. Publishes to Kafka topics.

## Sensor Types

| Sensor | Kafka Topic | Key Fields |
|--------|------------|------------|
| Radar | `sensor-radar` | sensor_id, timestamp, range_m, azimuth_deg, elevation_deg, rcs_dbsm |
| LIDAR | `sensor-lidar` | sensor_id, timestamp, x, y, z, intensity, return_num |
| Telemetry | `sensor-telemetry` | sensor_id, timestamp, altitude_m, speed_ms, heading_deg, status_code |

## Configuration

Set `EVENTS_PER_SECOND` in `.env` to control generator rate (default: 100 events/sec).

## Setup

```bash
pip install -r requirements.txt
python src/generate_all.py  # Starts all 3 generators
# or run individually:
python src/radar_generator.py
python src/lidar_generator.py
python src/telemetry_generator.py
```
