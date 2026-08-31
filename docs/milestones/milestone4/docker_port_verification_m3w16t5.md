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

Root cause, confirmed from the container's own startup log:

```
PostgreSQL Database directory appears to contain a database; Skipping initialization
...
2026-08-26 06:30:44.978 UTC [1] LOG:  starting PostgreSQL 16.14 ...
```

The named volume `dataforgerepo_timescaledb-data` already contained an initialized
Postgres data directory from **2026-08-26**. Postgres's official image only runs
`docker-entrypoint-initdb.d/*.sql` (i.e. `init-db.sql`) against a *fresh, empty* data
directory — on every subsequent `up`, it is skipped entirely, regardless of what
`init-db.sql` currently contains. If the `events` `CREATE TABLE` was added to
`init-db.sql` after this volume's first initialization on 2026-08-26, that statement has
never executed against this local volume.

This is **not a port mismatch** and is outside this task's scope to fix — flagging per
the task's instruction not to silently smooth over anything found. Confirmed independent
of the missing table: `promote_to_production.py`'s connection itself (host, port 5433)
succeeds (Section 2a); it is `events` being absent that would make an actual promotion
run fail with `relation "events" does not exist`, not the port. The adaptation-layer's
container-side pipeline (Section 2c) doesn't touch `events` at all, so it was unaffected
and ran clean.

**Recommendation (not actioned here):** whoever next needs the `events` table locally
should either `docker compose down -v` to drop and reinitialize the volume (destructive —
would also drop the 68 + 150,000 staging rows currently loaded), or run `init-db.sql`'s
`events`-table statements manually against the existing volume. Left for the task owner
to decide; no data was deleted or modified as part of this verification.

---

## 5. Conclusion

- **Port consistency: confirmed, no remaining mismatch.** Static review of all four
  target files plus a live, real (not simulated) check of both the host→5433 path and
  the container-internal→5432 path, from both directions, all passed. The container's
  actual pipeline run (`smoke_test.py` → `avro_adaptation_job.py`) executed successfully
  end-to-end over the 5432 container path during this verification, reading real data
  whose counts were independently confirmed via `psql`.
- **Open item:** the `events` production table is missing from the current local Docker
  volume due to volume staleness relative to `init-db.sql`, unrelated to the port fixes
  this task was scoped to verify. Reported per instruction; not fixed.
