# DataForge — Throughput Root-Cause Investigation & Partition-Fix Attempt

**Task:** M4W16T3
**Owner:** Abdullah
**Milestone:** M4 · Week 16 (Finalization & M4 Package)
**Originating item:** `open_items_m4.md` Item 5 (full-volume run throughput below prototype bar)
**Status:** Investigation complete. Gap not closed. Modest, measured improvement found and kept. Root cause identified as architectural — a bigger fix than this week's scope, flagged for M5 consideration.

---

## 1. What this investigates

`open_items_m4.md` Item 5 logged M4W15T4's full-volume run at **1,665.56 events/sec** against a locked prototype bar of **≥10,000 events/sec** — roughly a 6x gap — and deferred root-causing it to this week. The item's own action items asked for two things specifically:

1. Confirm the actual Spark partition count used during the M4W15T4 run (`df.rdd.getNumPartitions()` on the sensor DataFrame), to verify the "single large task" hypothesis suggested by the original run's Spark warnings.
2. Evaluate splitting `parquet_writer.py`'s three-pass, per-sensor-type Parquet write into a single partitioned write.

Both were carried out. The findings below **refine** the original hypothesis rather than confirm it as literally stated, and the fix attempted did not close the gap — reported here exactly as measured, per the item's own instruction not to smooth this toward the prototype bar.

---

## 2. Partition count confirmation

A diagnostic script (`check_sensor_partitions.py`, not part of the production pipeline) was used to check the sensor DataFrame's actual partitioning, reusing `parquet_writer.py`'s own `read_avro_records()` / `records_to_dataframe()` functions unmodified so the check reflects the real construction path.

**Result:**

| Metric | Value |
|---|---|
| `df.rdd.getNumPartitions()` | **8** |
| `spark.sparkContext.defaultParallelism` | **8** |
| Sensor records | 150,000 |

**Finding:** the DataFrame is **not** a single partition — it's 8, matching the local machine's default parallelism (core count). The "single large task" framing in `open_items_m4.md` needs correcting: the `TaskSetManager: ... contains a task of very large size (3702–3703 KiB)` warning fires across all 8 tasks, not because there's only one. Increasing partition count would not, by itself, resolve this warning.

**A second, independent finding surfaced during this check:** the diagnostic script itself crashed twice (`Connection reset by peer` / `EOFError`) when attempting a heavier per-partition breakdown (`df.rdd.glom().collect()`), which pulls full partition contents back to the driver over the same local socket channel `spark.createDataFrame()` uses to ship data to the JVM in the first place. This is evidence, independent of the main pipeline run, that the underlying data-transfer path is fragile at this row count on this machine — not just slow.

---

## 3. Root cause

The real bottleneck is architectural, not a partition-count problem:

`parquet_writer.py`'s `records_to_dataframe()` calls `spark.createDataFrame(records)` on a plain Python list, built by reading the entire sensor Avro output into driver memory via `fastavro` first. This means:

- The full 150,000-record list must exist in the Python driver process before Spark can begin distributing anything.
- Handing that list to Spark requires pickling it and shipping it to the JVM over a local socket connection — an inherently serial, single-threaded-from-the-driver's-perspective step, regardless of how many partitions the resulting DataFrame ends up with.
- This step is also fragile at this volume, as shown by the diagnostic script crashes in Section 2.

Compounding this: `convert_sensor_streams_to_parquet()` builds `df` once, but performs 3 filter operations (one per RADAR/LIDAR/TELEMETRY) and each triggers **two** actions (`write_dataframe_to_parquet()` calls both `.count()` and `.write.parquet()`). Without caching, every one of those up-to-6 actions re-triggers the expensive construction above from scratch.

---

## 4. Fix attempted: caching

`df.cache()` was added immediately after DataFrame construction in `convert_sensor_streams_to_parquet()`, with `df.unpersist()` after the loop. This keeps the existing three-directory output layout (`parquet_root/radar`, `/lidar`, `/telemetry`) that `test_round_trip_conversion.py` depends on — `pytest test_round_trip_conversion.py` was re-run and confirmed passing (3 passed) after this change.

**A true single partitioned write (`df.write.partitionBy("sensor_type")`) was evaluated and deferred.** It would write in one pass, but Spark's `partitionBy` produces a different on-disk layout (`sensor_type=RADAR/` instead of `radar/`), which would require updating `test_round_trip_conversion.py` and confirming nothing else downstream depends on the current directory names — a larger, riskier change than this week's timeline supports for a fix that is not confirmed to close a 6x gap.

### Two additional bugs found and fixed while verifying this (not part of the original five open items)

1. **`avro_adaptation_job.py` had its own instance of the 5432/5433 port mismatch** already flagged to Beyza in `promote_to_production.py` — `DB_PORT` defaulted to `5432`, but the project's only TimescaleDB instance (the Docker container) publishes host port `5433`. This blocked every attempt to re-run `full_volume_run.py` for verification until corrected.
2. **`avro_adaptation_job.py` was missing `sc.addPyFile()` for itself.** The file already ships `schema_versioning.py` to Spark worker processes for exactly this reason, but never applied the same fix to its own module — needed because `write_avro()`'s `_partition_writer` (used inside `df.rdd.mapPartitionsWithIndex()`) is defined in `avro_adaptation_job.py` itself. Without this, running the pipeline from any working directory other than `services/adaptation-layer/` (which the script's own relative `schemas/` path otherwise requires) failed with `ModuleNotFoundError: No module named 'avro_adaptation_job'` inside the worker.

Both are fixed in the committed code as of this task.

---

## 5. Measured results

| Run | Wall-clock | Throughput (events/sec) | Notes |
|---|---|---|---|
| Original M4W15T4 baseline | ~90s | **1,665.56** | Pre-M4W16T3; neither the port fix, the addPyFile fix, nor the cache fix existed yet. |
| M4W16T3, with cache fix (+ port fix + addPyFile fix) | 131.35s | **1,142.5** | |
| M4W16T3, without cache (control; same port + addPyFile fixes) | 190.42s | **788.11** | Isolates the cache fix's effect from the other two fixes' overhead. |

Data loss (0.0%) and p95 latency (0.14–0.15ms) passed their bars in every run above; throughput is the only metric outside spec in all three.

**Reading these numbers honestly:**

- Comparing the two M4W16T3 rows (same environment, same port/addPyFile fixes, cache present vs. absent) isolates the cache fix's actual effect: **~45% faster with caching than without it** (1,142.5 vs. 788.11 events/sec). This is a real, measured improvement, not a wash.
- Neither M4W16T3 row reaches the original 1,665.56 baseline, let alone the ≥10,000 bar. Something in the current environment — most plausibly the `addPyFile` step, which now ships the whole module to workers on every run, an overhead the original baseline never paid — is adding cost across the board that the cache fix doesn't touch. This wasn't isolated further this week; flagged for anyone revisiting this in M5's context.
- The caching fix is kept in the committed code on the strength of the controlled comparison in the row above, not because it closes the gap — it doesn't.

---

## 6. Conclusion and disposition of `open_items_m4.md` Item 5

**The throughput bar is still missed.** The gap is not closed by this week's investigation or fix attempt, and is reported here exactly as measured per the open item's own instruction.

**What was accomplished:**
- The "single large task" hypothesis was tested directly and found to be incomplete: partition count is 8, not 1, matching local default parallelism.
- The actual root cause was identified: the Python-driver-side `spark.createDataFrame()` construction from a fully-materialized Python list, which is both expensive and fragile at this row count — a Spark-usage-pattern issue, not a partition-count issue.
- A modest, real fix (caching) was implemented, tested, and measured at ~45% faster than without it, in a controlled comparison.
- Two previously-unflagged bugs blocking verification were found and fixed.

**What remains open:** closing the full 6x gap would require avoiding the driver-side Python list materialization entirely — e.g. having Spark read Avro through a genuinely distributed reader rather than via `fastavro` into a Python list — which is a larger architectural change than this week's scope. Per the open item's own rationale, **M5's Kafka + Structured Streaming throughput benchmark is the roadmap's actual throughput deliverable** and will supersede this M4 batch-mode figure regardless. This M4 number should be carried forward as a baseline, not a final verdict, consistent with the open item's original framing — recommend M5 planning treat the driver-side-materialization pattern as a design constraint to avoid from the outset, rather than something to patch again.

**Recommendation:** carry Item 5 forward to the M4 package (T8) exactly as it stands — gap open, this week's investigation and partial fix documented — and flag the architectural root cause as an input to M5 kickoff planning.
