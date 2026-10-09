# fused_events + fusion_status DDL Verification

---

## DDL Applied

Added to `infrastructure/scripts/init-db.sql` and applied to the live volume via:

```
Get-Content init-db.sql | docker exec -i dataforge-timescaledb psql -U dataforge -d dataforge
```

FK note: `alice_event_id` and `sensor_event_id` are soft references — `uuid NOT NULL` with no `REFERENCES` clause. See `docs/database/fused_events_fk_decision.md`.

---

## Hypertable Verification

```sql
SELECT hypertable_name, num_chunks FROM timescaledb_information.hypertables;

 hypertable_name | num_chunks
-----------------+------------
 events          |          5
 fused_events    |          0
 fusion_status   |          0
```

---

## fused_events Column Verification

```
\d fused_events

      Column      |         Type          | Nullable | Default
------------------+-----------------------+----------+---------
 timestamp_ms     | bigint                | not null |
 fused_event_id   | uuid                  | not null |
 alice_event_id   | uuid                  | not null |
 sensor_event_id  | uuid                  | not null |
 sensor_type      | character varying(20) | not null |
 fusion_window_ms | integer               | not null | 500
 data_loss_pct    | real                  | not null | 0.0
 latency_ms       | bigint                | not null | 0
 schema_version   | character varying(10) | not null | '1.0'
 anomaly_label    | bigint                |          |
 risk_score       | real                  |          |
 confidence       | real                  |          |

Indexes:
    fused_events_pkey PRIMARY KEY (fused_event_id, timestamp_ms)
    fused_events_timestamp_ms_idx btree (timestamp_ms DESC)
    idx_fused_time_label btree (timestamp_ms, anomaly_label)
```

Chunk interval: 86,400,000 ms (1 day). Retention: 90 days (integer_now via `fused_events_now()`).

---

## fusion_status Column Verification

```
\d fusion_status

       Column        |           Type           | Nullable
---------------------+--------------------------+----------
 time                | timestamp with time zone | not null
 source_type         | character varying(20)    | not null
 quality_score       | integer                  | not null
 contribution_weight | real                     | not null
 data_loss           | real                     | not null
 latency             | real                     | not null
 status              | character varying(20)    | not null

Indexes:
    fusion_status_time_idx btree (time DESC)
```

Chunk interval: 1 hour. Retention: 7 days.

---

## Result

Both tables created as hypertables and verified in the live DB. Schema matches `fused_event_schema_v1.avsc` and `erd_final.md` exactly.

---

## Correction — M6W22T3 gate check (8 October 2026, Abdullah)

Two corrections found while confirming the Week 22 gate items against `develop`. Neither affects the
verified table shapes above, which were reproduced exactly.

**1. The DDL was never committed to `init-db.sql`.** The statement at the top of this note — "Added
to `infrastructure/scripts/init-db.sql`" — did not hold. Commit `71b6d2a` touched 18 files and
`init-db.sql` was not among them; the only `create_hypertable` call in that file was for `events`.
The tables existed solely in the live volume of the machine where the SQL was piped in by hand, so a
fresh `docker compose up` on any other machine produced a database with no fused layer. That would
have failed M6W22T2's first write and confounded M6W22T8's build verification. The DDL is now
committed, reproducing the verified `\d` output above column for column, type for type, default for
default.

**2. The replay de-duplication index was missing.** The design note Section 7 requires a unique index
on `(timestamp_ms, alice_event_id)`, listed as an open follow-up in its Section 13 checklist. It is
absent from the verified index output above. Without it, a checkpoint replay writes duplicate fused
rows, because the primary key's `fused_event_id` is a fresh UUID on every write. Added as
`uq_fused_events_replay`.

**Verified:** `init-db.sql` applied end to end against PostgreSQL 16 with the Timescale calls stubbed.
Resulting `\d fused_events` and `\d fusion_status` match the output above exactly. De-duplication
tested directly: five inserts, four rows — the replay duplicate collapsed, while a second producer
loop reusing the same `alice_event_id` under a new `timestamp_ms` survived, as did two ALICE events
sharing one sensor event (D2). Not covered by this test: hypertable chunking, the retention policies,
and `fused_events_timestamp_ms_idx`, which `create_hypertable` creates automatically — all three need
a real TimescaleDB instance.

**Action for Beyza:** the live volume already has both tables but not the unique index. Apply it
there without re-running the whole file:

```sql
CREATE UNIQUE INDEX IF NOT EXISTS uq_fused_events_replay
    ON fused_events (timestamp_ms, alice_event_id);
```

Safe to run on a populated table only while `fused_events` is empty, which it is (0 chunks). If any
fused rows have been written by the time this runs, the index build will fail on existing duplicates
rather than silently dropping them — that failure is the signal to check for them, not a reason to
drop the index.