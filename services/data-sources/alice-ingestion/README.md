# Module 1 — ALICE Kafka Producer

**Owner:** Abdullah  
**Milestone:** M5 (Week 17 — implementation)  
**Status:** ✅ Implemented (M5W17T1)

## Purpose

Publishes the 68 filtered, PyROOT-corrected ALICE Run 1 records to the
`alice-events` Kafka topic on a paced continuous loop, so downstream
Spark Structured Streaming (Week 18) has an ongoing stream to consume
rather than a single burst.

**Scope note:** this replays the *promoted, production* `events` table
data (`WHERE source_type = 'alice'`) — the same canonical output M4's
adaptation + promotion pipeline already produced. It is a republish of
trusted batch data over Kafka, not a fresh real-time ingestion source.
This is a deliberate M5 scope decision, logged here explicitly so it
isn't later implied as live ingestion. Field-level PyROOT correction
(momentum/energy derivation) happens once, upstream, in
`scripts/ingestion/staging_ingestion_script.py` — this service does not
duplicate that logic.

## Data Fields (per `schemas/alice_event_schema_v1.avsc`)

| Field | Type | Description |
|-------|------|-------------|
| event_id | string (UUID) | Unique event identifier |
| run_number | int | ALICE LHC run number |
| timestamp_ms | long | Event timestamp (ms since epoch) |
| track_count | int | Reconstructed charged tracks in the event |
| net_momentum_x/y/z | float | Net momentum components (GeV/c) |
| max_energy_gev | float | Highest track energy in the event (GeV) |
| total_energy_gev | float | Total energy summed across tracks (GeV) |
| schema_version | string | Stamped from the registry, not trusted verbatim (see `alice_producer.py`) |

## Kafka Output Topic

`alice-events`

## Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Run locally (reads schemas/ relative to repo root by default via
# ALICE_SCHEMA_PATH, or set DB_* / KAFKA_* env vars to match your setup)
python src/alice_producer.py
```

## Configuration (env vars)

| Var | Default | Notes |
|-----|---------|-------|
| `KAFKA_BOOTSTRAP_SERVERS` | `localhost:9092` | `kafka:29092` inside Docker |
| `KAFKA_TOPIC_ALICE` | `alice-events` | |
| `DB_HOST` | `localhost` | `timescaledb` inside Docker |
| `DB_PORT` | `5433` | Host-published port; `5432` inside Docker (container-internal) |
| `DB_NAME` / `DB_USER` / `DB_PASSWORD` | `dataforge` / `dataforge` / `dataforge_dev` | |
| `ALICE_REPLAY_INTERVAL_MS` | `500` | Pacing between records, not a throughput setting — see design notes in `alice_producer.py` |
| `ALICE_SCHEMA_PATH` | `/app/schemas/alice_event_schema_v1.avsc` | |

## Notes

- Docker Compose profile: `m5-and-above` (was `m3-and-above` when this
  service was still scoped as a file-based ingestion stub; updated to
  reflect the actual M5 implementation and its `timescaledb` dependency).
- Every record is round-trip checked (serialize → deserialize → compare)
  against the locked schema before publishing; failures are logged and
  counted, never silently dropped.
