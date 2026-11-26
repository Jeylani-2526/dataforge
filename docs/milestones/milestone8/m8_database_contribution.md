# M8 Database Contribution

_Owner:_ Beyza · _Milestone:_ M8 · _Tasks:_ M8W29T4 (W31T4 ve W32T6 sonra eklenecek)

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

> `xai_explanations` and `alerts_daily` were dropped and recreated from migration on 26 November 2026 — no data existed at the time.

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

`num_chunks = 0` — expected, no data inserted yet.

Migration applied manually via `docker cp` + `psql -f` — `init-db.sql` skipped by existing volume (runs on first initialization only).

### Constraint verification

```sql
SELECT conname FROM pg_constraint
WHERE conrelid IN ('anomaly_alerts'::regclass, 'xai_explanations'::regclass)
ORDER BY 1;
```

| conname                   |
| ------------------------- |
| chk_alerts_anomaly_label  |
| chk_alerts_confidence     |
| chk_alerts_risk_score     |
| chk_alerts_status         |
| chk_xai_shap_values_array |
| chk_xai_top_features      |
| pk_anomaly_alerts         |
| pk_xai_explanations       |

8 rows — 2 primary keys + 6 CHECK constraints.

### Retention and CAGG job verification

```sql
SELECT j.job_id, j.proc_name, COALESCE(c.view_name, j.hypertable_name) AS target, j.schedule_interval
FROM timescaledb_information.jobs j
LEFT JOIN timescaledb_information.continuous_aggregates c
       ON c.materialization_hypertable_name = j.hypertable_name
WHERE COALESCE(c.view_name, j.hypertable_name) IN ('anomaly_alerts','xai_explanations','alerts_daily')
ORDER BY 3;
```

| job_id | proc_name                           | target           | schedule_interval |
| ------ | ----------------------------------- | ---------------- | ----------------- |
| 1003   | policy_retention                    | anomaly_alerts   | 1 day             |
| 1007   | policy_refresh_continuous_aggregate | alerts_daily     | 01:00:00          |
| 1008   | policy_retention                    | xai_explanations | 1 day             |

3 rows — 2 retention policies + 1 CAGG refresh policy.

### alerts_daily column verification

```sql
SELECT column_name FROM information_schema.columns
WHERE table_name = 'alerts_daily' ORDER BY ordinal_position;
```

| column_name   |
| ------------- |
| bucket        |
| anomaly_count |

2 rows — no extra columns.

### xai_explanations JSONB default verification

```sql
SELECT column_name, column_default FROM information_schema.columns
WHERE table_name = 'xai_explanations' AND column_name IN ('shap_values','top_features');
```

| column_name  | column_default |
| ------------ | -------------- |
| shap_values  |                |
| top_features |                |

No defaults — values must be supplied explicitly.
