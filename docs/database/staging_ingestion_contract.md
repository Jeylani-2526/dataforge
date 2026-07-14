# DataForge — Staging Ingestion Contract

## File Format — Newline-Delimited JSON (NDJSON)

Her generator `.ndjson` dosyası çıktı verir — satır başına bir JSON objesi, wrapping array yok.

**NDJSON seçim gerekçesi:**
- Generator'lar düz `json.dumps()` yazar, schema compilation gerekmez
- M3 geliştirme sırasında insan gözüyle spot-check yapılabilir
- `psycopg2 COPY` ve `pandas read_json(lines=True)` ile M4 ingestion script'i direkt çalışır
- Parquet M5'e ertelendi — Spark pipeline'a girdiğinde columnar format değer kazanır

---

## Batch Size

| Parametre | Değer |
|---|---|
| Kayıt/dosya | 1,000 |
| Dosya/stream | 50 (50,000 kayıt corpus için) |
| Dosya adı — fixed mode | `{stream}_{batch_number:04d}.ndjson` — örn. `radar_0001.ndjson` |
| Dosya adı — continuous mode | `{stream}_{timestamp_ms}.ndjson` — overwrite olmaz |

---

## Zorunlu Field'lar

### ALICE kayıtları

| Field | Type | Null? | Not |
|---|---|---|---|
| `event_id` | string (UUID v4) | Hayır | Her kayıtta unique |
| `run_number` | int | Hayır | LHC10h: 139038 |
| `timestamp_ms` | long | Hayır | ms since epoch |
| `track_count` | int | Hayır | ≥ 0 |
| `net_momentum_x` | float | Hayır | ROOT Docker'a kadar 0.0 |
| `net_momentum_y` | float | Hayır | ROOT Docker'a kadar 0.0 |
| `net_momentum_z` | float | Hayır | ROOT Docker'a kadar 0.0 |
| `max_energy_gev` | float | Hayır | ROOT Docker'a kadar 0.0 |
| `total_energy_gev` | float | Hayır | ROOT Docker'a kadar 0.0 |
| `schema_version` | string | Hayır | `"1.0"` olmalı |

### Sensor kayıtları — tüm subtype'lar için ortak

| Field | Type | Null? |
|---|---|---|
| `event_id` | string (UUID v4) | Hayır |
| `sensor_id` | string (UUID v4) | Hayır |
| `sensor_type` | string | Hayır — `"RADAR"` / `"LIDAR"` / `"TELEMETRY"` |
| `timestamp_ms` | long | Hayır |
| `schema_version` | string | Hayır — `"1.0"` olmalı |

### RADAR — `sensor_type = "RADAR"` olduğunda zorunlu

| Field | Type |
|---|---|
| `target_id` | string |
| `range_m` | float |
| `bearing_deg` | float |
| `elevation_deg` | float |
| `velocity_ms` | float |
| `signal_strength_db` | float |

LIDAR/TELEMETRY field'ları RADAR kayıtlarında `null` olmalı.

### LIDAR — `sensor_type = "LIDAR"` olduğunda zorunlu

| Field | Type |
|---|---|
| `scan_id` | string |
| `point_count` | int |
| `centroid_x_m` | float |
| `centroid_y_m` | float |
| `centroid_z_m` | float |
| `max_range_m` | float |
| `avg_intensity` | float |
| `min_intensity` | float |

RADAR/TELEMETRY field'ları LIDAR kayıtlarında `null` olmalı.

### TELEMETRY — `sensor_type = "TELEMETRY"` olduğunda zorunlu

| Field | Type |
|---|---|
| `device_id` | string |
| `parameter_name` | string |
| `value` | float |
| `unit` | string |
| `sequence_number` | long |

RADAR/LIDAR field'ları TELEMETRY kayıtlarında `null` olmalı.

---

## Load Timestamp

`load_timestamp` staging ingestion script tarafından `NOW()` ile eklenir. Generator'lar bu field'ı **üretmez**.

---

## Validation Kuralları (M4 ingestion script'i uygular)

| Kural | Başarısız olursa |
|---|---|
| `event_id` geçerli UUID v4 | Kayıt reject → `load_status = 'failed'` |
| `schema_version = "1.0"` | Tüm batch reject |
| Zorunlu field'lar mevcut ve non-null | Kayıt reject → `load_status = 'failed'` |
| Subtype field'ları `sensor_type` ile tutarlı | Kayıt reject → `load_status = 'failed'` |
| `timestamp_ms` > 0 | Kayıt reject → `load_status = 'failed'` |

Başarısız kayıtlar loglanır, sessizce drop edilmez.

---

## Output Dizin Yapısı (Omer için)

```
/data/generated/
  alice/
    alice_0001.ndjson
  radar/
    radar_0001.ndjson
  lidar/
    lidar_0001.ndjson
  telemetry/
    telemetry_0001.ndjson
```
