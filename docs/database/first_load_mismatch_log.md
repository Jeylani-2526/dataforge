# First Load Test & Field-Mapping Mismatch Log

## Load Test Summary

| Stream | Files | Total | Validated | Failed |
|---|---|---|---|---|
| alice | 1 | 287 | 287 | 0 |
| radar | 1 | 50,000 | 50,000 | 0 |
| lidar | 1 | 50,000 | 50,000 | 0 |
| telemetry | 1 | 50,000 | 50,000 | 0 |

**Toplam:** 150,287 kayıt yüklendi · 0 failed · DB doğrulandı (19 Temmuz 2026)

---

## Staging → `events` Cross-Check (erd_final.md)

| Staging Field | `events` Column | Status |
|---|---|---|
| `event_id` | `event_id` (uuid) | ✅ Eşleşti |
| `run_number` | `run_number` (int) | ✅ Eşleşti — run 139465 |
| `timestamp_ms` | `timestamp_ms` (bigint) | ✅ Eşleşti |
| `track_count` | `track_count` (int) | ✅ Eşleşti |
| `net_momentum_x/y/z` | `net_momentum_x/y/z` (real) | ✅ 0.0 — PyROOT M4'te |
| `max_energy_gev` | `max_energy_gev` (real) | ✅ 0.0 — PyROOT M4'te |
| `total_energy_gev` | `total_energy_gev` (real) | ✅ 0.0 — PyROOT M4'te |
| `sensor_type` | `source_type` (lowercased) | ✅ Eşleşti |
| RADAR fields (6) | staging only | ✅ Tümü doğru yüklendi |
| LIDAR fields (8) | staging only | ✅ Tümü doğru yüklendi |
| TELEMETRY fields (5) | staging only | ✅ Tümü doğru yüklendi |

**Pipeline-written — staging'de bulunmaz (beklenen, doğrulandı):**
`latency_ms` (M5) · `data_loss_pct` (M3) · `quality_flag` (M5) · `anomaly_label` (M7) · `risk_score` (M7)

---

## Staging → API Contracts Cross-Check (api_contracts_final.md)

| API Field | Staging Kaynağı | Status |
|---|---|---|
| `event_id` | `event_id` | ✅ Eşleşti |
| `timestamp_ms` | `timestamp_ms` | ✅ Eşleşti |
| `source_type` | `sensor_type` lowercased | ✅ Eşleşti |
| `quality_flag` | Pipeline-written — beklenen absent | ✅ Doğrulandı |
| `latency_ms` | Pipeline-written — beklenen absent | ✅ Doğrulandı |
| `data_loss_pct` | Pipeline-written — beklenen absent | ✅ Doğrulandı |

---

## Mismatch Log

| # | Stream | Field | Beklenen | Gerçek | Severity | Çözüm |
|---|---|---|---|---|---|---|
| 1 | all | dosya uzantısı | `.ndjson` | `.jsonl` | INFO | staging_ingestion_script.py güncellendi |
| 2 | all | DB_URL kullanıcı | `postgres` | `dataforge` | INFO | staging_ingestion_script.py güncellendi |
| 3 | alice | momentum/energy | gerçek değer | 0.0 | INFO | PyROOT Docker M4'te eklenecek |

**Sonuç:** BLOCK veya WARN seviyesinde mismatch yok. 3 INFO-level uyumsuzluk — hepsi beklenen veya düzeltildi.
