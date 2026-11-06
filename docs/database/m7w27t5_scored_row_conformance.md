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

`enforce()` validates against `fused_event_schema_v1.avsc`. That schema carries no `anomaly_label`, `risk_score`, or `confidence` field — confirmed by M6W26T1 conformance check (PASS, 2026-11-05). The enforcement round-trip cannot introduce these values.

---

## 3. Database Verification

From M6W26T1 (executed 2026-11-05, 34,560 rows, 1,000 sampled):

| Column | NULL count in sample | Result |
|---|---|---|
| `anomaly_label` | 1,000 / 1,000 | PASS |
| `risk_score` | 1,000 / 1,000 | PASS |
| `confidence` | 1,000 / 1,000 | PASS |

All M7 nullable columns are NULL across the full 34,560-row table. No write path populates them before M7 inference.

---

## 4. M7 Write Path (forward reference)

When M7W28T3 (Live Inference) runs, the scoring engine will UPDATE these columns in-place per fused row. The write path for that update is outside the current scope and will be verified in M7W28T8.

---

## 5. Gate Status

**PASS** -- M7 nullable columns (`anomaly_label`, `risk_score`, `confidence`) are absent from `FUSED_FIELDS`, absent from record construction, and confirmed NULL across all 34,560 rows in the live DB. The write path does not corrupt M7 scoring inputs.
