# M3W11T8 Data Quality Check Results

**Task:** M3W11T8 – Data Quality Validation Suite

**Validation Date:** 05 August 2026

---

# Validation Scope

The following validation checks were performed:

- Avro schema validation
- Round-trip serialization/deserialization validation
- Completeness check
- Required-field null check
- Range validation

The validation covered:

- Sensor test records
- RADAR synthetic dataset
- LIDAR synthetic dataset
- TELEMETRY synthetic dataset
- ALICE sample extracted from `AliESDs.root`

---

# Schema Validation

## Sensor Test Records

| Metric | Result |
|--------|--------|
| Records validated | 3 |
| Passed | 3 |
| Failed | 0 |

All sensor test records successfully completed Avro round-trip validation. :contentReference[oaicite:0]{index=0}

---

# Synthetic Dataset Validation

| Dataset | Records | Schema | Completeness | Required Null Check |
|---------|--------:|:------:|:------------:|:-------------------:|
| RADAR | 50,000 | PASS | PASS | PASS |
| LIDAR | 50,000 | PASS | PASS | PASS |
| TELEMETRY | 50,000 | PASS | PASS | PASS |

### Range Validation

| Dataset | Result |
|---------|-------:|
| RADAR | 513 intentionally injected anomaly records detected |
| LIDAR | 0 range violations |
| TELEMETRY | 153 intentionally injected anomaly records detected |

The detected range violations correspond to records generated with `label = 1` as part of the synthetic anomaly generation process and therefore represent expected behaviour of the datasets rather than unintended data-quality defects. :contentReference[oaicite:1]{index=1} :contentReference[oaicite:2]{index=2}

---

# ALICE Dataset Validation

The ALICE Run-1 sample was extracted from `AliESDs.root` and validated using the locked `alice_event_schema_v1.avsc` schema.

| Metric | Result |
|--------|--------|
| Records extracted | 287 |
| JSON parsing | PASS |
| Schema validation | PASS |
| Completeness | PASS |
| Required null check | PASS |
| Range validation | PASS |

The current implementation stores placeholder values (`0.0`) for momentum and energy fields until the planned PyROOT implementation is integrated. This behaviour is expected for the current project milestone. :contentReference[oaicite:3]{index=3} :contentReference[oaicite:4]{index=4}

---

# Summary

| Dataset | Records | Overall Result |
|---------|--------:|:--------------:|
| Sensor test records | 3 | PASS |
| RADAR synthetic | 50,000 | PASS |
| LIDAR synthetic | 50,000 | PASS |
| TELEMETRY synthetic | 50,000 | PASS |
| ALICE sample | 287 | PASS |

---

# Conclusion

The M3W11T8 data-quality validation suite was completed successfully.

The validation confirmed:

- Successful Avro schema validation
- Successful round-trip validation
- Complete required-field coverage
- No unexpected required-field null values
- Correct detection of intentionally injected anomaly records during range validation

The ALICE sample extraction and validation also completed successfully.