# Field-Mapping Mismatch Resolution Log

## Week 10 Mismatch Resolution

| # | Stream | Field | Severity | Status | Resolution |
|---|---|---|---|---|---|
| 1 | all | File extension `.ndjson` vs `.jsonl` | INFO | ✅ Resolved | `staging_ingestion_script.py` güncellendi |
| 2 | all | DB_URL user `postgres` vs `dataforge` | INFO | ✅ Resolved | `staging_ingestion_script.py` güncellendi |
| 3 | alice | `net_momentum_x/y/z`, `max_energy_gev`, `total_energy_gev` = 0.0 | INFO | ✅ Accepted | PyROOT M4'te eklenecek |

---

## sensor_freeze → timestamp_stall Check

| Check | Result |
|---|---|
| `first_load_mismatch_log.md` içinde `sensor_freeze` | ❌ Yok |
| `staging_ingestion_script.py` içinde `sensor_freeze` | ❌ Yok |
| DB'de TELEMETRY `anomaly_type` değerleri | `out_of_range_value`, `timestamp_stall`, `missing_reading` ✅ |

---

## Staging Re-Validation (21 Temmuz 2026)

| Stream | Records | Validated | Failed | Anomaly Count | Anomaly Rate |
|---|---|---|---|---|---|
| RADAR | 50,000 | 50,000 | 0 | 1,482 | 2.96% |
| LIDAR | 50,000 | 50,000 | 0 | 1,486 | 2.97% |
| TELEMETRY | 50,000 | 50,000 | 0 | 1,483 | 2.97% |
| ALICE | 287 | 287 | 0 | — | — |
| **Total** | **150,287** | **150,287** | **0** | **4,451** | **~3%** |

---

## Open Items

| # | Item | Owner | Target |
|---|---|---|---|
| 1 | momentum/energy field'ları → gerçek değerler | Abdalla (PyROOT) | M4 |
| 2 | PHYSICS_EVENT filtresi (fEventType=7) → ALICE extraction | Beyza | M4 |
| 3 | `sensor_freeze` → M7 per-record Isolation Forest için yeniden değerlendir | Abdalla | M4/M7 |
