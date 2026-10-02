# DataForge — Spark Consumer End-to-End Verification (M5W18T8/T9 Close-Out)

**Task:** M5W19T1
**Owner:** Abdullah
**Milestone:** M5 · Week 19
**Originating context:** `M5W18T8_and_half_T9` (commit `37ce516`) added all four
`writeStream` queries (`alice_throughput`, `sensor_throughput`, `alice_staging_write`,
`sensor_staging_write`) but the commit message itself called the work "half" — no prior
verification note or test run confirmed it had ever been exercised against live Kafka.
**Status:** All four streams confirmed healthy end-to-end. One blocking bug found and
fixed during this task (see Section 3) — `sensor_staging_write` did not survive first contact
with live data before the fix. Checkpointing gap formally logged as an M5 open item
(Section 5), per task instruction, rather than left as an inline code comment only.

---

## 1. Stack brought up

```
$ docker compose --profile m3-and-above --profile m5-and-above up -d --build kafka timescaledb kafka-ui adminer sensor-generators alice-ingestion spark-processor
```

Note: the Week 19 plan's own suggested command (`--profile m5-and-above` alone) is
insufficient — `sensor-generators` is scoped `profiles: ["m3-and-above"]` in
`docker-compose.yml`, and Compose profiles are exact-match, not hierarchical. Running
with only `m5-and-above` would leave the sensor generators off entirely and the
consumer would only ever see `alice-events`, not all four topics. Corrected here for
whoever runs this next.

```
$ docker compose ps
NAME                          STATUS                    PORTS
dataforge-adminer             Up 46 minutes
dataforge-alice-ingestion     Up 45 minutes
dataforge-kafka               Up 46 minutes (healthy)   0.0.0.0:9092->9092/tcp
dataforge-kafka-ui             Up 45 minutes             0.0.0.0:8080->8080/tcp
dataforge-sensor-generators   Up 7 minutes   [post-fix rebuild, see Section 3]
dataforge-spark               Up 7 minutes   [post-fix rebuild, see Section 3]
dataforge-timescaledb         Up 46 minutes (healthy)   0.0.0.0:5433->5432/tcp
```

All seven containers up; both healthchecked services (`kafka`, `timescaledb`) report
`healthy`.

---

## 2. All four writeStream queries confirmed healthy

### 2a. Windowed throughput queries (console sink)

`alice_throughput`, 25+ batches, non-empty windowed counts per 5-second tumbling
window, e.g.:

```
Batch: 1
+------------------------------------------+------------+-----+
|window                                    |topic       |count|
+------------------------------------------+------------+-----+
|{2010-12-06 05:17:25, 2010-12-06 05:17:30}|alice-events|1    |
|{2010-12-06 05:17:35, 2010-12-06 05:17:40}|alice-events|14   |
```

`sensor_throughput`, same batch cadence, all three sensor topics represented across
the run (`sensor-radar`, `sensor-lidar`, `sensor-telemetry`), e.g.:

```
Batch: 6
+------------------------------------------+----------------+-----+
|window                                    |topic           |count|
+------------------------------------------+----------------+-----+
|{2026-09-20 08:57:20, 2026-09-20 08:57:25}|sensor-telemetry|5    |
|{2026-09-20 08:57:25, 2026-09-20 08:57:30}|sensor-telemetry|5    |
```

**Observation, not a bug:** `alice_throughput`'s window timestamps read `2010-12-06`,
not the current date. This is correct — `alice_producer.py` replays real ALICE Run 1
detector data, and the consumer windows on each record's own `timestamp_ms` (event
time, per the M5W17T2 watermark/window design), which is the original 2010 physics-run
timestamp, not Kafka ingestion time. Documented here so it doesn't read as a defect to
someone checking this note later.

**Observation, logged for T2's benchmark methodology:** the log shows repeated
`ProcessingTimeExecutor: Current batch is falling behind` warnings, with individual
micro-batches taking up to 17.6s against the 5-second trigger interval. Not a failure,
but a likely throughput constraint independent of Kafka/Spark's raw capacity — see Section 4.

### 2b. Non-windowed staging writes (`foreachBatch`)

`alice_staging_write` — 40+ micro-batches, 0 rejected throughout, e.g.:

```
2026-09-20 08:58:43,227  INFO  ALICE micro-batch 24 (db batch=22bd95a9): 13 written, 0 rejected (data_loss_pct=0.0000%).
```

`sensor_staging_write` — post-fix (Section 3), 29 micro-batches, 0 rejected:

```
2026-09-20 08:59:54,841  INFO  SENSOR micro-batch 28 (db batch=7f7593de): 41 written, 0 rejected (data_loss_pct=0.0000%).
```

**Note on "N written":** this counts records that passed `schema_versioning.enforce()`,
not rows actually inserted. `raw_alice_events_staging` stayed at its pre-existing 68
rows throughout this run despite 1,300+ cumulative "written" ALICE records — expected,
since `alice_producer.py` replays the same 68 `event_id`s on a loop and
`ON CONFLICT (event_id) DO NOTHING` correctly no-ops the repeats. Confirmed via direct
SQL, not Adminer:

```
$ docker exec dataforge-timescaledb psql -U dataforge -d dataforge -c "SELECT count(*) FROM raw_alice_events_staging;"
 count
-------
    68

$ docker exec dataforge-timescaledb psql -U dataforge -d dataforge -c "SELECT batch_id, count(*), max(load_timestamp) FROM raw_alice_events_staging GROUP BY batch_id ORDER BY max(load_timestamp) DESC LIMIT 5;"
               batch_id               | count |              max
--------------------------------------+-------+-------------------------------
 f6292cf2-34aa-4776-956d-ad05780a3f1d |    68 | 2026-08-19 06:56:40.814706+00
```

Sensor events don't share this idempotency — every accepted record is a new row.
Confirmed pre/post-fix counts in Section 3.3.

---

## 3. Bug found and fixed: `sensor_staging_write` crashed on first contact with live data

### 3.1 Symptom

`sensor_staging_write` terminated on its very first micro-batch, before the fix below,
and did not recover — the consumer's exception handling (`spark_consumer.py`
lines 466–472) keeps *other* still-active queries running when one dies, but does not
restart the one that failed:

```
dataforge-spark  | 2026-09-20 08:16:49,015  ERROR  There was an exception while executing the Python Proxy on the Python Side.
dataforge-spark  | psycopg2.errors.InvalidTextRepresentation: invalid input syntax for type uuid: "GCS-01"
dataforge-spark  | 26/09/20 08:16:49 ERROR MicroBatchExecution: Query sensor_staging_write [...] terminated with error
```

### 3.2 Root cause

Traced through the actual files, not inferred:

- `"GCS-01"` is one of five `TELEMETRY_DEVICE_IDS` in `sensor_producer.py` (line 47).
  `generate_telemetry()` (line 159) calls `_base("TELEMETRY", device_id)`, and `_base()`
  (lines 88–92) binds that second argument to the `sensor_id` field.
- `init-db.sql` (line 28) types `raw_sensor_events_staging.sensor_id` as `UUID NOT NULL`.
  `"GCS-01"` isn't a valid UUID, so Postgres rejected the insert.
- This is not a stale-doc problem — it's a producer bug against the schema's own
  documented contract. `schemas/sensor_schema_v1.avsc`'s `sensor_id` field doc reads:
  *"Physical sensor device identifier (UUID v4) ... PostgreSQL storage type: uuid"*,
  while `device_id`'s doc reads *"e.g., UAV-07, SENSOR-UNIT-12"* — the schema clearly
  intends `sensor_id` as a machine UUID and `device_id` as the human-readable label.
  `data_dictionary_v1.md`, `staging_ingestion_contract.md`, and `data_flow_spec.md` all
  independently confirm `sensor_id` as UUID v4.
- Affects all three sensor types, not just TELEMETRY — `"radar-001"` and `"lidar-001"`
  (from `RADAR_SENSOR_IDS` / `LIDAR_SENSOR_IDS`) aren't UUIDs either. TELEMETRY's
  `"GCS-01"` was simply the first row the query happened to process.
- **Cross-reference:** `docs/database/sensor_streamed_record_erd_api_conformance.md`
  (M5W19T6, Beyza) marks `sensor_id | varchar | device ID string | ✅` as conformant.
  That check appears to have validated only `validate_and_serialize()` (Avro's `string`
  type has no format constraint, so any string round-trips), not the schema's documented
  UUID v4 intent. Flagged here for the team, not corrected unilaterally — not this
  task's file to edit.

### 3.3 Fix applied

`services/data-sources/sensor-generators/src/sensor_producer.py` — `sensor_id` is now a
stable UUID v4 per simulated sensor instance (one `uuid.uuid4()` generated per label at
process start, held for the container's lifetime), rather than the readable label
itself. `device_id` (TELEMETRY) is unchanged — it was already correct per the schema.
No `init-db.sql` or schema/ERD-doc changes were needed; both were already right.

Re-verified post-fix, rebuilt via `docker compose ... up -d --build sensor-generators spark-processor`:

```
$ docker compose logs spark-processor | grep -i "error\|exception\|terminated"
[no output]

$ docker exec dataforge-timescaledb psql -U dataforge -d dataforge -c "SELECT count(*) FROM raw_sensor_events_staging;"
 count
--------
 151203

$ docker exec dataforge-timescaledb psql -U dataforge -d dataforge -c "SELECT sensor_id, sensor_type FROM raw_sensor_events_staging ORDER BY load_id DESC LIMIT 5;"
              sensor_id               | sensor_type
--------------------------------------+-------------
 6a563817-fd5c-4c1c-9452-4522adc36efb | LIDAR
 6a563817-fd5c-4c1c-9452-4522adc36efb | LIDAR
 10afeb77-f9d5-4edd-bd54-9bdd8a3cb4fc | LIDAR
 2de9bf33-af4d-42b3-8511-24bc787dc044 | LIDAR
 10afeb77-f9d5-4edd-bd54-9bdd8a3cb4fc | LIDAR
```

151,203 vs. the pre-fix 150,000 baseline — 1,203 genuinely new rows, all valid UUIDs.
The repeated UUID (`6a563817-...`) across two of the five sampled rows confirms the
same physical sensor instance maps to the same `sensor_id` across records, as intended.

---

## 4. Risk flagged for T2 (not fixed here — out of this task's scope)

Both staging writers `.collect()` every micro-batch onto the Spark driver before a
single-connection `psycopg2.extras.execute_batch()` insert (`spark_consumer.py`,
`make_alice_batch_writer` / `make_sensor_batch_writer`). This doesn't parallelize
across the batch, and the `ProcessingTimeExecutor: Current batch is falling behind`
warnings observed in Section 2a (batches up to 17.6s against a 5s trigger) suggest this may
be a throughput ceiling independent of Kafka or Spark's own read capacity. T2's
benchmark methodology should account for this rather than treat a low result as
necessarily a Kafka/Spark limitation.

---

## 5. Formal M5 open item: no checkpointing

Per `spark_consumer.py`'s own design-note comment (Section 6 of the file's docstring): no
`checkpointLocation` is set for any of the four queries, so Spark uses an ephemeral
temp directory inside the container. A container restart currently loses all stream
offsets and staging-write progress rather than resuming. Fine for this milestone's
local verification; logged here formally, per task instruction, rather than left as an
inline comment only.

| Field | Detail |
|---|---|
| Item | No checkpointing on any of the four Spark Structured Streaming queries |
| Impact | Container restart loses Kafka offsets and staging-write state; at-least-once semantics rely on `ON CONFLICT DO NOTHING` idempotency for ALICE only — sensor events have no such protection and would be silently skipped (offset lost) or duplicated (offset replayed from an older checkpoint), depending on restart timing |
| Deferred to | Post-M5 hardening — not required for prototype-scale local verification |
| Trigger for resolution | Any move beyond local dev/verification use |

---

## 6. Conclusion

- **All four streams confirmed healthy end-to-end**, verified via live logs and direct
  SQL (not Adminer) — not verbal confirmation.
- **One blocking bug found and fixed**: `sensor_id` UUID mismatch in
  `sensor_producer.py`, root-caused against the schema's own documented field intent,
  not just legacy docs. Cross-references an inconsistency in Beyza's M5W19T6 note for
  the team's awareness.
- **Checkpointing gap formally logged** as an M5 open item per task instruction.
- **T2 dependency cleared**: the consumer is now verified trustworthy enough for the
  throughput benchmark to depend on, with one methodology risk (Section 4) flagged in advance.
