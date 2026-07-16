# First Load Test & Field-Mapping Mismatch Log

## Load Test Summary

| Stream | Files | Total | Validated | Failed |
|---|---|---|---|---|
| alice | — | — | — | — |
| radar | — | — | — | — |
| lidar | — | — | — | — |
| telemetry | — | — | — | — |

*Omer'in batch'leri gelince doldurulacak.*

---

## Staging → `events` Cross-Check (erd_final.md)

| Staging Field | `events` Column | Status |
|---|---|---|
| `event_id` | `event_id` (uuid) | Pending |
| `run_number` | `run_number` (int) | Pending |
| `timestamp_ms` | `timestamp_ms` (bigint) | Pending |
| `track_count` | `track_count` (int) | Pending |
| `net_momentum_x/y/z` | `net_momentum_x/y/z` (real) | Pending |
| `max_energy_gev` | `max_energy_gev` (real) | Pending |
| `total_energy_gev` | `total_energy_gev` (real) | Pending |
| `sensor_type` | `source_type` (lowercased) | Pending |
| RADAR fields (6) | staging only | Pending |
| LIDAR fields (8) | staging only | Pending |
| TELEMETRY fields (5) | staging only | Pending |

**Pipeline-written — staging'de bulunmaz (beklenen):**
`latency_ms` (M5) · `data_loss_pct` (M3) · `quality_flag` (M5) · `anomaly_label` (M7) · `risk_score` (M7)

---

## Staging → API Contracts Cross-Check (api_contracts_final.md)

| API Field | Staging Kaynağı | Status |
|---|---|---|
| `event_id` | `event_id` | Pending |
| `timestamp_ms` | `timestamp_ms` | Pending |
| `source_type` | `sensor_type` lowercased | Pending |
| `quality_flag` | Pipeline-written — beklenen absent | — |
| `latency_ms` | Pipeline-written — beklenen absent | — |
| `data_loss_pct` | Pipeline-written — beklenen absent | — |

---

## Mismatch Log

| # | Stream | Field | Beklenen | Gerçek | Severity | Çözüm |
|---|---|---|---|---|---|---|
| — | — | — | — | — | — | Week 11 |

**Severity:** BLOCK — yükleme engeller · WARN — M4 promote'u etkiler · INFO — kozmetik

Mismatches sessizce patch edilmez — Abdullah ve Omer'e Cuma 17 Temmuz'a kadar iletilir.
