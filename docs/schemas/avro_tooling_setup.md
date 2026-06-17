# Avro Validation Tool

## Overview

The Avro Validation Tool verifies that a JSON record can be successfully serialized and deserialized using a given Avro schema. The tool performs a round-trip validation and confirms data integrity.

## Requirements

Install the required dependency:

```bash
pip install fastavro
```

## Usage

Run the validation script with an Avro schema file and a JSON test record:

```bash
python schemas/validate_schema.py <schema.avsc> <record.json>
```

## Example

```bash
python schemas/validate_schema.py sample.avsc test_record.json
```

Example output:

## Example

Example test record:

```json
{
  "event_id": "EVT-139038-000042",
  "run_number": 139038,
  "timestamp_ms": 1710000000000,
  "track_count": 12,
  "net_momentum_x": 1.25,
  "net_momentum_y": -0.75,
  "net_momentum_z": 3.5,
  "max_energy_gev": 4.0,
  "total_energy_gev": 18.5,
  "schema_version": "0.1"
}
```

Run:

```bash
python schemas/validate_schema.py schemas/alice_event_schema_v0.avsc schemas/test_record.json
```

Example output:

```text
Original record:
{
  'event_id': 'EVT-139038-000042',
  'run_number': 139038,
  'timestamp_ms': 1710000000000,
  'track_count': 12,
  'net_momentum_x': 1.25,
  'net_momentum_y': -0.75,
  'net_momentum_z': 3.5,
  'max_energy_gev': 4.0,
  'total_energy_gev': 18.5,
  'schema_version': '0.1'
}

Decoded record:
{
  'event_id': 'EVT-139038-000042',
  'run_number': 139038,
  'timestamp_ms': 1710000000000,
  'track_count': 12,
  'net_momentum_x': 1.25,
  'net_momentum_y': -0.75,
  'net_momentum_z': 3.5,
  'max_energy_gev': 4.0,
  'total_energy_gev': 18.5,
  'schema_version': '0.1'
}

PASS: Round-trip validation successful

## Validation Process

The tool performs the following steps:

1. Loads the Avro schema (.avsc)
2. Loads the JSON test record
3. Parses the schema using fastavro
4. Serializes the record into Avro binary format
5. Deserializes the binary data back into a record
6. Compares the original and decoded records
7. Reports PASS or FAIL based on the comparison

## Error Handling

The script validates:

- Missing command-line arguments
- Invalid schema files
- Invalid JSON files
- Serialization errors
- Deserialization errors

Any error is reported with a descriptive message:

```text
ERROR: <error details>
```

## Exit Codes

| Code | Meaning |
|--------|---------|
| 0 | Validation successful |
| 1 | Validation failed or an error occurred |