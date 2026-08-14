# Promotion Contract

## ALICE → events

| Field | Source |
|---|---|
| `event_id` | `raw_alice_events_staging.event_id` |
| `source_type` | Hardcoded `'alice'` |
| `timestamp_ms` | `raw_alice_events_staging.timestamp_ms` |
| `run_number` | `raw_alice_events_staging.run_number` |
| `track_count` | `raw_alice_events_staging.track_count` |
| `net_momentum_x` | `raw_alice_events_staging.net_momentum_x` |
| `net_momentum_y` | `raw_alice_events_staging.net_momentum_y` |
| `net_momentum_z` | `raw_alice_events_staging.net_momentum_z` |
| `max_energy_gev` | `raw_alice_events_staging.max_energy_gev` |
| `total_energy_gev` | `raw_alice_events_staging.total_energy_gev` |
| `schema_version` | `raw_alice_events_staging.schema_version` |

## Sensor → events

| Field | Source |
|---|---|
| `event_id` | `raw_sensor_events_staging.event_id` |
| `source_type` | `LOWER(raw_sensor_events_staging.sensor_type)` |
| `timestamp_ms` | `raw_sensor_events_staging.timestamp_ms` |
| `sensor_type` | `raw_sensor_events_staging.sensor_type` |
| `label` | `raw_sensor_events_staging.label` |
| `anomaly_type` | `raw_sensor_events_staging.anomaly_type` |
| `schema_version` | `raw_sensor_events_staging.schema_version` |

---

## load_status Transitions

| load_status | Açıklama |
|---|---|
| `pending` | Kayıt yazıldı, henüz doğrulanmadı |
| `validated` | Promote için hazır |
| `promoted` | `events` hypertable'a yazıldı |
| `failed` | Promote edilmez |

---

## Adaptation Pipeline Output — Required Fields

**ALICE stream:**
`event_id`, `run_number`, `timestamp_ms`, `track_count`, `net_momentum_x/y/z`, `max_energy_gev`, `total_energy_gev`, `schema_version`

**Sensor stream:**
`event_id`, `sensor_id`, `sensor_type`, `timestamp_ms`, `label`, `anomaly_type`, `schema_version` + sensör tipine özgü field'lar

`load_status` promotion script tarafından yönetilir — pipeline tarafından set edilmez.

---

## Deferred Fields

| Field | Milestone |
|---|---|
| `latency_ms` | M5 |
| `anomaly_label` | M7 |
| `risk_score` | M7 |
