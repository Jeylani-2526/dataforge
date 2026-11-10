# M7W27T5 — Scored-Row Write Path Conformance

---

## 1. Purpose

Verify that the M7 nullable columns (`anomaly_label`, `risk_score`, `confidence`) are absent from the current write path and will remain NULL in `fused_events` until the M7 scoring engine populates them. This ensures the write path does not silently zero-fill or default these columns before inference runs.

---

## 2. Write Path Analysis — `fused_writer.py`

### 2.1 FUSED_FIELDS (insert column list)

```python
FUSED_FIELDS = [
    "fused_event_id", "alice_event_id", "sensor_event_id",
    "timestamp_ms", "fusion_window_ms", "sensor_type",
    "data_loss_pct", "latency_ms", "schema_version",
]
```

`anomaly_label`, `risk_score`, `confidence` are **not present** in `FUSED_FIELDS`. The COPY insert targets only these 9 columns.

### 2.2 Record construction (`write_fused_events`)

```python
raw_records = [
    {
        "fused_event_id": str(uuid.uuid4()),
        "alice_event_id": r["alice_event_id"],
        "sensor_event_id": r["sensor_event_id"],
        "timestamp_ms": r["timestamp_ms"],
        "fusion_window_ms": FUSION_WINDOW_MS,
        "sensor_type": r["sensor_type"],
        "data_loss_pct": 0.0,
        "latency_ms": 0,
        "schema_version": "1.0",
    }
    for r in rows
]
```

M7 nullable columns are never constructed in the dict. No default value, no zero-fill.

### 2.3 Insert path (`_copy_insert_fused`)

The COPY buffer is built from `FUSED_FIELDS` only:

```python
buf.write(",".join(_csv_field(rec[c]) for c in columns))
```

The INSERT statement targets only `FUSED_FIELDS` columns. PostgreSQL fills the remaining columns (`anomaly_label`, `risk_score`, `confidence`) with their column defaults, which are `NULL`.

### 2.4 schema_versioning.enforce()

`enforce()` validates against `fused_event_schema_v1.avsc`. That schema carries no `anomaly_label`, `risk_score`, or `confidence` field -- confirmed by M6W26T1 conformance check (PASS, 2026-11-05). The enforcement round-trip cannot introduce these values.

---

## 3. Database Verification

Full table count (34,560 rows, executed 2026-11-10):

| Column | NOT NULL count | Total rows | Result |
|---|---|---|---|
| `anomaly_label` | 0 | 34,560 | PASS |
| `risk_score` | 0 | 34,560 | PASS |
| `confidence` | 0 | 34,560 | PASS |

Query: `SELECT COUNT(*) FILTER (WHERE anomaly_label IS NOT NULL) AS scored, COUNT(*) AS total FROM fused_events;`

All M7 nullable columns are NULL across the full 34,560-row table. No write path populates them before M7 inference.

---

## 4. Write Test (ROLLBACK)

Executed 2026-11-10 via `docker exec dataforge-timescaledb psql`. Transaction rolled back -- no data modified.

### 4.1 Valid score write

```sql
UPDATE fused_events SET anomaly_label = 1, risk_score = 0.91, confidence = 0.94
WHERE fused_event_id = (SELECT fused_event_id FROM fused_events LIMIT 1)
RETURNING fused_event_id, anomaly_label, risk_score, confidence;
```

Result:

| fused_event_id | anomaly_label | risk_score | confidence |
|---|---|---|---|
| 00033274-e360-4170-8449-7d0673a46a3b | 1 | 0.91 | 0.94 |

UPDATE 1 -- PASS. Values written and returned correctly.

### 4.2 Out-of-range write (risk_score = 1.5)

```sql
UPDATE fused_events SET risk_score = 1.5
WHERE fused_event_id = (SELECT fused_event_id FROM fused_events LIMIT 1)
RETURNING risk_score;
```

Result: `risk_score = 1.5` -- UPDATE 1 accepted.

**FINDING:** No CHECK constraint on `risk_score` or `confidence` in the database schema. The API contract specifies 0.0-1.0 but the DB accepts values outside this range. Schema enforcement decision deferred to Abdalla (schema authority).

### 4.3 Type compatibility

| Column | DB type | API contract | Compatible |
|---|---|---|---|
| `anomaly_label` | BIGINT | int 0/1 | YES |
| `risk_score` | REAL | float 0.0-1.0 | YES (range not enforced at DB level) |
| `confidence` | REAL | float 0.0-1.0 | YES (range not enforced at DB level) |

---

## 5. M7 Write Path (forward reference)

When M7W28T3 (Live Inference) runs, the scoring engine will UPDATE these columns in-place per fused row. The write path for that update is outside the current scope and will be verified in M7W28T8.

---

## 6. Gate Status

**PASS** -- M7 nullable columns (`anomaly_label`, `risk_score`, `confidence`) are absent from `FUSED_FIELDS`, absent from record construction, and confirmed NULL across all 34,560 rows in the live DB. Write test confirms correct type acceptance. FINDING: no CHECK constraint for 0.0-1.0 range -- reported, decision deferred to Abdalla.
