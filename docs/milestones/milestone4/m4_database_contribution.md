# M4 Database Contribution

## 1. Promotion Design

PRIMARY KEY `(event_id, timestamp_ms)` — TimescaleDB hypertable partitioning gerekliliği.

```sql
CREATE TABLE events (
    event_id          UUID        NOT NULL,
    timestamp_ms      BIGINT      NOT NULL,
    source_type       VARCHAR(20) NOT NULL,
    run_number        INTEGER,
    track_count       INTEGER,
    net_momentum_x    REAL,
    net_momentum_y    REAL,
    net_momentum_z    REAL,
    max_energy_gev    REAL,
    total_energy_gev  REAL,
    sensor_type       VARCHAR(20),
    label             INTEGER     DEFAULT 0,
    anomaly_type      VARCHAR(50),
    latency_ms        REAL,
    anomaly_label     INTEGER,
    risk_score        REAL,
    schema_version    VARCHAR(10) NOT NULL DEFAULT '1.0',
    PRIMARY KEY (event_id, timestamp_ms)
);

SELECT create_hypertable('events', 'timestamp_ms', chunk_time_interval => 86400000);
```

load_status: `pending → validated → promoted / failed`

Deferred: `latency_ms` (M5) · `anomaly_label` (M7) · `risk_score` (M7)

---

## 2. Promotion Results

| source_type | count       |
| ----------- | ----------- |
| alice       | 68          |
| lidar       | 50,000      |
| radar       | 50,000      |
| telemetry   | 50,000      |
| **Total**   | **150,068** |

0 failed · 0 skipped · port 5433

---

## 3. ERD / API Implications

- `events` tablosu M9 dashboard API'sinin tek production kaynağı
- `GET /api/v1/events/live` ve `GET /api/v1/alerts/recent` bu tabloyu sorgular
- `source_type` ALICE ve sensör akışlarını ayırt eder
- `label` ve `anomaly_type` M7'de AI/ML çıktılarıyla güncellenecek
