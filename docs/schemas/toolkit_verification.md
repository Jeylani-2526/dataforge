# TimescaleDB Toolkit Verification

## Purpose

This document records the installation and verification of the `timescaledb_toolkit` extension for the DataForge TimescaleDB Docker service.

The toolkit is required for Week 7 CAGG validation because several percentile aggregation and rollup functions are only available through TimescaleDB Toolkit.

---

## Docker Image

The TimescaleDB service was updated to use the HA image that includes Toolkit support.

```yaml
timescaledb:
  image: timescale/timescaledb-ha:pg16
```

---

## Service Startup

The TimescaleDB container was started using Docker Compose.

```bash
docker compose up -d timescaledb
```

---

## Database Access

The database container was accessed using:

```bash
docker exec -it dataforge-timescaledb psql -U dataforge -d dataforge
```

---

## Extension Installation

The required extensions were enabled inside the DataForge database.

```sql
CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE EXTENSION IF NOT EXISTS timescaledb_toolkit;
```

---

## Verification Query

The installed extension versions were verified with:

```sql
SELECT extname, extversion
FROM pg_extension
WHERE extname IN ('timescaledb', 'timescaledb_toolkit');
```

---

## Verification Output

```text
extname             | extversion
--------------------+-----------
timescaledb_toolkit | 1.23.0
timescaledb         | 2.27.2
```

---

## Result

Verification completed successfully.

The output confirms that:

- TimescaleDB is installed and available.
- TimescaleDB Toolkit is installed and available.
- Toolkit functions can now be used by future DataForge modules.
- The environment is ready for Week 7 CAGG validation tasks.

---

## Verification Date

18 June 2026