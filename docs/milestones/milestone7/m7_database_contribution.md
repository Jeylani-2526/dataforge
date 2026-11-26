# M7 Database Contribution

---

## Schema Changes

Three CHECK constraints added to `fused_events` (M7W27T5 finding, applied 12 November 2026):

```sql
ALTER TABLE fused_events
    ADD CONSTRAINT chk_fused_anomaly_label CHECK (anomaly_label IN (0, 1));
ALTER TABLE fused_events
    ADD CONSTRAINT chk_fused_risk_score    CHECK (risk_score BETWEEN 0.0 AND 1.0);
ALTER TABLE fused_events
    ADD CONSTRAINT chk_fused_confidence   CHECK (confidence BETWEEN 0.0 AND 1.0);
```

NULL passes all three checks — unscored rows are unaffected. Migration: `infrastructure/scripts/migrations/m7w27_fused_score_checks.sql`

`summary_5min` materialized view rebuilt — `anomaly_rate` now counts `anomaly_label = 1` rows only (previously counted any non-NULL label, which would read 100% once scoring starts). Migration: `infrastructure/scripts/migrations/m7w27_summary_anomaly_rate.sql`

---

## Training Set Extraction (M7W27T4)

M3 corpus used as-is — 150,000 records across three streams, natural ~2.97% anomaly rate.

| Stream | Total | Normal | Anomaly | Anomaly % |
|---|---|---|---|---|
| RADAR | 50,000 | 48,518 | 1,482 | 2.96% |
| LIDAR | 50,000 | 48,514 | 1,486 | 2.97% |
| TELEMETRY | 50,000 | 48,517 | 1,483 | 2.97% |

80/20 stratified split by `anomaly_type`, seed=42. Test IDs saved to `data/splits/` for reproducibility across team members.

SMOTE evaluated and rejected — Isolation Forest relies on anomaly rarity; 50/50 training raised FPR to 18–26% vs 0.4–0.5% at natural ratio. Train set retains natural ~3% distribution. Decision: Abdalla, 9 November 2026.

Script: `services/ml/make_split.py`
Design note: `docs/database/m7w27t4_training_extraction.md`

---

## Scored-Row Write Path (M7W27T5)

Verified that `anomaly_label`, `risk_score`, `confidence` are absent from `fused_writer.py` FUSED_FIELDS and from record construction — PostgreSQL fills them as NULL until M7 scoring engine writes them.

ROLLBACK write test (11 November 2026, 34,560 rows):

| Column | DB type | API contract | Result |
|---|---|---|---|
| `anomaly_label` | BIGINT | int 0/1 | PASS |
| `risk_score` | REAL | float 0.0–1.0 | PASS |
| `confidence` | REAL | float 0.0–1.0 | PASS |

Finding: no CHECK constraints on scored columns at time of test — added on 12 November via migration above (commit fe0175b).
NULL count: 34,560 / 34,560 rows unscored (confirmed full table, not sample).

Design note: `docs/database/m7w27t5_scored_row_conformance.md`

---

## ERD / API Implications

- `fused_events`: three new CHECK constraints enforce scoring API contract at DB level
- `summary_5min`: `anomaly_rate` column now semantically correct — reflects true anomaly share once scoring runs
- Write path unchanged — `fused_writer.py` COPY insert targets 9 columns only; scored columns written separately by scoring engine (M7W28T3, verified M7W28T8)
- `GET /api/v1/alerts/recent` depends on `anomaly_label = 1` — constraint now enforced end-to-end

---

## Scored-Row Verification (M7W28T8)

**Checks run:** 20 November 2026 · **Model:** `combined-m7w28t1-v2` · SQL through `docker exec`, not Adminer.

**Plan B** (decided 20 November, Abdalla). The planned second-machine run on **aligned** data was
not completed: Docker Desktop on Beyza's machine failed during the image rebuild (read-only
filesystem). Aligned-data scores are therefore verified on Abdalla's machine; Beyza's machine
contributes write-path evidence on pre-alignment data only.

### A. Aligned data — Abdalla's machine

Window from 2026-11-12 07:06:00 UTC — after the producer alignment (`8af19aa`) and image rebuild.
Rows scored by M7W28T3.

| Stream | Rows | Scored | Alarms | Rate | risk_score | confidence |
|---|---|---|---|---|---|---|
| LIDAR | 4,077 | 4,077 | 42 | 1.03% | 0.0006–1.0000 | 0.0004–1.0000 |
| RADAR | 4,053 | 4,053 | 44 | 1.09% | 0.0005–1.0000 | 0.0001–0.9995 |
| TELEMETRY | 3,993 | 3,993 | 40 | 1.00% | 0.0176–1.0000 | 0.0018–1.0000 |

| Check | Result | PASS / FAIL |
|---|---|---|
| Every fused row in the window scored | 12,123 / 12,123 | PASS |
| Values inside the CHECK ranges | risk 0.0005–1.0000, confidence 0.0001–1.0000 | PASS |
| `anomaly_label` = 1 exactly when `risk_score` ≥ 0.995 | 0 inconsistent | PASS |
| CHECK constraints present | 3 constraints, on the hypertable and each of its 3 daily chunks (12 entries in `pg_constraint`) | PASS |
| `summary_5min.anomaly_rate` populated | 20 / 20 buckets per stream; mean 0.0103 / 0.0111 / 0.0099 | PASS |
| Rows before the window untouched | 37,060 rows, 0 scored | PASS |

### B. Second machine — Beyza's, pre-alignment data

- Window from 2026-10-01: Beyza's 34,560 M6 fused rows, all produced **before** the producer
  alignment. Flagged: LIDAR 98.18%, RADAR 66.09%, TELEMETRY 36.63%; 4,548 telemetry rows skipped
  for parameters only the old producer emits (`altitude_m`, `signal_rssi`). This reproduces the
  M7W27T1 finding that the corpus-trained model flags the old producer's records (LIDAR 93.9% there).
- These scores were **written by mistake**, then **reverted on 20 November** (scores set back to
  NULL, `summary_5min` refreshed, scored count confirmed 0).
- **What it still shows:** on a second database, the CHECK constraints accepted the writes,
  label and risk stayed consistent (0 inconsistent), and `summary_5min` picked up the scores
  (61 / 61 buckets) — the write path works on a second machine.
- **What it does not show:** scoring of aligned data on a second machine. Carried in
  `open_items_m7.md`.

---

## M8W29 Database Additions (T4)

**Applied:** 26 November 2026 · **Commit:** `5db790d` · **Migration:** `infrastructure/scripts/migrations/m8w29_alerts_xai_tables.sql`

### New objects

**`anomaly_alerts`** — hypertable, partition column `time` TIMESTAMPTZ, 1-day chunks, 365-day retention.

Primary key: `(time, fused_event_id)`

- `fused_event_id UUID NOT NULL` — soft reference, no DB-level FK constraint (TimescaleDB cannot enforce FK into a hypertable; M6 Option C, confirmed M7, implemented here)
- CHECK constraints: `risk_score BETWEEN 0.0 AND 1.0`, `confidence BETWEEN 0.0 AND 1.0`, `anomaly_label = 1`, `status IN ('active','reviewed','closed')`
- Index: `idx_alerts_fused_risk ON (fused_event_id, risk_score DESC)`

**`alerts_daily`** — continuous aggregate on `anomaly_alerts`, 1-day bucket.

- Refresh policy: `start_offset 3 days`, `end_offset 1 hour`, `schedule_interval 1 hour`
- Columns: `total_alerts`, `active_count`, `critical_count`, `avg_risk_score`, `max_risk_score` per `source_type` per day
- Consumer: `GET /api/v1/reports` (Endpoint 15)

**`xai_explanations`** — hypertable, partition column `time` TIMESTAMPTZ, 1-day chunks, 365-day retention.

Primary key: `(time, fused_event_id)`

- `fused_event_id UUID NOT NULL` — soft reference, same rationale as `anomaly_alerts`
- `shap_values JSONB`: array of `{feature, shap_value, direction}` — field name is `shap_value` (not `value`), per `m8w29t1_xai_design.md`
- `top_features JSONB`: precomputed array, up to 3 features
- Consumer: `GET /api/v1/xai/{fused_event_id}` (Endpoint 10)

### ERD update

`erd_final.md` FK table updated — both "Decide at M7" rows replaced with confirmed M6 Option C soft reference note. Commit `b127824`.

### Verification (docker exec, not Adminer)

Query: `SELECT hypertable_name, num_chunks FROM timescaledb_information.hypertables WHERE hypertable_name IN ('anomaly_alerts', 'xai_explanations');`

| hypertable_name | num_chunks |
|---|---|
| anomaly_alerts | 0 |
| xai_explanations | 0 |

`num_chunks = 0` — expected, no data inserted yet. Tables and CAGG presence confirmed via `\dt` and `\dm`.

Migration applied manually via `docker cp` + `psql -f` — `init-db.sql` skipped by existing volume (runs on first initialization only).
