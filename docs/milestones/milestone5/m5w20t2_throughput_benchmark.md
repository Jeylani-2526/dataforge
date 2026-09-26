# DataForge — Post-Fix Throughput Benchmark

**Task:** M5W20T2
**Owner:** Abdullah
**Milestone:** M5 · Week 20
**Depends on:** M5W20T1 — `docs/milestones/milestone5/m5w20t1_write_path_root_cause.md`
**Baseline:** M5W19T2 — `docs/milestones/milestone5/m5w19t2_throughput_benchmark.md`
**Status:** Complete. **Bar still missed** (≥10,000 events/sec). The pipeline's own capacity rose
from ~594 to **~3,650 events/sec (6.1×)**, with zero data loss.

---

## 1. Headline results

| Measure | M5W19T2 baseline | Run 2: pooling only | Run 3: full fix | Drain test: full fix |
|---|---|---|---|---|
| **Persisted events/sec** | 594 | ~471 | **1,417** | **~3,650** |
| Window | ~265 s (approx.) | 310 s | 313 s | 562 s steady |
| Rows persisted | 157,479 | 145,951 | 443,529 | 2,191,854 (all) |
| Largest sensor batch | 141,609 rows in 244 s | 134,022 rows in 253 s | 49,999 (capped) | 49,999 (capped) |
| Rejected / errors | 0 / 0 | 0 / 0 | 0 / 0 | 0 / 0 |

**Two headline figures, because they answer different questions:**
- **Like-for-like (Run 3): 1,417 events/sec, 2.4× the baseline.** This uses the same method as
  M5W19T2: unthrottled producers and Spark running at the same time, 5 minutes, staging row-count
  delta. It is the official comparison with the baseline.
- **Pipeline capacity (drain test): ~3,650 events/sec, 6.1× the baseline.** Spark drains a
  pre-built Kafka backlog without the producers competing for CPU. This measures what the pipeline
  itself can do, independent of the generator.

The ≥10,000 events/sec bar is missed on both measures.

---

## 2. What was run

### Code under test

M5W20T1's full change set:
- 8 shuffle partitions (was Spark's default of 200);
- a 50,000-record cap per micro-batch;
- COPY-based staging insert;
- one persistent DB connection per writer;
- per-phase timing logs.

Startup log confirmed:
`shuffle_partitions=8 max_offsets_per_trigger=50000 starting_timestamp_ms=latest`.
`nproc` in the Spark container = 8.

### Run 3: like-for-like (times +03:00)

```
17:09:35   count(raw_sensor_events_staging)  ->    578,705
17:09:46   sensor-generators recreated, SENSOR_PUBLISH_INTERVAL_MS=0
17:14:48   count(raw_sensor_events_staging)  ->  1,022,234
17:15:02   sensor-generators recreated at the default interval (reverted)
```

### Drain test: pipeline capacity (times +03:00)

```
17:16:28   spark-processor stopped
17:16:40   T0 = 1790259400884 (epoch ms)
17:16:44   count -> 1,322,226; sensor-generators unthrottled (Spark not consuming)
17:21:49   sensor-generators stopped. Final totals: radar=731,031 lidar=730,698 telemetry=730,105
17:21:54   spark-processor started with SPARK_STARTING_TIMESTAMP_MS=T0 (replays exactly the backlog)
17:23:29   first sensor micro-batch written (~90 s after restart: JVM start + package download)
17:33:11   last micro-batch written (41,910 rows)
17:33:27   count -> 3,514,080, unchanged at 17:33:58, 17:34:29, 17:35:00
17:35:03   both services restored (no replay timestamp, default producer interval)
```

Logs: `docs/milestones/milestone5/benchmark_logs/`
- `m5w20t2_run3_benchmark_log.txt` and `m5w20t2_run3_producer_log.txt` (Run 3)
- `m5w20t2_drain_benchmark_log.txt` and `m5w20t2_drain_producer_log.txt` (drain test)

---

## 3. Data integrity

**Drain test, published against stored:**
- The drain producer published 2,191,834 events with 0 failed deliveries.
- Rows stored: 3,514,080 − 1,322,226 = **2,191,854**.
- **No events were lost.**
- The 20 extra rows most likely come from the default-rate producer, which was still running for
  ~6 s after T0 before being recreated unthrottled. Its log for those seconds was not captured.

**Consumed against stored:** the windowed monitoring query counted exactly 2,191,854 sensor events
for the replayed period, the same as the rows stored. Every event Spark consumed reached the table.

**All runs:**
- 0 rejected records, 0 duplicates skipped.
- 0 error or traceback lines.
- 0 reconnects; one persistent connection per writer.

---

## 4. Where the time goes now (per 50,000-row batch, median)

| Phase | Drain test | Run 3 (producers competing for CPU) |
|---|---|---|
| collect (Spark job + JVM → Python) | 1.5 s | 2.9 s |
| `enforce()` (drift check + Avro round-trip) | 4.2 s | 8.4 s |
| insert (COPY → temp table → `INSERT … ON CONFLICT`) | **6.9 s** | **12.2 s** |
| **Batch total** | **~12.6 s** | ~23.5 s |

"Batch falling behind" warnings (5 s trigger): drain 47 (median 13.0 s), Run 3: 13 (median 23.2 s).

**Findings:**

1. **The M5W20T1 root cause is removed on the real stack.** Before the fix, collect included minutes
   of waiting for Spark cores behind 200-task windowed batches; it now takes 1.5 s. Batch size is
   bounded at 49,999 as designed.
2. **Per-record work is now the limit, led by the insert.**
   - At ~12.6 s per 50k batch the ceiling is ~4,000 events/sec, which matches the measured ~3,650.
   - Reaching 10,000/sec needs the same batch done in ~5 s.
   - The insert is about 7× slower here than in the M5W20T1 sandbox estimate (~1.0 s per 50k).
   - Likely causes, none confirmed:
     - the staging table has grown to 3.5M rows (random-UUID unique index no longer fits in memory);
     - TimescaleDB memory settings;
     - Docker Desktop disk I/O on Windows.
3. **All services share the same 8 CPUs.**
   - The generator published 7,253 events/sec with Spark stopped, but 3,650/sec with Spark running.
   - Spark's phases roughly doubled while unthrottled producers ran.
   - This is why Run 3 (1,417/sec) sits below capacity.
   - Two further effects on Run 3: ~54 s of its window passed before the first write, and producers
     outpaced Spark, so a backlog built up. The drain test shows the backlog is fully persisted
     later, not lost.
4. **Generator ceiling, revised.** The ~3,400–3,650/sec "ceiling" reported earlier is largely CPU
   contention. The generator alone reaches ~7,250/sec, which is still below the bar.

---

## 5. ALICE stream: idle during Run 3 and the drain test (explained and verified)

**Cause: a clean stop, not a crash.**
- `alice-ingestion` received a stop signal (SIGTERM, exit 0) at 15:20 on 24 September (+03:00),
  before Run 3. `adminer` and `kafka-ui` stopped around the same time. What issued the stop was not
  recorded.
- The later commands started individual services only (`up -d <service>`), so it was never
  restarted.
- A restart policy would not have prevented this, because `on-failure` does not restart a container
  after a clean stop.

**Impact on the results:** none on the sensor figures. ALICE is paced at ~2 events/sec on its own
topic.

**Verified on 25 September after restart:**
- The producer fetched 68 records and published every loop with 0 failures.
- The Spark ALICE writer opened one persistent connection.
- 26 consecutive ALICE micro-batches each logged `0 written, 0 rejected, 9–12 duplicate(s) skipped`
  (collect ~0.5 s, insert 5–9 ms).
- All duplicates is the expected result. The replay loop resends the same 68 `event_id`s, which
  staging has held since 19 August, so `ON CONFLICT` skips them. The old log line reported these
  redeliveries as "written".

**Side observation:**
- `spark-processor` exited with code 137 (force-killed) when the stack stopped on the evening of
  24 September.
- Earlier, `docker compose stop spark-processor` took 11.6 s, longer than Docker's default 10 s
  grace period, so Docker force-kills it on every stop.
- Running out of memory cannot be ruled out afterwards, because the restart reset the container
  state.

## 6. Corrections to M5W19T2 (carried from this analysis)

- **Kafka consumption was double-counted.** Its ~4,300/sec summed every printed row of the
  update-mode window tables, so repeated updates of the same window were counted again (100,883
  events). De-duplicated, it is **~3,919/sec**. The official 594 figure is unaffected.
- **§6 contradicted §3.** §6 said the Kafka/Spark read path "comfortably exceeded the bar"; the read
  side was measured below 10,000/sec.
- **The generator ceiling was misread.** The ~3,400/sec seen earlier was the generator under CPU
  contention, not the read path or the generator's own limit (see §4, finding 4).

---

## 7. Next steps (logged in `open_items_m5.md`)

1. **Insert diagnostics** (read-only):
   - staging table and index sizes;
   - TimescaleDB `shared_buffers`;
   - COPY timing with the table at different sizes.
   Also: agree with Beyza how benchmark rows in staging are cleaned up; staging now holds ~3.5M
   synthetic rows.
2. **Parallel writers.** Split `enforce()` + insert across partitions and connections. This is the
   largest structural lever and changes the per-micro-batch write design, so it needs a design
   decision.
3. **Generator scaling** (several producer processes) and CPU allocation in Docker, so the
   ≥10,000/sec bar can be tested end to end. Proposed owner: Omer.
4. **Clean shutdown:**
   - `spark-processor` does not stop within Docker's 10 s grace period (exit 137); consider
     `stop_grace_period` for it, and check how quickly the shutdown handler stops queries.
   - Before each benchmark, check `docker compose ps -a`, so a stopped producer is noticed
     (see §5).

---

## 8. Conclusion

- **Bar missed:** 1,417 events/sec like-for-like and ~3,650/sec pipeline capacity, against the
  ≥10,000 requirement.
- **Real improvement:** 2.4× like-for-like and 6.1× capacity, with the M5W20T1 root cause removed,
  batch size bounded, and zero data loss or rejections across ~2.6M streamed events.
- **The remaining gap has a measured shape:** insert ~55%, `enforce()` ~33%, collect ~12% of batch
  time. Each next step is aimed at a specific measured cost.
- **Official M5 figures for the validation report:**
  - 1,417 events/sec persisted (like-for-like with M5W19T2);
  - ~3,650 events/sec pipeline capacity (backlog drain).
