# DataForge — Streaming Write-Path Throughput: Root Cause & Fix

**Task:** M5W20T1 (extended; scope approved by Abdullah, 24 September 2026)
**Owner:** Abdullah
**Milestone:** M5 · Week 20
**Related:** M5W19T2 (baseline, 594 events/sec), M5W20T2 (post-fix benchmark),
M4W16T3 (`docs/milestones/milestone4/throughput_root_cause_m4w16t3.md`)
**Status:** Root cause identified, reproduced and fixed. Confirmed on the real Docker stack in
M5W20T2: pipeline capacity ~3,650 events/sec (6.1× the baseline), zero data loss. The bar is not
yet met; the remaining per-record costs are measured in M5W20T2 §4.

---

## 1. Summary

The ~500–600 events/sec ceiling was **not** caused by the database insert, `enforce()`, or the
driver-side `.collect()`. It was caused by **Spark's default `spark.sql.shuffle.partitions = 200`**.
Every trigger, each of the two windowed monitoring queries split a tiny count into 200 stateful
tasks. On a `local[*]` session with ~8 task slots, those tasks occupied the cores, and the staging
writes spent most of each micro-batch waiting for a free slot.

The originally planned fix (a pooled connection, M5W19T2 §5) was applied and measured first. It
works as designed but did not change throughput, which is what prompted this investigation.

---

## 2. Method

Stages were measured one at a time with the **real committed code and schemas**, then the full
query layout was reproduced end to end.

- **Environment:** a 1-core Linux sandbox; PostgreSQL 16 (same major version as
  `timescale/timescaledb:latest-pg16`) loaded with the real staging DDL from `init-db.sql`; PySpark
  3.5.9 (same as `requirements.txt`).
- **Data:** 134,022 records from the real `sensor_producer.py` generators, the size of the largest
  production micro-batch in M5W19T2 and M5W20T2.
- **Table state:** preloaded to 430,000 rows so index sizes match the real table.
- **Limits of the method:** Kafka is replaced by a file source (10,000 records per micro-batch). The
  sandbox has 1 core against ~8 on the real machine. **Absolute numbers will differ on the real
  stack; the comparisons between configurations are the finding.**

---

## 3. Elimination: time per stage for 134,022 records

| Stage | Time | Share of the 252 s production batch |
|---|---|---|
| `.collect()` + `row.asDict()` (JVM → Python) | 2.6 s | ~1% |
| `schema_versioning.enforce()` (drift + Avro round-trip) | 3.8 s | ~1.5% |
| Insert, `execute_batch` page 500 (code at the time) | 11.2 s | ~4.4% |
| **Sum of the write path's own work** | **~18 s** | **~7%** |

Insert strategies on the same table (430k rows, 6 indexes):

| Insert method | 134,022 rows | Rows/sec |
|---|---|---|
| `execute_batch`, page 500 (code at the time) | 11.2 s | ~12,000 |
| `execute_values`, page 1,000 | 8.3 s | ~16,200 |
| `COPY` → temp table → `INSERT … ON CONFLICT DO NOTHING` | 2.8 s | ~48,600 |

About 93% of the real batch time was therefore spent outside the write path's own work.

---

## 4. Root cause, reproduced

The consumer's four queries (two windowed, two `foreachBatch` staging writers) were rebuilt with
the real `make_sensor_batch_writer`. Persisted throughput, same 134,022 records:

| Configuration | Old writer | New writer (COPY) |
|---|---|---|
| 200 shuffle partitions (Spark default, code at the time) | **512/s** | 496/s |
| 8 shuffle partitions | 2,292/s | 2,649/s |
| 1 shuffle partition (matches the 1-core sandbox) | 2,913/s | **3,488/s** |
| Staging query alone, no windowed queries (reference only; the design requires them) | 4,278/s | — |

**Evidence:**
- **The current configuration reproduces production.** 512/s here against 594/s (M5W19T2) and
  ~471/s (M5W20T2).
- **The windowed queries are the cost.** With 200 partitions, each windowed micro-batch took a median
  of ~17.8 s. With 8 partitions it took ~2.8 s, and with 1 partition ~1.6 s.
- **Per-phase timing shows the waiting.** Under 200 partitions, `collect` for a 10,000-row batch took
  20.0 s and 7.4 s. Under 8 partitions it took ~1 s. `collect` is where the Spark job runs, so this
  time is queueing for executor slots, not data transfer.
- **It explains an earlier puzzle.** In M5W20T2, ALICE micro-batches of 3–51 rows took 12–14 s each,
  which only makes sense if the executor was saturated.

**Relation to M4W16T3:** M4's bottleneck was the serial Python ↔ JVM transfer on the driver. The
same pattern exists here (`.collect()`), but it measured at only ~1% of batch time. It becomes
relevant again only at much higher rates (see §7).

---

## 5. Changes

All changes are in `services/streaming/spark/src/spark_consumer.py` unless noted.

| # | Change | Why |
|---|---|---|
| T1 | One persistent psycopg2 connection per writer, with reconnect and one retry | The planned fix. Kept: correct and cheap, though not the bottleneck. |
| A1 | `spark.sql.shuffle.partitions` = `SPARK_SHUFFLE_PARTITIONS` (default 8) | The root cause. Explicit rather than auto-detected, so runs are reproducible across machines. |
| A2 | Kafka `maxOffsetsPerTrigger` = `SPARK_MAX_OFFSETS_PER_TRIGGER` (default 50,000; 0 = off) | Bounds batch size (10k/s × 5 s trigger). Prevents 134k-row driver collects and 250 s batches, which would also fail the ≤500 ms p95 latency bar in M10. |
| B | Staging insert: `COPY` into a session temp table, then `INSERT … SELECT … ON CONFLICT (event_id) DO NOTHING` | ~4x faster than `execute_batch`, with the same duplicate handling. At 50k rows per batch the old insert (~4.2 s) would have used most of the 5 s trigger. |
| C | Per-batch log: `collect=…ms enforce=…ms insert=…ms`, plus `duplicate(s) skipped` | Makes the next bottleneck visible without another investigation. |
| — | Optional `SPARK_STARTING_TIMESTAMP_MS` replay point (Kafka `startingTimestamp`, fallback `latest`) | Needed for the backlog-drain test; also useful for M6 replay testing. Empty = unchanged behaviour. |
| — | The two writers share one implementation; the rejection reason is logged | Removes duplicated code; data-loss causes become visible. |

Supporting changes:
- **`docker-compose.yml` / `.env.example`:** the three new settings, following the
  `WATERMARK_DELAY_SECONDS` pattern.
- **`.github/workflows/ci.yml`:** installs `services/streaming/spark/requirements.txt` so the new
  tests run in CI.
- **`services/streaming/spark/src/test_spark_consumer.py`:** 13 tests (details in §6).

**Unchanged by design:**
- The watermark/window design note §5: windowed monitoring queries kept, `foreachBatch` staging
  write, and `enforce()` per micro-batch, unmodified.
- `schema_versioning.py` is not modified.

**Log meaning change:** "written" now means rows actually inserted (from `cur.rowcount`).
Redelivered duplicates are reported separately. The line's prefix is unchanged, so existing parsers
still match.

---

## 6. Verification

**Equality, old vs new writer** (identical input into two databases, all columns compared):
- **Inputs:** 5,000 generator records plus edge cases:
  - empty strings and NULLs;
  - commas, quotes, CR/LF, backslashes, a literal `\N`, tabs, and unicode;
  - float32 extremes and a BIGINT maximum;
  - a NaN record (rejected by both writers);
  - in-batch duplicates and a redelivered batch.
- **Result:** identical, with one intended difference. The old path stored `-0.0` as `0`, because
  psycopg2 sends a numeric literal and Postgres `numeric` has no negative zero. COPY keeps `-0.0`, as
  Avro does. `-0 = 0` is true in SQL, so no data is lost.

**Tests:**
- 13 pass, including one against a real Postgres.
- The full `pytest services/` suite passes: 15 passed, 1 skipped (the real-database test, which is
  skipped without `DATAFORGE_TEST_DB_DSN`).
- flake8 is clean at CI's settings.

**Mutation check:** each of these deliberate breakages made tests fail:
- writing NULL as an empty string;
- removing `ON CONFLICT`;
- not rewinding the COPY buffer on retry.

**Kafka options:** checked against the Spark 3.5 Kafka integration guide (`maxOffsetsPerTrigger`,
`startingTimestamp`, `startingOffsetsByTimestampStrategy`).

**Real stack (M5W20T2):** confirmed with the Kafka source on 8 cores. Batches are capped at
49,999, collect dropped to ~1.5 s per 50k batch, and no errors, rejections or losses occurred.
The ALICE write path was verified separately on 25 September: 26 micro-batches of redelivered
events, all correctly skipped as duplicates (M5W20T2 §5).

---

## 7. Future considerations (for T4 / M6 / M10)

1. **Generator ceiling.** Unthrottled, `sensor_producer.py` publishes ~3,400–3,500 events/sec from
   one Python loop. A normal run cannot show more than that. Scaling it (several producer processes)
   is needed before the ≥10,000 bar can be tested end to end. Proposed owner: Omer (roadmap:
   synthetic data generation).
2. **Checkpointing (open since M5W19T1).**
   - When it is added, Spark locks the shuffle partition count into the checkpoint for stateful
     queries; changing it later needs a new checkpoint.
   - Setting the value now, before checkpoints exist, is deliberate.
   - `SPARK_STARTING_TIMESTAMP_MS` only applies to fresh queries.
3. **M6 stream-stream join.** The join is stateful and will use the same shuffle partition setting;
   size it with the same rule (≈ cores).
4. **Next bottlenecks at higher rates.**
   - Per 50k rows, this sandbox measured: collect ~1.0 s, `enforce()` ~1.4 s, COPY ~1.0 s.
   - The driver-side Python path (collect + `enforce()`) stays single-threaded.
   - Options if needed:
     - Arrow-based transfer (needs pyarrow/pandas in the image);
     - per-partition writes;
     - more Kafka topic partitions (each sensor topic currently has 1, which limits read parallelism).
5. **Staging schema changes.** The COPY temp table copies column types from the staging table at
   first use per connection, so a staging `ALTER` needs a consumer restart.
   `test_staging_columns_match_init_db_sql` fails if the column lists drift from `init-db.sql`.
