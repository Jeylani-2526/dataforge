# M3 Database Contribution

## 1. Staging Schema Design Decisions

Two staging tables receive raw data before M4 promotes them to production hypertables.

| Table | Source | Promotes to |
|---|---|---|
| `raw_sensor_events_staging` | RADAR / LIDAR / TELEMETRY generators | `events` hypertable |
| `raw_alice_events_staging` | ALICE ESD extraction (uproot) | `events` (source_type='alice') |

- `label` and `anomaly_type` columns added to carry labeled training data into production.
- `net_momentum_x/y/z`, `max_energy_gev`, `total_energy_gev` stored as `REAL DEFAULT 0.0` — PyROOT deferred to M4.
- `load_status` tracks lifecycle: `pending → validated → promoted → failed`.

---

## 2. Ingestion Contract

**Script:** `scripts/ingestion/staging_ingestion_script.py`
**Validation:** UUID v4 · schema_version · sensor type · psycopg2 execute_batch (500/batch)

| Stream | Records | Failed |
|---|---|---|
| RADAR | 50,000 | 0 |
| LIDAR | 50,000 | 0 |
| TELEMETRY | 50,000 | 0 |
| ALICE | 287 | 0 |
| **Total** | **150,287** | **0** |

---

## 3. ERD / API Conformance Results

**Mismatch Resolution (T4)**

| # | Issue | Resolution |
|---|---|---|
| 1 | `.ndjson` vs `.jsonl` | Script updated |
| 2 | DB user `postgres` vs `dataforge` | Credentials corrected |
| 3 | `net_momentum_x/y/z` = 0.0 | Deferred to M4 |

`sensor_freeze` absent ✅ · `timestamp_stall` confirmed in TELEMETRY ✅

**API Contract Tests (T5)**

| Endpoint | Result |
|---|---|
| `GET /api/v1/events/live` | ✅ PASS |
| `GET /api/v1/alerts/recent` | ✅ PASS |

**Anomaly Distribution**

| sensor_type | anomaly_type | count |
|---|---|---|
| LIDAR | ghost_point | 498 |
| LIDAR | noise_burst | 502 |
| LIDAR | point_cloud_dropout | 486 |
| RADAR | ghost_target | 513 |
| RADAR | sensor_dropout | 498 |
| RADAR | velocity_spike | 471 |
| TELEMETRY | missing_reading | 465 |
| TELEMETRY | out_of_range_value | 496 |
| TELEMETRY | timestamp_stall | 522 |

---

## 4. Open Items for M4

| # | Item | Owner |
|---|---|---|
| 1 | momentum/energy fields → PyROOT | Abdalla |
| 2 | PHYSICS_EVENT filter (fEventType=7) | Beyza |
| 3 | Promote staging → production hypertable | M4 |
