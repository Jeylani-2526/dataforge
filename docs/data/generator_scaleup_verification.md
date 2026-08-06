# M3W12T7 Generator Scale-Up Verification

**Task:** M3W12T7 – Generator Scale-Up Verification (M5 Target Volumes)

**Validation Date:** 05 August 2026

---

# Objective

This verification confirms that all three synthetic data generators operate correctly in continuous mode at the required M5 throughput target.

The verification included:

- Continuous-mode execution
- Throughput measurement
- Anomaly taxonomy verification
- Timestamp stall verification

---

# Continuous Mode Throughput

Each generator was executed in continuous mode for 10 seconds using zero emission delay.

Target throughput:

- **≥ 10,000 events/second**

| Generator | Events Generated | Duration | Throughput (events/s) | Result |
|------------|----------------:|---------:|----------------------:|:------:|
| RADAR | 125,000 | 10 s | 12,500.0 | PASS |
| LIDAR | 116,834 | 10 s | 11,683.4 | PASS |
| TELEMETRY | 106,561 | 10 s | 10,656.1 | PASS |

All generators exceeded the required M5 throughput target.

---

# Continuous Mode Anomaly Taxonomy Verification

A continuous sample of 100,000 generated records was collected for each generator and inspected to verify that the anomaly taxonomy remained unchanged under continuous operation.

## RADAR

| Anomaly Type | Records |
|---------------|-------:|
| ghost_target | 979 |
| velocity_spike | 972 |
| sensor_dropout | 1,016 |

Normal records:

- 97,033

---

## LIDAR

| Anomaly Type | Records |
|---------------|-------:|
| ghost_point | 1,019 |
| point_cloud_dropout | 999 |
| noise_burst | 1,015 |

Normal records:

- 96,967

---

## TELEMETRY

| Anomaly Type | Records |
|---------------|-------:|
| out_of_range_value | 954 |
| timestamp_stall | 1,014 |
| missing_reading | 940 |

Normal records:

- 97,092

The observed anomaly rate remained approximately 3%, matching the configured anomaly injection probability.

---

# Timestamp Stall Verification

The corrected `timestamp_stall` anomaly was verified during continuous operation.

Sample validation:

| Property | Value |
|----------|-------|
| Previous timestamp | 1785935723703 |
| Current timestamp | 1785935723703 |
| Timestamp delta | **0 ms** |
| Label | 1 |
| Anomaly type | timestamp_stall |

The anomaly preserved the expected behaviour by emitting consecutive records with an identical timestamp while remaining correctly labelled.

---

# Summary

| Verification | Result |
|-------------|:------:|
| RADAR continuous mode | PASS |
| LIDAR continuous mode | PASS |
| TELEMETRY continuous mode | PASS |
| Throughput target (≥10,000 events/s) | PASS |
| Anomaly taxonomy preserved | PASS |
| timestamp_stall verification | PASS |

---

# Conclusion

All three generators successfully completed continuous-mode verification at the required M5 throughput target.

The corrected anomaly taxonomy remained intact under sustained generation, including successful verification of the `timestamp_stall` anomaly. All generators exceeded the required throughput of **10,000 events per second**, confirming readiness for M5 target-volume operation.