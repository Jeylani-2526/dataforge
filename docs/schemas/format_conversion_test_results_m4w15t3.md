# DataForge — Format-Conversion Test Results (Avro → Parquet → Avro)

**Backfilled task:** M4W16T4
**Originating task:** M4W15T3 (test suite authored; results note never committed — this backfills that gap)
**Owner:** Abdullah
**Test file:** `services/adaptation-layer/test_round_trip_conversion.py`
**Run command:** `pytest services/adaptation-layer/test_round_trip_conversion.py`
**Last run result:** `3 passed in 38.84s`

---

## 1. What this test suite covers

`test_round_trip_conversion.py` drives a record through the adaptation layer's full storage path:

```
Avro (adaptation job output)
  -> Parquet (parquet_writer.py, M4W14T4 — existing, unmodified)
  -> Avro (parquet_to_avro.py, M4W15T3 — new)
```

For each stream, it checks two things:

1. **Data integrity** — the record that comes out matches what went in, with float fields compared at float32 precision (matching the Avro schema's declared `float` type, so this is the correct expected baseline rather than a workaround for lost precision).
2. **`schema_version` propagation** — the field survives the Parquet leg unchanged, confirmed against `CURRENT_SCHEMA_VERSIONS` in `schema_versioning.py`.

---

## 2. Results by stream

| Test | Streams covered | Result | What it confirms |
|---|---|---|---|
| `test_alice_event_round_trip` | ALICE | **PASS** | ALICE record round-trips through Parquet with no data loss; `schema_version` propagates correctly. |
| `test_sensor_streams_round_trip_combined_batch` | RADAR, LIDAR, TELEMETRY | **PASS** | All three sensor subtypes, written as a single combined Avro batch (matching how `avro_adaptation_job.py` actually produces the unified `sensor_event` stream in production), round-trip correctly through their respective split Parquet datasets. Each subtype's data integrity and `schema_version` propagation confirmed independently. |
| `test_sensor_single_type_batch_hits_known_spark_inference_gap` | Sensor (single-type batch) | **PASS** (as an intentional failure-mode test — see Section 3) | Documents a known Spark schema-inference fragility rather than a production bug. |

**All four streams (ALICE, RADAR, LIDAR, TELEMETRY) are confirmed passing** for data-integrity and `schema_version` propagation through the Avro → Parquet → Avro round trip.

---

## 3. Known, documented fragility (not a defect requiring an M4 fix)

The third test is deliberately written to *expect* a failure: `parquet_writer.records_to_dataframe()` calls `spark.createDataFrame(records)` without an explicit schema. If a batch contains only one sensor subtype, every column belonging to the other two subtypes is `null` in every row, and Spark's type inference cannot determine a type for an all-null column — it raises `PySparkValueError: CANNOT_DETERMINE_TYPE`.

**This does not occur in the real pipeline today**, because `avro_adaptation_job.py` always writes RADAR, LIDAR, and TELEMETRY into one shared `sensor_event` Avro output before the Parquet writer reads it back — so every column has at least one non-null value across the combined batch, as the second test above proves by passing. It would only surface with a future single-sensor-type batch (a partial partition, a backfill of one sensor type in isolation, or a unit test constructed that way).

**Disposition:** filed as an M4W15T3 finding, not fixed as part of this test suite or this week's work — an explicit-schema fix belongs to `parquet_writer.py` itself, which is out of scope for a test-suite task. Recorded here so it doesn't need rediscovering later; a fix (an explicit schema passed to `records_to_dataframe()`) is a reasonable candidate for whoever next touches `parquet_writer.py`'s DataFrame construction — notably, this is the same function `M4W16T3`'s throughput investigation also modified (see `throughput_root_cause_m4w16t3.md`), so any future work on that function should keep this fragility in mind.

---

## 4. Conclusion

All four streams pass their round-trip conversion tests as of this write-up. No data-integrity or schema-version-propagation issues found. One known, non-production-impacting Spark schema-inference edge case is documented and intentionally tested rather than silently left as a gap.
