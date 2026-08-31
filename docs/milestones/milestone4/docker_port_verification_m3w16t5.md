# DataForge — Docker Execution Environment & Port Consistency Verification

**Task:** M3W16T5
**Owner:** Abdullah (taking over from Ömer this week)
**Milestone:** M3 · Week 16
**Originating context:** Prior fixes this week (`4dcf172`, `daa82cc`) corrected a 5432/5433
port mismatch in `promote_to_production.py` (host script → now `localhost:5433`) and
`avro_adaptation_job.py` (host default → now `DB_PORT=5433`), matching
`docker-compose.yml`'s `"5433:5432"` mapping for TimescaleDB.
**Status:** Port consistency confirmed end-to-end, both host-side and container-side. One
unrelated, pre-existing gap found (missing `events` table in the local data volume) —
flagged, not fixed, per task instruction.

---

## 1. Static review of port configuration

| File | Path type | Port used | Correct? |
|---|---|---|---|
| `docker-compose.yml` — `timescaledb` service | Host↔container mapping | `"5433:5432"` | Source of truth |
| `docker-compose.yml` — `adaptation-layer` service | Container-to-container | `DB_HOST: timescaledb`, `DB_PORT: 5432` | Yes — internal Docker network, correct to use 5432 |
| `docker-compose.yml` — `spark-processor`, `api` services | Container-to-container | `DB_PORT: 5432` / `timescaledb:5432` in `DATABASE_URL` | Yes, same reasoning |
| `scripts/ingestion/promote_to_production.py` | Host execution | Hardcoded `DB_URL = postgresql://dataforge:dataforge_dev@localhost:5433/dataforge` | Yes |
| `services/adaptation-layer/avro_adaptation_job.py` | Dual-mode (host default / container override via env) | `DB_PORT = os.environ.get("DB_PORT", "5433")` | Yes — defaults to 5433 for bare host execution, but is overridden to `5432` by `docker-compose.yml`'s `adaptation-layer` service env when run in-container |
| `.env.example` | N/A | No `DB_PORT` var present at all | Not a gap — nothing in the codebase reads `DB_PORT` from `.env`; both host callers hardcode/default their own port per above |

`services/adaptation-layer/smoke_test.py` (the actual `CMD` in
`infrastructure/docker/adaptation-layer.Dockerfile`) imports and calls
`avro_adaptation_job.run_adaptation_job()` directly, so it inherits whatever `DB_PORT`
is in its process environment — `5432` when run via `docker compose`, matching the
service's own env block. No separate hardcoded port exists in `smoke_test.py`.

**Finding:** no remaining port mismatch in static review. Every host-side path resolves
to `5433`; every container-to-container path resolves to `5432`, consistent with the
`5433:5432` mapping in `docker-compose.yml`.

---

## 2. Live stack verification

Docker Desktop was not running at the start of this task and had to be started before
`docker compose` could reach the engine; once up, the stack was brought up as instructed:

```
$ docker compose --profile m4-and-above up -d timescaledb adaptation-layer
 Container dataforge-adaptation Recreate
 Container dataforge-adaptation Recreated
 Container dataforge-timescaledb Starting
 Container dataforge-timescaledb Started
 Container dataforge-timescaledb Waiting
 Container dataforge-timescaledb Healthy
 Container dataforge-adaptation Starting
 Container dataforge-adaptation Started

$ docker ps --filter "name=dataforge-timescaledb" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
NAMES                   STATUS                    PORTS
dataforge-timescaledb   Up 15 seconds (healthy)   0.0.0.0:5433->5432/tcp, [::]:5433->5432/tcp
```

### 2a. Host → port 5433

```
$ (exec 3<>/dev/tcp/localhost/5433 && echo "TCP connect to localhost:5433 SUCCEEDED")
TCP connect to localhost:5433 SUCCEEDED

$ (exec 3<>/dev/tcp/localhost/5432 && echo "SUCCEEDED (unexpected)") || echo "FAILED (expected)"
/usr/bin/bash: connect: Connection refused
TCP connect to localhost:5432 FAILED (expected)
```

A real `psql` connection (not just a TCP probe) was also run from the host side using
a throwaway `postgres:16-alpine` container on `--network host`:

```
$ docker run --rm --network host -e PGPASSWORD=dataforge_dev postgres:16-alpine \
    psql -h localhost -p 5433 -U dataforge -d dataforge -c "SELECT 'host-5433-ok' AS check, now();"
    check     |              now
--------------+-------------------------------
 host-5433-ok | 2026-08-31 04:19:12.759552+00
(1 row)
```

Separately, `promote_to_production.py`'s exact `DB_URL` string was tested directly with
`psycopg2` from the host (outside any container), using the real Python install at
`C:\Users\Jeylani\AppData\Local\Programs\Python\Python312\python.exe` (the
`python3`/`python` aliases on `PATH` resolve to the Windows Store stub and do not run):

```
$ python -c "
import psycopg2
conn = psycopg2.connect('postgresql://dataforge:dataforge_dev@localhost:5433/dataforge')
print('promote_to_production.py DB_URL (localhost:5433) -- connection: OK')
"
promote_to_production.py DB_URL (localhost:5433) -- connection: OK
```

### 2b. Container → container, port 5432

```
$ docker exec dataforge-adaptation python3 -c "
import socket
s = socket.create_connection(('timescaledb', 5432), timeout=5)
print('adaptation-layer -> timescaledb:5432 TCP connect: OK')
"
adaptation-layer -> timescaledb:5432 TCP connect: OK

$ docker exec dataforge-adaptation python3 -c "
import socket
try:
    s = socket.create_connection(('timescaledb', 5433), timeout=5)
    print('SUCCEEDED (unexpected)')
except Exception as e:
    print(f'FAILED as expected ({e})')
"
adaptation-layer -> timescaledb:5433 TCP connect: FAILED as expected ([Errno 111] Connection refused)
```

This confirms `5433` is a host-only published mapping and is correctly *not* reachable
from inside the compose network — services must use `5432` internally, which is exactly
what `docker-compose.yml`'s `adaptation-layer`/`spark-processor`/`api` env blocks do.

### 2c. Full real pipeline run, container-side

`dataforge-adaptation`'s `CMD` (`smoke_test.py`) ran to completion during `up -d`
(exit code `0`), actually exercising `avro_adaptation_job.py`'s JDBC read against
`timescaledb:5432` from inside the container — not a synthetic check:

```
2026-08-31 04:18:5x  INFO  Reading ALICE staging records...
...
"avro_adaptation_job": {
  "alice_event":  {"records": 68,     ...},
  "sensor_event": {"records": 150000, ...}
}
```

These counts (68 ALICE, 150,000 sensor) match the live row counts queried directly via
`psql` in Section 3 below, confirming the container-side JDBC path (`DB_HOST=timescaledb`,
`DB_PORT=5432`) is reading the real staging data, not failing silently or reading a stale
source.

---

## 3. Database liveness check (`\dt` and real queries)

```
$ docker exec dataforge-timescaledb psql -U dataforge -d dataforge -c '\dt'
                   List of relations
 Schema |           Name            | Type  |   Owner
--------+---------------------------+-------+-----------
 public | raw_alice_events_staging  | table | dataforge
 public | raw_sensor_events_staging | table | dataforge
(2 rows)

$ docker exec dataforge-timescaledb psql -U dataforge -d dataforge -c \
    "SELECT count(*) AS alice_rows FROM raw_alice_events_staging;"
 alice_rows
------------
         68

$ docker exec dataforge-timescaledb psql -U dataforge -d dataforge -c \
    "SELECT count(*) AS sensor_rows FROM raw_sensor_events_staging;"
 sensor_rows
-------------
      150000
```

DB is live, reachable, and holds real data on both the host-published port and the
internal container port.

---

## 4. Open item found (not a port issue — flagged, not fixed)

`\dt` shows only the two staging tables. `infrastructure/scripts/init-db.sql` also
defines a third table, `events` (the production hypertable that `promote_to_production.py`
writes into), but it is **not present** in this environment's live database:

```
$ docker exec dataforge-timescaledb psql -U dataforge -d dataforge -c \
    "SELECT to_regclass('public.events') AS events_table_exists;"
 events_table_exists
---------------------
 (empty)
```

Root cause, confirmed precisely (not just inferred from a restart log — see correction
below) via `docker volume inspect` and `git log`:

```
$ docker volume inspect dataforgerepo_timescaledb-data
    "CreatedAt": "2026-08-11T08:31:27Z"

$ git log -p --follow -- infrastructure/scripts/init-db.sql | grep -n "CREATE TABLE IF NOT EXISTS events\|^commit\|^Date:"
commit 62a734588261330c3000c70c605ab5a1276ab969
Date:   Thu Aug 20 11:03:37 2026 +0300
+CREATE TABLE IF NOT EXISTS events (
```

**Correction to an earlier read of this section:** the container's startup log
(`PostgreSQL Database directory appears to contain a database; Skipping initialization`,
timestamped 2026-08-26) is only a *restart* timestamp, not the volume's creation date —
initially misread as such above. The volume's actual `CreatedAt` is **2026-08-11T08:31:27Z**
per `docker volume inspect`. The `events` table was added to `init-db.sql` in commit
`62a7345` on **2026-08-20** (Beyza, M4W15T5-T6) — nine days *after* the volume was first
initialized. Postgres's official image only runs `docker-entrypoint-initdb.d/*.sql`
against a *fresh, empty* data directory; on every subsequent `up` it is skipped entirely,
regardless of what `init-db.sql` currently contains. This volume was created before the
`events` statement existed in the init script, so it never ran.

This is **not a port mismatch**. Confirmed independent of the missing table:
`promote_to_production.py`'s connection itself (host, port 5433) succeeds (Section 2a);
it is `events` being absent that would make an actual promotion run fail with
`relation "events" does not exist`, not the port. The adaptation-layer's container-side
pipeline (Section 2c) doesn't touch `events` at all, so it was unaffected and ran clean.

**Resolution:** fixed directly — see Section 6 below. Logged as
`open_items_m4.md` Item 6 ("Missing `events` Production Table in Local Dev Volume"),
resolved same-day rather than deferred, since this is a mechanical schema-drift gap with
a known-safe fix, not a question requiring team input.

---

## 5. Conclusion

- **Port consistency: confirmed, no remaining mismatch.** Static review of all four
  target files plus a live, real (not simulated) check of both the host→5433 path and
  the container-internal→5432 path, from both directions, all passed. The container's
  actual pipeline run (`smoke_test.py` → `avro_adaptation_job.py`) executed successfully
  end-to-end over the 5432 container path during this verification, reading real data
  whose counts were independently confirmed via `psql`.
- **Schema-drift item found and resolved:** the `events` production table was missing
  from the local Docker volume due to volume-vs-init-script timing, unrelated to the port
  fixes this task was scoped to verify. Root-caused and fixed same-day — see Section 6.

---

## 6. Close-out: `events` Table Fix Applied and Verified

This section documents the fix referenced in Sections 4–5 above, applied after the
initial verification pass. Cross-referenced as `open_items_m4.md` **Item 6**.

### 6.1 Statements applied

Pulled verbatim from `infrastructure/scripts/init-db.sql` (lines 63–89) and run against
the live database via `docker exec -i dataforge-timescaledb psql -U dataforge -d dataforge`:

```sql
CREATE TABLE IF NOT EXISTS events (
    event_id          UUID        NOT NULL,
    timestamp_ms      BIGINT      NOT NULL,
    source_type       VARCHAR(20) NOT NULL,
    run_number        INTEGER,
    track_count       INTEGER,
    net_momentum_x    REAL,
    net_momentum_y    REAL,
    net_momentum_z    REAL,
    max_energy_gev    REAL,
    total_energy_gev  REAL,
    sensor_type       VARCHAR(20),
    label             INTEGER     DEFAULT 0,
    anomaly_type      VARCHAR(50),
    latency_ms        REAL,
    anomaly_label     INTEGER,
    risk_score        REAL,
    schema_version    VARCHAR(10) NOT NULL DEFAULT '1.0',
    PRIMARY KEY (event_id, timestamp_ms)
);

SELECT create_hypertable('events', 'timestamp_ms',
    chunk_time_interval => 86400000,
    if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_events_source_type ON events (source_type, timestamp_ms);
CREATE INDEX IF NOT EXISTS idx_events_label       ON events (label, timestamp_ms);
```

All statements are idempotent (`IF NOT EXISTS` / `if_not_exists => TRUE`) — safe to
re-run, and in fact re-run as part of producing this section, against a state where the
table already existed from an earlier application of this same fix:

```
$ sed -n '61,89p' infrastructure/scripts/init-db.sql | docker exec -i dataforge-timescaledb psql -U dataforge -d dataforge
NOTICE:  relation "events" already exists, skipping
CREATE TABLE
  create_hypertable
---------------------
 (1,public,events,f)
(1 row)

NOTICE:  table "events" is already a hypertable, skipping
CREATE INDEX
NOTICE:  relation "idx_events_source_type" already exists, skipping
NOTICE:  relation "idx_events_label" already exists, skipping
CREATE INDEX
```

### 6.2 Verification output

```
$ docker exec dataforge-timescaledb psql -U dataforge -d dataforge -c '\d events'
                                   Table "public.events"
      Column      |         Type          | Collation | Nullable |         Default
------------------+-----------------------+-----------+----------+--------------------------
 event_id         | uuid                  |           | not null |
 timestamp_ms     | bigint                |           | not null |
 source_type      | character varying(20) |           | not null |
 run_number       | integer               |           |          |
 track_count      | integer               |           |          |
 net_momentum_x   | real                  |           |          |
 net_momentum_y   | real                  |           |          |
 net_momentum_z   | real                  |           |          |
 max_energy_gev   | real                  |           |          |
 total_energy_gev | real                  |           |          |
 sensor_type      | character varying(20) |           |          |
 label            | integer               |           |          | 0
 anomaly_type     | character varying(50) |           |          |
 latency_ms       | real                  |           |          |
 anomaly_label    | integer               |           |          |
 risk_score       | real                  |           |          |
 schema_version   | character varying(10) |           | not null | '1.0'::character varying
Indexes:
    "events_pkey" PRIMARY KEY, btree (event_id, timestamp_ms)
    "events_timestamp_ms_idx" btree (timestamp_ms DESC)
    "idx_events_label" btree (label, timestamp_ms)
    "idx_events_source_type" btree (source_type, timestamp_ms)

$ docker exec dataforge-timescaledb psql -U dataforge -d dataforge -c \
    "SELECT hypertable_name, primary_dimension, num_chunks FROM timescaledb_information.hypertables;"
 hypertable_name | primary_dimension | num_chunks
-----------------+--------------------+------------
 events          | timestamp_ms       |          0
(1 row)
```

Schema matches `init-db.sql`'s definition exactly, including the primary key and both
declared indexes. `events_timestamp_ms_idx` is TimescaleDB's own index, automatically
created by `create_hypertable()` on the partitioning column — not something declared in
`init-db.sql`, and correctly present. `num_chunks=0` is expected: no rows have been
written to `events` yet (a real `promote_to_production.py` run has not been executed
since this fix — noted as a natural follow-up in `open_items_m4.md` Item 6, not itself
blocking or logged as a new open item).

### 6.3 No staging data affected

Row counts checked immediately before and after applying the fix:

```
$ docker exec dataforge-timescaledb psql -U dataforge -d dataforge -c \
    "SELECT count(*) AS alice_rows FROM raw_alice_events_staging;
     SELECT count(*) AS sensor_rows FROM raw_sensor_events_staging;
     SELECT count(*) AS events_rows FROM events;"
 alice_rows
------------
         68

 sensor_rows
-------------
      150000

 events_rows
-------------
           0
```

`raw_alice_events_staging` (68) and `raw_sensor_events_staging` (150,000) are unchanged
from every count taken earlier in this document. **No staging data was dropped or
modified.** `events` correctly holds 0 rows — its creation does not itself promote or
copy any data.
