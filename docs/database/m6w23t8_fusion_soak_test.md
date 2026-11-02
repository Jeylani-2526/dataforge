# Fusion Engine Soak Test

**Week:** M6W23  **Task:** T8  **Owner:** Beyza

## Environment

| Component | Value |
|-----------|-------|
| Fusion engine | dataforge-fusion (Spark 3.5, PySpark) |
| Kafka bootstrap | kafka:29092 |
| Window | 500 ms |
| Watermark | 5 s |
| Trigger | 5 s |
| TimescaleDB | dataforge-timescaledb:5432 |
| Host memory limit | 5.734 GiB |

## Observations

| t (min) | fused_events count | Fusion MEM usage | MEM % |
|---------|--------------------|-----------------|-------|
| 0 | 96 | — | — |
| +15 | 5 423 | 1 000 MiB | 17.04 % |
| +30 | 7 191 | 951 MiB | 16.20 % |

## Findings

- **Throughput:** ~355 row/min in first 15 min window; rate normalised in second window due to alice-ingestion loop interval (~72 s/loop, 136 events/loop).
- **Memory:** Stable — usage dropped from 1 000 MiB to 951 MiB between t+15 and t+30, confirming JVM/Python GC is reclaiming memory. No leak detected.
- **Crash / restart count:** 0 during observation window.

## Bugs fixed during setup

| Issue | Fix |
|-------|-----|
| `ON CONFLICT (timestamp_ms, alice_event_id)` had no matching constraint | Added `UNIQUE INDEX uq_fused_time_alice` on `fused_events` |
| `heartbeat_writer` missing from Docker image | Added to `COPY` line in `fusion.Dockerfile` |
| Host port 9092 conflict with subop-kafka | Remapped DataForge Kafka host port to 9093 (local only, skip-worktree) |

## Verdict

PASS — fusion engine runs continuously without memory growth or crashes. Row ingestion rate consistent with producer output.
