# M8 Database Contribution

---

## M8W29 Database Additions (T4)

**Applied:** 26 November 2026 · **Migration:** `infrastructure/scripts/migrations/m8w29_alerts_xai_tables.sql`

### New objects

**`anomaly_alerts`** — hypertable, partition column `time` TIMESTAMPTZ, 1-day chunks, 365-day retention.

Primary key: `(time, fused_event_id)`

- `fused_event_id UUID NOT NULL` — soft reference, no DB-level FK constraint (TimescaleDB cannot enforce FK into a hypertable; M6 Option C, confirmed M7, implemented here)
- CHECK constraints: `risk_score BETWEEN 0.0 AND 1.0`, `confidence BETWEEN 0.0 AND 1.0`, `anomaly_label = 1`, `status IN ('active','reviewed','closed')`
- Index: `idx_alerts_fused_risk ON (fused_event_id, risk_score DESC)`

**`alerts_daily`** — continuous aggregate on `anomaly_alerts`, 1-day bucket.

- Refresh policy: `start_offset 3 days`, `end_offset 1 hour`, `schedule_interval 1 hour`
- Columns: `bucket`, `anomaly_count`
- Consumer: `GET /api/v1/reports` (Endpoint 15)

**`xai_explanations`** — hypertable, partition column `time` TIMESTAMPTZ, 1-day chunks, 365-day retention.

Primary key: `(time, fused_event_id)`

- `fused_event_id UUID NOT NULL` — soft reference, same rationale as `anomaly_alerts`
- `shap_values JSONB NOT NULL` — array of `{feature, shap_value, direction}`; CHECK `jsonb_typeof(shap_values) = 'array'`
- `top_features JSONB NOT NULL` — precomputed array, up to 3 features; CHECK `jsonb_array_length BETWEEN 1 AND 3`
- Consumer: `GET /api/v1/xai/{fused_event_id}` (Endpoint 10)

### ERD update

`erd_final.md` column notes updated — `anomaly_alerts.fused_event_id` and `xai_explanations.fused_event_id` now show soft reference note; `xai_explanations.top_features` corrected to "up to 3 precomputed".

### Verification (docker exec, not Adminer)

```sql
SELECT hypertable_name, num_chunks
FROM timescaledb_information.hypertables
WHERE hypertable_name IN ('anomaly_alerts', 'xai_explanations');
```

| hypertable_name  | num_chunks |
| ---------------- | ---------- |
| anomaly_alerts   | 0          |
| xai_explanations | 0          |

`num_chunks = 0` — expected, no data inserted yet. Tables and CAGG presence confirmed via `\dt` and `\dm`.

Migration applied manually via `docker cp` + `psql -f` — `init-db.sql` skipped by existing volume (runs on first initialization only).

### Retention and CAGG job verification

```sql
SELECT application_name, schedule_interval, next_start
FROM timescaledb_information.jobs
WHERE application_name IN (
    'Retention Policy [anomaly_alerts]',
    'Retention Policy [xai_explanations]',
    'Refresh Continuous Aggregate Policy [alerts_daily]'
);
```

Expected result:

| application_name                                   | schedule_interval | next_start  |
| -------------------------------------------------- | ----------------- | ----------- |
| Retention Policy [anomaly_alerts]                  | 1 day             | (scheduled) |
| Retention Policy [xai_explanations]                | 1 day             | (scheduled) |
| Refresh Continuous Aggregate Policy [alerts_daily] | 1 hour            | (scheduled) |
