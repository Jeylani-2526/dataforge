# First Load Test & Field-Mapping Mismatch Log

## Load Test Summary

| Stream | Files | Total | Validated | Failed |
|---|---|---|---|---|
| alice | — | — | — | ALICE batch henüz yüklenmedi (AliESDs.root mevcut, M4'te işlenecek) |
| radar | 1 | 50,000 | 50,000 | 0 |
| lidar | 1 | 50,000 | 50,000 | 0 |
| telemetry | 1 | 50,000 | 50,000 | 0 |

**Toplam:** 150,000 kayıt yüklendi · 0 failed · DB doğrulandı (19 Temmuz 2026)

---

## Staging → `events` Cross-Check (erd_final.md)

| Staging Field | `events` Column | Status |
|---|---|---|
| `event_id` | `event_id` (uuid) | ✅ Eşleşti |
| `run_number` | `run_number` (int) | ✅ ALICE için hazır |
| `timestamp_ms` | `timestamp_ms` (bigint) | ✅ Eşleşti |
| `track_count` | `track_count` (int) | ✅ ALICE için hazır |
| `net_momentum_x/y/z` | `net_momentum_x/y/z` (real) | ✅ ALICE için hazır |
| `max_energy_gev` | `max_energy_gev` (real) | ✅ ALICE için hazır |
| `total_energy_gev` | `total_energy_gev` (real) | ✅ ALICE için hazır |
| `sensor_type` | `source_type` (lowercased) | ✅ Eşleşti — lowercase dönüşümü script'te uygulandı |
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
| 1 | all | dosya uzantısı | `.ndjson` | `.jsonl` | INFO | staging_ingestion_script.py güncellendi — `.jsonl` desteklenir |
| 2 | all | DB_URL kullanıcı | `postgres` | `dataforge` | INFO | staging_ingestion_script.py güncellendi — doğru credentials |

**Severity:** BLOCK — yükleme engeller · WARN — M4 promote'u etkiler · INFO — kozmetik

**Sonuç:** BLOCK veya WARN seviyesinde mismatch yok. 2 INFO-level uyumsuzluk script'te düzeltildi.
