# Staging → Production Promotion Design

## Source → Destination

| Source | Destination | Condition |
|---|---|---|
| `raw_alice_events_staging` | `events` | `load_status = 'validated'` |
| `raw_sensor_events_staging` | `events` | `load_status = 'validated'` |

---

## Events Hypertable — Target Schema

```sql
CREATE TABLE events (
    event_id          UUID        PRIMARY KEY,
    source_type       VARCHAR(20) NOT NULL,
    timestamp_ms      BIGINT      NOT NULL,
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
    schema_version    VARCHAR(10) NOT NULL DEFAULT '1.0'
);

SELECT create_hypertable('events', 'timestamp_ms',
    chunk_time_interval => 86400000);
```

---

## Promotion Logic

### ALICE

```sql
INSERT INTO events (
    event_id, source_type, timestamp_ms, run_number, track_count,
    net_momentum_x, net_momentum_y, net_momentum_z,
    max_energy_gev, total_energy_gev, schema_version
)
SELECT
    event_id, 'alice', timestamp_ms, run_number, track_count,
    net_momentum_x, net_momentum_y, net_momentum_z,
    max_energy_gev, total_energy_gev, schema_version
FROM raw_alice_events_staging
WHERE load_status = 'validated';

UPDATE raw_alice_events_staging
SET load_status = 'promoted'
WHERE load_status = 'validated';
```

### Sensor

```sql
INSERT INTO events (
    event_id, source_type, timestamp_ms, sensor_type,
    label, anomaly_type, schema_version
)
SELECT
    event_id, LOWER(sensor_type), timestamp_ms, sensor_type,
    label, anomaly_type, schema_version
FROM raw_sensor_events_staging
WHERE load_status = 'validated';

UPDATE raw_sensor_events_staging
SET load_status = 'promoted'
WHERE load_status = 'validated';
```

---

## Validation Gates

| Gate | ALICE | Sensor |
|---|---|---|
| `event_id` UUID v4 | ✅ | ✅ |
| `timestamp_ms` > 0 | ✅ | ✅ |
| `load_status = 'validated'` | ✅ | ✅ |
| `run_number` NOT NULL | ✅ | — |
| `sensor_type` geçerli değer | — | ✅ |

---

## load_status Transitions

```
pending → validated → promoted
                   ↘ failed
```

---

## Notes

- Promotion atomik — INSERT başarısız olursa `load_status` güncellenmez
- Duplicate koruması: `ON CONFLICT (event_id) DO NOTHING`
- `latency_ms`, `anomaly_label`, `risk_score` → M5-M7'de doldurulacak
