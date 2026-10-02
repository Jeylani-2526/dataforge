# DataForge — Real Streaming Throughput Benchmark

**Task:** M5W19T2
**Owner:** Abdullah
**Milestone:** M5 · Week 19
**Originating item:** M5 milestone doc / roadmap — "the resulting throughput is benchmarked
against the ≥10,000 events/sec prototype bar — the real verdict on that bar, superseding
M4's batch-mode measurement." No M5 throughput figure existed anywhere in the repo prior
to this task.
**Status:** Benchmark run and measured. **Bar missed.** Reported exactly as measured,
per task instruction, including that the comparable figure is below M4's own batch-mode
result — not smoothed toward a better-looking number.

> **Correction (M5W20T2):** the ~4,300 events/sec Kafka-consumption figure
> double-counted repeated update-mode window rows. De-duplicated, it is ~3,919/sec, and section 6's
> "comfortably exceeded the bar" does not hold. The official 594 events/sec figure is unaffected.
> The logs referenced below now live in `docs/milestones/milestone5/benchmark_logs/`. See
> `m5w20t2_throughput_benchmark.md` section 6.

---

## 1. Methodology (agreed with the team before running)

- **Consumer prerequisite:** only run after M5W19T1 confirmed all four Spark streams
  healthy and the `sensor_id` bug fixed — an unverified consumer would have made any
  number here meaningless.
- **ALICE left at its normal paced rate.** `docker-compose.yml`'s own comment calls it
  "not a throughput source" by design, and it only has 68 unique records to replay —
  artificially speeding it up wouldn't represent anything real.
- **Sensor generators unthrottled for the run.** `EVENTS_PER_SECOND` (declared in
  `docker-compose.yml`/`.env.example`) turned out to be dead configuration —
  `sensor_producer.py` never reads it (flagged for M5W19T4). The actual throttle is
  `SENSOR_PUBLISH_INTERVAL_MS` (default `200`, one `time.sleep()` per single record
  published). Set to `0` for this run only, via a one-off container recreate, not a
  permanent `docker-compose.yml` change.
- **Duration:** 5 minutes sustained load, to move past startup transients.
- **Measured two ways**, deliberately, because they answer different questions (see
  Section 3): windowed Kafka-consumption counts (the `sensor_throughput` /
  `alice_throughput` console queries already built for this purpose), and the staging
  table's row-count delta (genuine persisted throughput).

---

## 2. Run

```
$ docker exec dataforge-timescaledb psql -U dataforge -d dataforge -c "SELECT count(*) FROM raw_sensor_events_staging;"
 count
--------
 162321

$ SENSOR_PUBLISH_INTERVAL_MS=0 docker compose --profile m3-and-above --profile m5-and-above up -d --build sensor-generators

[... 5 minutes sustained load ...]

$ docker compose logs --since 5m spark-processor > t2_benchmark_log.txt
$ docker compose logs --since 5m sensor-generators > t2_producer_log.txt
$ grep -i "error\|exception\|terminated\|bufferError" t2_benchmark_log.txt t2_producer_log.txt
[no output — no errors during the run]

$ docker exec dataforge-timescaledb psql -U dataforge -d dataforge -c "SELECT count(*) FROM raw_sensor_events_staging;"
 count
--------
 319800
```

No errors, no query terminations, at any point during the run.

---

## 3. Results — two numbers, and why they disagree by ~7x

Windowed console log parsed programmatically (53 distinct 5-second windows, back-to-back,
zero gaps — full continuous coverage of the run, not a sampling artifact):

| Metric | Total events | Span | Throughput |
|---|---|---|---|
| Sensor events **consumed from Kafka** (windowed counts: radar+lidar+telemetry) | 1,139,499 | 265 s | **~4,300 events/sec** |
| Sensor rows **persisted to staging** (`319,800 − 162,321`) | 157,479 | ~265 s (approx. — exact query timestamps not separately logged) | **~594 events/sec** |
| ALICE (both measures — replay-paced, not a throughput source) | 613 events consumed | 265 s | ~2.3 events/sec |

**Both figures miss the ≥10,000 events/sec bar.** They measure different things, and the
gap between them is itself the real finding:

- The **4,300/sec** figure is how fast Spark can read and window-count from Kafka —
  nothing durable happens at that rate. Useful as a diagnostic, not as "pipeline
  throughput."
- The **594/sec** figure is genuine end-to-end throughput — Kafka → Spark →
  TimescaleDB, actually landed and durable — the same definition M4's 1,135.05
  events/sec batch-mode figure used. **This is the comparable, official M5 figure.**

**M5's real streaming throughput (594/sec) is below M4's batch-mode result
(1,135.05/sec).** Not the improvement the M5 milestone doc anticipated
("supersedes M4's batch-mode result"). Reported plainly, not reframed around the
higher (but not meaningfully comparable) 4,300/sec number.

---

## 4. Root cause

Traced to the same design T1's verification note flagged as a risk (Section 4) before
this benchmark ran, now confirmed at scale: both staging writers
(`make_alice_batch_writer` / `make_sensor_batch_writer` in `spark_consumer.py`)
`.collect()` every micro-batch onto the Spark driver, then insert through a **single
psycopg2 connection**, opened fresh (`_get_db_connection()`) and closed on every
micro-batch call. This serializes all writes through one connection and doesn't
parallelize across the batch — so while Kafka/Spark's read side can sustain ~4,300
events/sec, the write side can only push ~594/sec through, and the difference queues up
as a growing backlog rather than being lost (no errors were logged; `ON CONFLICT DO
NOTHING` and no-rejection counts confirm records that are processed are processed
correctly — they're just not persisted fast enough to keep pace with consumption).

---

## 5. What was tried, what wasn't

**Tried:** removing the producer-side artificial throttle (`SENSOR_PUBLISH_INTERVAL_MS`)
— this is what surfaced the write-side bottleneck as the actual constraint, rather than
producer speed.

**Deliberately not tried this week:** reusing a single pooled DB connection across
micro-batches instead of opening one per batch (a plausible partial fix for the
write-side bottleneck identified in Section 4). Discussed as an option; decided against
attempting it this week so the reported number reflects the current committed code
exactly, not a same-day in-progress change. Logged as a concrete follow-up direction
below rather than left vague.

**Environment reverted** after the run — `sensor-generators` recreated without the
`SENSOR_PUBLISH_INTERVAL_MS=0` override, back to the `docker-compose.yml` default of
`200`, so the stack is not left running in an artificially stressed state.

---

## 6. Recommendation for closing the gap (not this week's scope)

The write-side bottleneck (Section 4) is the actionable target — not Kafka, not Spark's
read/window path, both of which comfortably exceeded the bar. Candidate directions for
a future task: connection pooling or a persistent connection reused across micro-batches
(the untried option from Section 5); replacing per-record `execute_batch()` with a bulk
`COPY`-based insert; or partitioning the DataFrame before `foreachBatch` so multiple
connections write concurrently instead of one serial path per micro-batch.

---

## 7. Conclusion

- **Bar missed**, on both measures. Reported as the official M5 figure: **~594
  events/sec** (persisted, end-to-end) — below M4's 1,135.05 events/sec batch-mode
  result.
- **Root cause identified and traced to specific code**, not guessed — the
  driver-collect + single-connection write path in `spark_consumer.py`, flagged as a
  risk in M5W19T1's note before this benchmark confirmed it at scale.
- **No errors or data corruption** — the gap is a throughput ceiling, not data loss.
- Fix deferred to a future task per this week's decision; direction is concrete
  (Section 6), not open-ended.
