# fused_events + fusion_status DDL Verification

---

## DDL Applied

Added to `infrastructure/scripts/init-db.sql` and applied to the live volume via:

```
Get-Content init-db.sql | docker exec -i dataforge-timescaledb psql -U dataforge -d dataforge
```

FK note: `alice_event_id` and `sensor_event_id` are soft references — `uuid NOT NULL` with no `REFERENCES` clause. See `docs/database/fused_events_fk_decision.md`.

---

## Hypertable Verification

```sql
SELECT hypertable_name, num_chunks FROM timescaledb_information.hypertables;

 hypertable_name | num_chunks
-----------------+------------
 events          |          5
 fused_events    |          0
 fusion_status   |          0
```

---

## fused_events Column Verification

```
\d fused_events

      Column      |         Type          | Nullable | Default
------------------+-----------------------+----------+---------
 timestamp_ms     | bigint                | not null |
 fused_event_id   | uuid                  | not null |
 alice_event_id   | uuid                  | not null |
 sensor_event_id  | uuid                  | not null |
 sensor_type      | character varying(20) | not null |
 fusion_window_ms | integer               | not null | 500
 data_loss_pct    | real                  | not null | 0.0
 latency_ms       | bigint                | not null | 0
 schema_version   | character varying(10) | not null | '1.0'
 anomaly_label    | bigint                |          |
 risk_score       | real                  |          |
 confidence       | real                  |          |

Indexes:
    fused_events_pkey PRIMARY KEY (fused_event_id, timestamp_ms)
    fused_events_timestamp_ms_idx btree (timestamp_ms DESC)
    idx_fused_time_label btree (timestamp_ms, anomaly_label)
```

Chunk interval: 86,400,000 ms (1 day). Retention: 90 days (integer_now via `fused_events_now()`).

---

## fusion_status Column Verification

```
\d fusion_status

       Column        |           Type           | Nullable
---------------------+--------------------------+----------
 time                | timestamp with time zone | not null
 source_type         | character varying(20)    | not null
 quality_score       | integer                  | not null
 contribution_weight | real                     | not null
 data_loss           | real                     | not null
 latency             | real                     | not null
 status              | character varying(20)    | not null

Indexes:
    fusion_status_time_idx btree (time DESC)
```

Chunk interval: 1 hour. Retention: 7 days.

---

## Result

Both tables created as hypertables and verified in the live DB. Schema matches `fused_event_schema_v1.avsc` and `erd_final.md` exactly.
