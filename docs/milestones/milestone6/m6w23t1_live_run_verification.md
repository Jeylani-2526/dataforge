# M6W23T1 — Live End-to-End Fused Run Verification



## Objective

First live end-to-end run of the Week 22 join through real Kafka sources. Week 22
committed the stream-stream join (`21be55f`) and the real `write_fused_events()`,
but neither had run outside a file-source spike (`spike_join_check.py`) and a
Postgres unit test (`test_fused_writer.py`). This is the Week 23 gate: a non-zero
`fused_events` count, verified through psql, opens T2, T4 and T6.

Two additional checks fold in, both named in the Week 23 plan:

1. The fused writer's `enforce()` import must resolve in-container after
   M6W22T8 moved `schema_versioning.py` from `/app/src/` to `/app/`.
2. The fusion checkpoint must recover after a kill-restart against real Kafka
   sources.

## Environment

| Component | Value |
|---|---|
| Services up | timescaledb, kafka, alice-ingestion, sensor-generators, spark-processor, fusion-engine |
| Fusion window | 500 ms (bucket 1000 ms) |
| Watermark delay | 5 s |
| Trigger interval | 5 s |
| Shuffle partitions | 8 |
| Kafka bootstrap | kafka:29092 |
| TimescaleDB | 5433 (host) → 5432 (container) |
| ALICE replay interval | 500 ms |
| Verification method | `docker exec` + psql — Adminer not used |

`fusion-checkpoints` was created fresh at startup, so the join began with no
prior checkpoint state.

## Result — Gate PASSED

Baseline was zero: the first non-empty micro-batch wrote 24 rows, and the count
taken immediately after returned exactly 24.

| Measurement | Value | Time |
|---|---|---|
| Rows before first write | 0 | 09:31 |
| First fused write (micro-batch 2) | 24 written, 0 rejected | 09:32:59 |
| `SELECT COUNT(*)` after first batch | 24 | 09:33 |
| Count before kill | 505 | 09:36:56 |
| Count after restart | 815 | 09:39:28 |
| Duplicate `(timestamp_ms, alice_event_id)` pairs | 0 | 09:39:28 |

Micro-batches 0 and 1 were empty, as expected — append-mode output cannot emit
until the watermark passes the first join window.

Sustained fused write rate across the run: **481 rows in 237 s ≈ 2.03 rows/s**.
The ALICE producer publishes at 500 ms intervals, so roughly 2 events/s enter the
join. Fused output therefore tracks ALICE input nearly one-to-one, which implies
a match rate close to 100 percent. T2 measures this properly; it is recorded here
only as an observation consistent with the count.

### Sample fused row

```
timestamp_ms     | 1792046123315
fused_event_id   | 70bccc73-5408-4f2b-ab12-989a949770cc
alice_event_id   | e57231ab-6c8c-4110-b400-6243a442477b
sensor_event_id  | ca93ecfb-3615-425d-8a69-fc293c551b2a
sensor_type      | LIDAR
fusion_window_ms | 500
data_loss_pct    | 0
latency_ms       | 14936
schema_version   | 1.0
anomaly_label    | (null)
risk_score       | (null)
confidence       | (null)
```

All nine locked v1 fields are present and populated. The three M7 columns are
null, as expected. Field-by-field conformance is Beyza's T6, not this task.

## Check 1 — enforce() import after the /app/ mount change: PASS

```
$ docker exec dataforge-fusion python -c "import schema_versioning, inspect; ..."
resolved -> /app/schema_versioning.py
enforce -> True
```

Confirmed a second way by the write path itself: every batch logs an enforcement
line before inserting, e.g.

```
[fused_event] enforcement: total=24 passed=24 version_drift=0 round_trip_failed=0 data_loss_pct=0.0000%
```

Since `enforce()` runs before any row reaches `fused_events`, a broken import
would have produced zero rows. 815 rows is independent evidence.

Enforcement outcome across the whole run: **0 version drift, 0 round-trip
failures, data_loss_pct 0.0000 percent on every batch.**

## Check 2 — checkpoint recovery after kill-restart: PASS

`docker kill` was used rather than `docker stop` — SIGKILL tests the checkpoint
itself, not the graceful shutdown path.

Evidence the checkpoint was recovered rather than reset:

- Micro-batch numbering **continued at 66** after the restart. A lost or reset
  checkpoint would have restarted batch IDs at 0.
- Counts moved forward monotonically, 505 → 815, with no gap in writing beyond
  the restart interval.
- `duplicate_pairs = 0`, so `uq_fused_events_replay` absorbed any replayed
  offsets, matching the M6W22T2 unit-test behaviour against a real stream.

Restart downtime was about 1 minute 51 seconds (09:36:56 kill → 09:38:47 first
post-restart batch), dominated by Spark startup and Kafka package resolution.

**Scope limit, stated plainly:** zero duplicates is proven. "No fused row
skipped" is *not* proven by row counts alone — it requires reconciling fused
output against published input counts, which is T2's reconciliation step. T1
establishes that the checkpoint resumed and that replay did not double-count.

## Findings raised by this run

### Finding 1 — fused-path latency is roughly 16 s, against a ≤500 ms bar

`latency_ms` on the sample row is 14,936 ms, and heartbeat lines across the run
report 15,931–17,905 ms consistently.

This is structural, not a defect in the write path. `latency_ms` is computed as
write time minus `timestamp_ms`, and the fused path necessarily includes:

- the 5 s watermark delay, since append-mode output cannot emit until the
  watermark passes the window,
- up to 5 s of trigger interval,
- 1.7–3.1 s of observed `collect` time per batch.

The locked ≤500 ms p95 bar and this figure are therefore not measuring the same
quantity. The bar describes pipeline processing latency; `latency_ms` on
`fused_events` describes event-time-to-write including a deliberate 5 s wait.

T2 measures fused-path p95 by the standard M5 SQL method and reports it as
measured. This note records the cause now so the figure is not read as a
regression. Carry to `open_items_m6.md` in Week 24.

### Finding 2 — heartbeat reports `status=critical` on a fully healthy run

Every heartbeat line in the run reads:

```
[heartbeat] alice — quality=0 status=critical data_loss=0.0000% latency=16981.9ms
```

This is on a run with 0 rejections, 0 version drift, 0 round-trip failures and
0.0000 percent data loss. `quality=0` and `status=critical` are both wrong
descriptions of that state. The cause is almost certainly a latency threshold
reacting to Finding 1.

This is distinct from, and compounds, the two heartbeat contract mismatches
already recorded in Beyza's T6:

| # | Issue | Source |
|---|---|---|
| 1 | status values written as `ok` / `degraded` / `critical`, contract specifies `online` / `degraded` / `offline` | T6 (vocabulary) |
| 2 | only `source_type` `alice` and `sensor` written, contract specifies latest row per sensor | T6 (granularity) |
| 3 | status and quality report `critical` / `0` on a healthy run | **this run (semantics)** |

Recorded as a finding, not corrected here. Goes to Beyza for T6 and T7, and to
Emrah in the Friday T5 update.

### Observation — startup batch lag, self-correcting

Early batches logged `Current batch is falling behind` (21,570 ms against a
5,000 ms trigger). This settled by batch 66, with collect times of 1.7–2.6 ms-scale
seconds and insert times of 6–10 ms. Startup cost, not a sustained condition. No
action.

## Gate decision

Non-zero fused rows confirmed through psql against a live Kafka run. **Week 23
proceeds as a measurement week.** T2, T4 and T6 are unblocked.
