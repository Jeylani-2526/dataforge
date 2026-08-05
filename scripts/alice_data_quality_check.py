import json
import sys
from io import BytesIO
from pathlib import Path

from fastavro import parse_schema, schemaless_reader, schemaless_writer
from fastavro.validation import validate


# Fields required for every ALICE event record
REQUIRED_FIELDS = [
    "event_id",
    "run_number",
    "timestamp_ms",
    "track_count",
    "net_momentum_x",
    "net_momentum_y",
    "net_momentum_z",
    "max_energy_gev",
    "total_energy_gev",
    "schema_version",
]


def load_schema(schema_path):
    """
    Load and parse the ALICE Avro schema.
    """

    with open(schema_path, "r", encoding="utf-8") as schema_file:
        schema = json.load(schema_file)

    return schema, parse_schema(schema)


def read_jsonl(file_path):
    """
    Read an NDJSON/JSON Lines file one record at a time.

    Empty lines are ignored. Invalid JSON lines are reported
    without stopping validation of the remaining records.
    """

    with open(file_path, "r", encoding="utf-8") as input_file:
        for line_number, line in enumerate(input_file, start=1):
            line = line.strip()

            if not line:
                continue

            try:
                yield line_number, json.loads(line), None
            except json.JSONDecodeError as error:
                yield line_number, None, str(error)


def validate_schema_record(record, parsed_schema):
    """
    Validate one ALICE record against the Avro schema and verify
    that it can complete a binary serialization round trip.
    """

    validate(record, parsed_schema, raise_errors=True)

    buffer = BytesIO()

    schemaless_writer(buffer, parsed_schema, record)
    buffer.seek(0)

    schemaless_reader(buffer, parsed_schema)

    return True


def check_completeness(record):
    """
    Check whether every required ALICE field is present.
    """

    return [
        field
        for field in REQUIRED_FIELDS
        if field not in record
    ]


def check_required_nulls(record):
    """
    Check whether any required ALICE field contains a null value.
    """

    return [
        field
        for field in REQUIRED_FIELDS
        if record.get(field) is None
    ]


def check_ranges(record):
    """
    Check basic numeric and categorical constraints for ALICE data.
    """

    violations = []

    run_number = record.get("run_number")
    timestamp_ms = record.get("timestamp_ms")
    track_count = record.get("track_count")
    max_energy_gev = record.get("max_energy_gev")
    total_energy_gev = record.get("total_energy_gev")
    schema_version = record.get("schema_version")

    if run_number is not None and run_number <= 0:
        violations.append(
            ("run_number", run_number, "must be greater than 0")
        )

    if timestamp_ms is not None and timestamp_ms <= 0:
        violations.append(
            ("timestamp_ms", timestamp_ms, "must be greater than 0")
        )

    if track_count is not None and track_count < 0:
        violations.append(
            ("track_count", track_count, "must be greater than or equal to 0")
        )

    if max_energy_gev is not None and max_energy_gev < 0:
        violations.append(
            (
                "max_energy_gev",
                max_energy_gev,
                "must be greater than or equal to 0",
            )
        )

    if total_energy_gev is not None and total_energy_gev < 0:
        violations.append(
            (
                "total_energy_gev",
                total_energy_gev,
                "must be greater than or equal to 0",
            )
        )

    if (
        max_energy_gev is not None
        and total_energy_gev is not None
        and max_energy_gev > total_energy_gev
    ):
        violations.append(
            (
                "max_energy_gev",
                max_energy_gev,
                "must not exceed total_energy_gev",
            )
        )

    if schema_version != "1.0":
        violations.append(
            ("schema_version", schema_version, "must equal 1.0")
        )

    return violations


def main():

    # Validate command-line arguments:
    # 1. Path to the ALICE Avro schema
    # 2. Path to the extracted ALICE JSONL dataset
    if len(sys.argv) != 3:
        print(
            "Usage: python scripts/alice_data_quality_check.py "
            "<alice_schema.avsc> <alice_dataset.jsonl>"
        )
        sys.exit(1)

    schema_path = Path(sys.argv[1])
    dataset_path = Path(sys.argv[2])

    total_records = 0
    invalid_json = 0
    schema_failures = 0
    missing_required = 0
    required_nulls = 0
    range_violations = 0
    examples = []

    try:
        _, parsed_schema = load_schema(schema_path)

        for line_number, record, json_error in read_jsonl(dataset_path):
            total_records += 1

            if json_error is not None:
                invalid_json += 1

                if len(examples) < 20:
                    examples.append(
                        (
                            line_number,
                            "JSON",
                            json_error,
                        )
                    )

                continue

            try:
                validate_schema_record(record, parsed_schema)
            except Exception as error:
                schema_failures += 1

                if len(examples) < 20:
                    examples.append(
                        (
                            line_number,
                            "Schema",
                            str(error),
                        )
                    )

            missing_fields = check_completeness(record)

            if missing_fields:
                missing_required += 1

                if len(examples) < 20:
                    examples.append(
                        (
                            line_number,
                            "Completeness",
                            ", ".join(missing_fields),
                        )
                    )

            null_fields = check_required_nulls(record)

            if null_fields:
                required_nulls += 1

                if len(examples) < 20:
                    examples.append(
                        (
                            line_number,
                            "Null",
                            ", ".join(null_fields),
                        )
                    )

            violations = check_ranges(record)
            range_violations += len(violations)

            for field, value, message in violations:
                if len(examples) < 20:
                    examples.append(
                        (
                            line_number,
                            "Range",
                            f"{field}={value}: {message}",
                        )
                    )

        print()
        print("=" * 72)
        print(f"Dataset: {dataset_path}")
        print("=" * 72)
        print(f"Total records: {total_records}")
        print(f"Invalid JSON records: {invalid_json}")
        print(f"Schema failures: {schema_failures}")
        print(f"Records with missing required fields: {missing_required}")
        print(f"Records with required null fields: {required_nulls}")
        print(f"Range violations: {range_violations}")

        if examples:
            print()
            print("Example violations:")

            for line_number, check_name, message in examples:
                print(
                    f"- Line {line_number} "
                    f"[{check_name}]: {message}"
                )

        total_failures = (
            invalid_json
            + schema_failures
            + missing_required
            + required_nulls
            + range_violations
        )

        print()
        print("=" * 72)

        if total_failures == 0:
            print("PASS: ALICE dataset passed all data-quality checks")
            sys.exit(0)

        print(f"FAIL: ALICE data-quality checks found {total_failures} issue(s)")
        sys.exit(1)

    except FileNotFoundError as error:
        print(f"ERROR: File not found: {error.filename}")
        sys.exit(1)

    except Exception as error:
        print(f"ERROR: {error}")
        sys.exit(1)


# Application entry point
if __name__ == "__main__":
    main()