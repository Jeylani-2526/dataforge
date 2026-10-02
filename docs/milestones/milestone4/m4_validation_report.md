# DataForge — M4 Validation Report

**Task:** M4W16T7
**Owner:** Abdullah
**Milestone:** M4 (Data Adaptation Layer) — final validation ahead of M4 package assembly (T8)

---

## 1. Purpose

This report validates three things ahead of closing Milestone 4:

1. **Format-conversion correctness** — does the Avro → Parquet → Avro round trip preserve data and schema versioning across all four streams?
2. **Pipeline throughput** — does the full-volume pipeline meet the locked prototype bar, and if not, why?
3. **Schema-versioning enforcement** — is `schema_evolution_policy.md`'s versioning contract actually enforced by running pipeline code, or only described in documentation?

Each section draws on the committed source documents produced this week (T3, T4) rather than restating figures that only exist in console output.

---

## 2. Conversion-test results

**Source:** `docs/schemas/format_conversion_test_results_m4w15t3.md` (backfilled M4W16T4)

All four streams — ALICE, RADAR, LIDAR, TELEMETRY — pass their Avro → Parquet → Avro round-trip tests (`pytest services/adaptation-layer/test_round_trip_conversion.py`, 3 passed). Each passing test confirms two things per stream: no data loss through the round trip (floats compared at float32 precision, matching the schema's declared type), and correct `schema_version` propagation through the Parquet leg.

One known, non-production-impacting fragility is documented rather than silently left as a gap: a single-sensor-type batch triggers a Spark schema-inference limitation (`CANNOT_DETERMINE_TYPE`) in `parquet_writer.records_to_dataframe()`, because all-null columns for the other two subtypes can't have their type inferred. This does not occur in production, since `avro_adaptation_job.py` always writes all three sensor subtypes into one combined batch before the Parquet writer runs. Recorded as a candidate fix for whoever next touches that function.

**Status: PASS**, with one documented, non-blocking edge case.

---

## 3. Pipeline throughput

**Source:** `docs/milestones/milestone4/throughput_root_cause_m4w16t3.md` and `docs/data/full_volume_run_m4w15t4.md` (both from this week's investigation)

| Metric | Bar | Result | Status |
|---|---|---|---|
| Throughput | ≥ 10,000 events/sec | **1,135.05 events/sec** | **FAIL** |
| Latency (p95) | ≤ 500 ms | 0.1334 ms | PASS |
| Data loss | ≤ 1% | 0.0% | PASS |

Data integrity remains fully sound — throughput is the only metric outside the locked prototype bar.

**This week's investigation (M4W16T3) found:**

- The original M4W15T4 open item's "single large task" framing was partially incorrect: the sensor DataFrame actually uses 8 partitions (matching local default parallelism), not 1. The Spark task-size warning fires across all 8, independent of partition count.
- The real bottleneck is architectural: `parquet_writer.py`'s `records_to_dataframe()` builds the sensor DataFrame via `spark.createDataFrame()` on a Python list fully materialized in driver memory by `fastavro` — an inherently serial, expensive step regardless of partitioning, and one that proved fragile enough to crash a lightweight diagnostic script twice during this investigation.
- A caching fix was implemented and measured, in a controlled same-environment comparison, to be **~44–45% faster than without it** (1,135–1,142.5 vs. 788.11 events/sec). This is a real, kept improvement — but it does not close the gap to the ≥10,000 bar, nor does it recover the original 1,665.56 events/sec baseline measured before this week's fixes.
- Two previously-unflagged bugs were found and fixed while verifying this: a second instance of the 5432/5433 TimescaleDB port mismatch (in `avro_adaptation_job.py`, distinct from the instance flagged to Beyza in `promote_to_production.py`), and a missing `sc.addPyFile()` call for the module's own code, without which the pipeline could only run from one specific working directory.

**Status: FAIL, root-caused, partially mitigated, gap not closed.** Consistent with the original open item's own framing, M5's Kafka + Structured Streaming benchmark is the roadmap's actual throughput deliverable and will supersede this M4 batch-mode figure. This M4 number is carried forward as a baseline for that comparison, not a final verdict on whether the prototype bar is reachable.

---

## 4. Schema-versioning enforcement: pipeline code, not documentation only

`schema_evolution_policy.md` defines the versioning contract (MAJOR.MINOR numbering, backward-compatibility rules, the `schema_version` field as the authoritative per-record version marker). This section confirms that contract is enforced by running code, not just described.

**Evidence:**

- `avro_adaptation_job.py` imports and calls `schema_versioning.enforce()` directly inside `_write_partition_to_avro()` (the actual per-partition writer function executed by every pipeline run) — not in a separate validation script run out-of-band.
- `enforce()` performs a genuine serialize → deserialize → compare round-trip check per record (`schema_versioning.round_trip_check()`), and records failing either the version stamp or the round-trip comparison are excluded and counted in `data_loss_pct`, not silently dropped.
- This week's own full-volume run produced live enforcement output as part of normal pipeline execution, not a separate test:
  ```
  [alice_event] enforcement: total=68  passed=68  version_drift=0  round_trip_failed=0  data_loss_pct=0.0000%
  [sensor_event] enforcement: total=150000  passed=150000  version_drift=0  round_trip_failed=0  data_loss_pct=0.0000%
  ```
  This is runtime output from `full_volume_run.py`'s actual execution this week (see `docs/data/full_volume_run_m4w15t4.md`), confirming enforcement executes on every record in a real pipeline run, not only in an isolated unit test.
- The pipeline explicitly ships `schema_versioning.py` to Spark worker processes via `sc.addPyFile()` specifically so `enforce()` can run inside distributed worker code, not just on the driver — reinforcing that this is production pipeline behavior, not a documentation-only claim.

**Status: PASS.** Schema-versioning enforcement is implemented as executable pipeline code and demonstrated running against the full committed data volume this week, with zero version drift and zero round-trip failures across both streams.

---

## 5. Summary

| Area | Status |
|---|---|
| Format-conversion correctness (all 4 streams) | PASS (1 documented non-blocking edge case) |
| Pipeline throughput vs. prototype bar | FAIL — root-caused, partially mitigated, gap open |
| Data loss | PASS (0.0%) |
| Latency (p95) | PASS (0.1334 ms) |
| Schema-versioning enforcement (runs as pipeline code) | PASS |

M4's data-adaptation layer is validated as correct and schema-compliant. The one open item — throughput — is carried forward to the M4 package (T8) exactly as measured this week, with root cause and mitigation documented, consistent with the project's practice of reporting gaps plainly rather than smoothing them over.
