# M6 W26 T7 — Cross-Machine Build Verification

**Test date:** 8 November 2026
**Test machine:** Windows laptop (PowerShell)
**Working directory:** C:\Users\asus\dataforge
**Git branch:** develop
**Baseline commit:** 62b2ce9
**Compose profiles:** m3-and-above, m4-and-above, m5-and-above, m6-and-above

## Executive Result

**PASS after local workaround; unmodified baseline clean startup FAIL.**

All five application images built successfully without cache. The initial startup failed during TimescaleDB initialization. After a local SQL policy correction and volume recreation, TimescaleDB became healthy.

The Fusion Engine initially terminated with a Kafka topic/partition error. Following a restart, fused_events increased from 323 to 395.

Both the replay-safe index and continuous aggregate were verified.

## Step-by-Step Results

| Step | Action | Result |
| --- | --- | --- |
| 1 | Update develop and record commit | PASS (reported) |
| 2 | Docker Compose down -v | PASS |
| 3 | Build all profiles with --no-cache | PASS |
| 4 | Start all profiles | FAIL initially; PASS after workaround |
| 5 | Stage ALICE data | PASS |
| 6 | Promote ALICE data | PASS |
| 7 | Restart alice-ingestion | PASS |
| 8 | Verify fused_events increases | PASS after restart |
| 9 | Verify replay-safe index | PASS |
| 10 | Verify continuous aggregate | PASS |

## Docker Build

Command:

    docker compose --profile m3-and-above --profile m4-and-above --profile m5-and-above --profile m6-and-above build --no-cache

Successfully built images:

- dataforge-spark-processor
- dataforge-fusion-engine
- dataforge-sensor-generators
- dataforge-alice-ingestion
- dataforge-adaptation-layer

Build duration: 648.8 seconds.

**Result: PASS**

## Issue 1 — TimescaleDB Initialization

Initial Docker Compose startup failed:

    Container dataforge-timescaledb Error dependency timescaledb failed to start
    dependency failed to start: container dataforge-timescaledb exited (3)

Exact database error:

    2026-11-08 07:17:05.223 UTC [82] ERROR:  policy refresh window too small
    2026-11-08 07:17:05.223 UTC [82] DETAIL:  The start and end offsets must cover at least two buckets in the valid time range of type "bigint".
    2026-11-08 07:17:05.223 UTC [82] STATEMENT:  SELECT add_continuous_aggregate_policy('summary_5min',
                start_offset => BIGINT '600000',
                end_offset   => BIGINT '300000',
                schedule_interval => INTERVAL '5 minutes',
                if_not_exists => TRUE);
    psql:/docker-entrypoint-initdb.d/init.sql:163: ERROR:  policy refresh window too small
    DETAIL:  The start and end offsets must cover at least two buckets in the valid time range of type "bigint".

### Workaround

File:

    infrastructure/scripts/init-db.sql

Original:

    start_offset => BIGINT '600000',

Modified locally:

    start_offset => BIGINT '900000',

After this change, Docker volumes were recreated and services started successfully.

TimescaleDB: Healthy
Kafka: Healthy

**Result: PASS after local workaround.**

This workaround was not part of baseline commit 62b2ce9.

## Issue 2 — Fusion Engine Startup

Initially, fused_events remained empty and Fusion Engine exited.

The captured error was:

    org.apache.kafka.common.errors.UnknownTopicOrPartitionException: This server does not host this topic-partition.

Relevant Spark error:

    java.util.concurrent.ExecutionException: org.apache.kafka.common.errors.UnknownTopicOrPartitionException: This server does not host this topic-partition.

    at java.base/java.util.concurrent.CompletableFuture.reportGet(CompletableFuture.java:396)
    at java.base/java.util.concurrent.CompletableFuture.get(CompletableFuture.java:2073)
    at org.apache.kafka.common.internals.KafkaFutureImpl.get(KafkaFutureImpl.java:165)
    at org.apache.spark.sql.kafka010.ConsumerStrategy.retrieveAllPartitions(ConsumerStrategy.scala:66)
    at org.apache.spark.sql.kafka010.SubscribeStrategy.assignedTopicPartitions(ConsumerStrategy.scala:113)
    at org.apache.spark.sql.kafka010.KafkaOffsetReaderAdmin.fetchLatestOffsets(KafkaOffsetReaderAdmin.scala:297)

    Caused by: org.apache.kafka.common.errors.UnknownTopicOrPartitionException: This server does not host this topic-partition.

Application log:

    2026-11-08 07:24:37,812 ERROR Fusion query terminated with an exception: [STREAM_FAILED] Query terminated with exception: org.apache.kafka.common.errors.UnknownTopicOrPartitionException: This server does not host this topic-partition.
    2026-11-08 07:24:38,164 INFO Fusion query is no longer active — exiting.

Kafka topics verified:

    alice-events
    sensor-lidar
    sensor-radar
    sensor-telemetry

Recovery command:

    docker compose restart fusion-engine

After restarting, the Fusion Engine began producing fused events.

**Result: PASS after restart.**

The exact cause of the initial Kafka error was not conclusively established.

## ALICE Ingestion

Staging command:

    python scripts/ingestion/staging_ingestion_script.py "$HOME\alice_seed"

Output:

    2026-11-08 10:24:06,966 INFO alice.jsonl stream=alice batch=690077ee loaded=68 failed=0 duplicates=0
    2026-11-08 10:24:06,969 INFO DONE — files=1 total_loaded=68 total_failed=0 total_duplicates=0

Promotion command:

    python scripts/ingestion/promote_to_production.py

Output:

    2026-11-08 10:24:29,253 INFO ALICE — promoted=68 skipped=0
    2026-11-08 10:24:29,258 INFO SENSOR — promoted=0 skipped=0
    2026-11-08 10:24:29,259 INFO DONE total_promoted=68 total_skipped=0

**Result: PASS**

## Database Verification

All checks were executed with psql inside the TimescaleDB container.

### Fused Events

Query:

    SELECT COUNT(*) FROM fused_events;

Initial measurements:

    0
    0
    0

After Fusion Engine restart:

| Measurement | Count |
| --- | ---: |
| First measurement | 323 |
| Second measurement | 395 |
| Increase | +72 |

**Result: PASS**

The exact time interval between the final measurements was not recorded.

### Replay-Safe Index

Query:

    SELECT indexname FROM pg_indexes WHERE tablename='fused_events';

Observed:

    fused_events_pkey
    fused_events_timestamp_ms_idx
    idx_fused_time_label
    uq_fused_events_replay

**Result: PASS — uq_fused_events_replay exists.**

### Continuous Aggregate

Query:

    SELECT view_name FROM timescaledb_information.continuous_aggregates;

Observed:

    summary_5min

**Result: PASS — summary_5min exists.**

## Additional Observations

- Docker Compose reported an obsolete version attribute warning.
- The adaptation-layer container exited with code 0 after its smoke test.
- The initial Fusion Engine startup encountered a Kafka topic/partition error.
- A PowerShell parser error occurred when SQL was entered directly into PowerShell.
- The SQL policy correction remains local unless separately committed and merged.

## Final Assessment

**T7 outcome: PASS with documented interventions.**

Verified:

- Five Docker images built without cache.
- TimescaleDB became healthy after the SQL workaround.
- ALICE ingestion successfully processed 68 records.
- Fusion Engine produced increasing fused_events counts.
- Replay-safe index uq_fused_events_replay exists.
- Continuous aggregate summary_5min exists.

Not verified:

- Fully automatic clean startup using the unmodified baseline commit.

Follow-up actions:

1. Review and merge the TimescaleDB refresh-policy correction.
2. Investigate Kafka readiness and Fusion Engine startup sequencing.
3. Confirm adaptation-layer service lifecycle expectations.
4. Repeat clean-start verification after the permanent fix.

**Conclusion:** Functional cross-machine verification succeeded after documented interventions. Strict no-intervention clean-start reproducibility failed for baseline commit 62b2ce9.



## Re-test (2026-11-13)

### Environment
- **OS:** Windows (PowerShell)
- **Project:** Dataforge M6
- **Test:** T7 Cross-Machine Build
- **Docker Compose profiles:** m3-and-above, m4-and-above, m5-and-above, m6-and-above

### 1. Docker Build and Startup
- Executed `docker compose down -v` to remove existing containers and volumes.
- Rebuilt and started the environment using `docker compose up -d --build` with all required profiles.
- Docker Compose completed successfully (`19/19`).
- Kafka and TimescaleDB reported healthy status.
- **Policy refresh window error:** No. The previously encountered TimescaleDB policy error did not reappear during this re-test.

### 2. Alice Data Ingestion
- Loaded `alice.jsonl` into staging.
- **Alice staging:** 68 records loaded, 0 failed, 0 duplicates.
- **Production promotion:**
  - ALICE: 68 records promoted.
  - SENSOR: 1,006 records promoted.
  - Total: 1,074 records promoted, 0 skipped.
- Restarted the `alice-ingestion` service.

### 3. Fusion Engine Startup
- **Did Fusion Engine start successfully on the first attempt?** No.
- The initial Fusion Engine process terminated after encountering a Kafka topic/partition error:

  `UnknownTopicOrPartitionException: This server does not host this topic-partition.`

- Verified that the required Kafka topics were present:
  - `alice-events`
  - `sensor-lidar`
  - `sensor-radar`
  - `sensor-telemetry`
- Restarted Fusion Engine using:

  `docker compose --profile m6-and-above up -d fusion-engine`

- Following the restart, Fusion Engine remained running and successfully processed streaming micro-batches.
- Fusion logs confirmed successful database writes with 0 rejected records and 0.0000% reported data loss.

### 4. Fused Events Verification
Executed the following SQL query against TimescaleDB:

`SELECT COUNT(*) FROM fused_events;`

| Measurement | Fused Events Count |
|-------------|-------------------:|
| First measurement | 123 |
| Second measurement | 130 |
| Additional verification 1 | 193 |
| Additional verification 2 | 202 |

- The count increased from 123 to 130 between the first two measurements.
- Subsequent measurements confirmed continued growth to 193 and 202.
- This verifies that Fusion Engine was actively writing records to TimescaleDB.

### 5. Additional Observations
- Kafka and TimescaleDB remained healthy.
- Fusion Engine successfully resumed processing after restart.
- Fusion micro-batch logs reported 0 rejected records and 0.0000% data loss.
- Heartbeat logs still reported `status=critical` for ALICE and SENSOR, indicating a remaining latency/quality issue requiring separate investigation.
- Docker Compose displayed an obsolete `version` attribute warning, which did not prevent startup.

### 6. Final Result
**Re-test result: PASS WITH OBSERVATIONS**

- **Policy error encountered:** No.
- **Fusion Engine started successfully on first attempt:** No.
- **Fusion Engine restart required:** Yes.
- **Fused events (two measurements):** 123 → 130.
- **Additional verification:** 193 → 202.
- **Final outcome:** Docker build succeeded, ingestion and promotion completed, and the end-to-end fusion pipeline was confirmed operational after restarting Fusion Engine.

**Follow-up:** Investigate Fusion Engine startup ordering and heartbeat latency/quality warnings.
