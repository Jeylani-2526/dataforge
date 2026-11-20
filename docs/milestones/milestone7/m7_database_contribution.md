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

Run on Beyza’s machine, 20 November 2026, window from 2026-10-01T00:00:00Z UTC. Model `combined-m7w28t1-v2`.

Pre-alignment rows (34,560) dry-run: LIDAR 98.2%, RADAR 66.1%, TELEMETRY 36.6%; 4,548 skipped for old parameters (`altitude_m`, `signal_rssi`) — not written, same decision as M7W28T3.

| Stream | Rows | Scored | Flagged | Rate |
|---|---|---|---|---|
| LIDAR | 11,406 | 11,406 | 11,198 | 98.18% |
| RADAR | 11,798 | 11,798 | 7,797 | 66.09% |
| TELEMETRY | 11,356 | 6,808 | 2,494 | 36.63% |

Checks (SQL through docker exec, not Adminer):

| Check | Result | PASS / FAIL |
|---|---|---|
| All scored rows in window, values within 0–1 | rows = scored, risk/conf 0.0000–1.0000 | PASS |
| anomaly_label consistent with risk_score >= 0.995 | 0 inconsistent | PASS |
| CHECK constraints present | 3 (chk_fused_anomaly_label, chk_fused_confidence, chk_fused_risk_score) | PASS |
| summary_5min anomaly_rate populated | 61/61 buckets per stream | PASS |

Reference — Abdalla’s machine (M7W28T3, 19 November): 12,123 rows, flag rates 1.00–1.09%.
