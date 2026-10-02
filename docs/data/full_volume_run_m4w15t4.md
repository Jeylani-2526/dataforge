# DataForge — Full-Volume Pipeline Run Report

**Task:** M4W15T4
**Owner:** Abdullah
**Run timestamp (UTC):** 2026-08-26T07:25:25.708715+00:00
**Wall-clock duration:** 132.213 s

---

## Volume check (against M4W15T1's trimmed spec)

| Stream | Expected | Actual | Match |
|---|---|---|---|
| ALICE | 68 | 68 | PASS |
| Sensor (RADAR+LIDAR+TELEMETRY) | 150000 | 150000 | PASS |

---

## Results vs. locked prototype bar

| Metric | Bar | Result | Status |
|---|---|---|---|
| Throughput | >= 10,000 events/sec | 1,135.05 events/sec | FAIL |
| Latency (p95) | <= 500 ms | 0.1334 ms | PASS |
| Data loss | <= 1.0% | 0.0% | PASS |

**Overall: ONE OR MORE BARS NOT MET — see Week 16 open item**

---

## Latency methodology (read before citing these numbers elsewhere)

There is no live event stream in M4 — Kafka + Structured Streaming is M5's deliverable. "Latency" here is the per-record processing time inside the adaptation layer's actual unit of work: `schema_versioning.py`'s serialize -> deserialize -> compare round-trip check (M4W14T3), timed individually per record. This is an honest proxy for this milestone's batch pipeline, not the streaming-latency metric M5 will measure end-to-end.

- p50: 0.0683 ms
- p95: 0.1334 ms
- p99: 0.1935 ms
- Sample size: 150,068 per-record timings (all passed + failed round-trip attempts across both streams)

---

## Per-stream breakdown

| Stream | Staging count | Passed | Rejected (version drift) | Rejected (round-trip) | Parquet written |
|---|---|---|---|---|---|
| ALICE | 68 | 68 | 0 | 0 | 68 |
| Sensor | 150000 | 150000 | 0 | 0 | {'radar': 50000, 'lidar': 50000, 'telemetry': 50000} |

---

## Raw data

Full machine-readable summary: `data\adaptation\full_volume_run_summary.json`
