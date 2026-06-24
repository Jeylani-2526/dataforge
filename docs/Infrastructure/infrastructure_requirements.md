Infrastructure Requirements
TimescaleDB
Database Image
image: timescale/timescaledb-ha:pg16
Installed Extensions
Extension	Version
timescaledb	2.27.2
timescaledb_toolkit	1.23.0
Verification

The TimescaleDB Toolkit extension was installed and verified successfully inside the DataForge Docker environment.

Verification query:

SELECT extname, extversion
FROM pg_extension
WHERE extname IN ('timescaledb', 'timescaledb_toolkit');

Verification result:

timescaledb_toolkit | 1.23.0
timescaledb         | 2.27.2