# DataForge — Infrastructure Requirements

## TimescaleDB

### Database Image

```
image: timescale/timescaledb-ha:pg16
```

### Installed Extensions

| Extension            | Version |
| -------------------- | ------- |
| `timescaledb`        | 2.27.2  |
| `timescaledb_toolkit`| 1.23.0  |

### Verification

The TimescaleDB and timescaledb_toolkit extensions were installed and verified
inside the DataForge Docker environment.

```sql
SELECT extname, extversion
FROM pg_extension
WHERE extname IN ('timescaledb', 'timescaledb_toolkit');
```

```
       extname        | extversion
----------------------+------------
 timescaledb          | 2.27.2
 timescaledb_toolkit  | 1.23.0
(2 rows)
```

> TimescaleDB ≥ 2.9 is required for cascading continuous aggregates.
> Version 2.27.2 satisfies this requirement.

---

## Avro Dependencies

All three entries below are the binding contract for M4 pipeline development.
Any version upgrade after M2 requires a change note in this document.

### fastavro

| Property     | Value                  |
| ------------ | ---------------------- |
| Package      | `fastavro`             |
| Pinned version | `1.9.4`              |
| Pin date     | 25 June 2026           |
| Usage        | Schema parsing, round-trip serialization/deserialization in `validate_schema.py` and the M4 Data Adaptation pipeline |

```
fastavro==1.9.4
```

**Rationale:** fastavro is the primary Avro library for the DataForge prototype.
It provides `parse_schema`, `schemaless_writer`, and `schemaless_reader` — all
used in `validate_schema.py`. It is actively maintained and sufficient for
prototype-scale throughput without requiring the heavier `apache-avro` stack.

---

### Kafka Avro Serializer

| Property       | Value                        |
| -------------- | ---------------------------- |
| Package        | `confluent-kafka[avro]`      |
| Pinned version | `2.4.0`                      |
| Pin date       | 25 June 2026                 |
| Usage          | Avro serialization/deserialization in the M4–M5 Kafka producer and consumer pipeline |

```
confluent-kafka[avro]==2.4.0
```

**Rationale:** `confluent-kafka[avro]` is the standard Kafka client for
Python with built-in Avro support via the Confluent Schema Registry serializer.
It integrates with the Docker Compose Kafka broker used across M4–M5 and
is compatible with the fastavro-validated schemas from M2.

---

### avro-python3

| Property | Value |
| -------- | ----- |
| Package  | `avro-python3` |
| Decision | **Not required — omitted from requirements.txt** |
| Pin date | 25 June 2026 |

**Rationale:** `avro-python3` is the Apache Software Foundation's official
Python Avro library. It is not needed because `fastavro` covers all schema
parsing and serialization requirements for the DataForge prototype, and
`confluent-kafka[avro]` handles Kafka-specific Avro serialization in M4–M5.
Including both `fastavro` and `avro-python3` would introduce redundant
dependencies with overlapping functionality. Decision: omit `avro-python3`
for the full duration of the prototype.

---

## requirements.txt entries (Avro section)

```
fastavro==1.9.4
confluent-kafka[avro]==2.4.0
```

`avro-python3` is explicitly excluded. No other Avro-related packages are required.
