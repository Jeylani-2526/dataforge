# Staging Review + Benchmark-Row Cleanup Plan

Closes M5 Item 1 action assigned to Beyza.

---

## Table and Index Sizes

| Table | Rows | Table | Indexes | Total |
|---|---|---|---|---|
| `raw_sensor_events_staging` | 450,000 | 166 MB | 70 MB | **236 MB** |
| `raw_alice_events_staging` | ~68 | — | — | 128 KB |
| `events` | ~150K promoted | — | — | 32 KB |

`raw_sensor_events_staging` dominates storage at 236 MB. The 450,000 rows are a mix of M5W20T2 benchmark runs and the 4.5-hour soak test (M5W20T9).

---

## TimescaleDB Settings

| Parameter | Value | Note |
|---|---|---|
| `shared_buffers` | 1,467 MB | ~25% of available RAM — standard TimescaleDB recommendation |
| `work_mem` | 15,649 KB | ~15 MB per sort/hash operation |
| `max_connections` | 75 | Adequate for current service count |

Settings are within normal range. The 6.9 s insert cost per 50K-row batch (M5W20T2) is attributable to the shuffle partition count and batch size, not to memory misconfiguration.

---

## Insert Cost Analysis

The 6.9 s p95 insert cost measured in M5W20T2 broke down as:

- collect: ~450–530 ms (Kafka fetch)
- enforce: <2 ms (schema validation)
- insert: up to ~6.4 s (DB write under load)

The COPY-based insert introduced in M5W20T1 (commit 59080e9) reduced this significantly from the previous row-by-row insert. Remaining cost is expected under 50K-row batches on a single-node TimescaleDB instance.

No index or settings changes are recommended at this stage. M6 fusion writes will land in `fused_events` (a separate hypertable) and will not increase staging insert pressure.

---

## Benchmark-Row Cleanup Plan

The ~450,000 rows in `raw_sensor_events_staging` are synthetic benchmark data from M5W20T2 runs. They are not production data and are safe to delete.

**Proposed cleanup SQL:**

```sql
-- Count before delete — confirm with Abdullah before running
SELECT COUNT(*) FROM raw_sensor_events_staging;

-- Delete benchmark rows (load_status = 'pending' or 'processed', batch from benchmark runs)
-- Run only after Abdullah sign-off and after T2 restart test passes
TRUNCATE raw_sensor_events_staging;
```

**Conditions before cleanup:**
1. Abdullah sign-off received
2. T2 (checkpointing + restart test) passes — cleanup must not happen while Spark is consuming from staging
3. `TRUNCATE` preferred over `DELETE` — faster, reclaims space immediately, resets sequences

**Expected result after cleanup:**
- `raw_sensor_events_staging`: 0 rows, ~0 MB
- No impact on `events`, `fused_events`, or `raw_alice_events_staging`

---

## Status

Cleanup pending Abdullah sign-off and T2 completion. This note is committed as the agreed plan; the `TRUNCATE` will be executed and confirmed in a follow-up commit once conditions are met.
