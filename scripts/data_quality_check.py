import json
import sys
from collections import Counter, defaultdict
from io import BytesIO
from pathlib import Path

from fastavro import parse_schema, schemaless_reader, schemaless_writer
from fastavro.validation import validate


# Fields required for every sensor record
COMMON_REQUIRED_FIELDS = [
    "event_id",
    "sensor_id",
    "sensor_type",
    "timestamp_ms",
    "schema_version",
]


# Fields required according to the sensor type
TYPE_REQUIRED_FIELDS = {
    "RADAR": [
        "target_id",
        "range_m",
        "bearing_deg",
        "elevation_deg",
        "velocity_ms",
        "signal_strength_db",
    ],
    "LIDAR": [
        "scan_id",
        "point_count",
        "centroid_x_m",
        "centroid_y_m",
        "centroid_z_m",
        "max_range_m",
        "avg_intensity",
        "min_intensity",
    ],
    "TELEMETRY": [
        "device_id",
        "parameter_name",
        "value",
        "unit",
        "sequence_number",
    ],
}


def load_schema(schema_path):
    """
    Load and parse the Avro schema.
    """

    with open(schema_path, "r", encoding="utf-8") as schema_file:
        schema = json.load(schema_file)

    return schema, parse_schema(schema)


def get_schema_field_names(schema):
    """
    Extract the field names defined in the Avro schema.
    """

    return {
        field["name"]
        for field in schema.get("fields", [])
    }


def read_jsonl(file_path):
    """
    Read a JSON Lines file one record at a time.

    Empty lines are ignored. Invalid JSON lines are returned
    as errors without stopping validation of the remaining file.
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


def validate_schema_round_trip(record, parsed_schema, schema_fields):
    """
    Validate one record against the Avro schema.

    Fields not defined in the Avro schema are excluded before
    validation. Metadata fields such as "label" and
    "anomaly_type" therefore do not affect schema validation.

    The fastavro validation function is used instead of an exact
    round-trip equality comparison because Avro float values may
    change slightly during binary serialization due to floating-
    point precision.
    """

    schema_record = {
        key: value
        for key, value in record.items()
        if key in schema_fields
    }

    # Validate the record directly against the parsed Avro schema
    if not validate(schema_record, parsed_schema, raise_errors=True):
        return False

    # Perform serialization and deserialization to verify that
    # the record can also complete an Avro binary round trip.
    buffer = BytesIO()

    schemaless_writer(buffer, parsed_schema, schema_record)
    buffer.seek(0)

    schemaless_reader(buffer, parsed_schema)

    return True


def check_completeness(record):
    """
    Check whether all required fields are present in the record.

    This check only verifies field presence. A present field with
    a null value is handled separately by the null check.
    """

    missing_fields = []

    for field in COMMON_REQUIRED_FIELDS:
        if field not in record:
            missing_fields.append(field)

    sensor_type = record.get("sensor_type")

    for field in TYPE_REQUIRED_FIELDS.get(sensor_type, []):
        if field not in record:
            missing_fields.append(field)

    return missing_fields


def check_required_nulls(record):
    """
    Check whether fields required for the record's sensor type
    contain null values.

    Null fields belonging to other sensor variants are expected
    and are therefore not counted as validation failures.
    """

    null_fields = []

    for field in COMMON_REQUIRED_FIELDS:
        if record.get(field) is None:
            null_fields.append(field)

    sensor_type = record.get("sensor_type")

    for field in TYPE_REQUIRED_FIELDS.get(sensor_type, []):
        if record.get(field) is None:
            null_fields.append(field)

    return null_fields


def check_ranges(record):
    """
    Check numeric and categorical field ranges.

    These rules represent basic validity constraints. They should
    be adjusted if stricter project-specific limits are documented
    elsewhere in the repository.
    """

    violations = []

    sensor_type = record.get("sensor_type")

    if sensor_type not in TYPE_REQUIRED_FIELDS:
        violations.append(
            ("sensor_type", sensor_type, "unsupported sensor type")
        )

    timestamp_ms = record.get("timestamp_ms")

    if timestamp_ms is not None and timestamp_ms <= 0:
        violations.append(
            ("timestamp_ms", timestamp_ms, "must be greater than 0")
        )

    if record.get("schema_version") != "1.0":
        violations.append(
            (
                "schema_version",
                record.get("schema_version"),
                "must equal 1.0",
            )
        )

    if sensor_type == "RADAR":
        range_m = record.get("range_m")
        bearing_deg = record.get("bearing_deg")
        elevation_deg = record.get("elevation_deg")

        if range_m is not None and range_m < 0:
            violations.append(
                ("range_m", range_m, "must be greater than or equal to 0")
            )

        if bearing_deg is not None and not 0 <= bearing_deg <= 360:
            violations.append(
                ("bearing_deg", bearing_deg, "must be between 0 and 360")
            )

        if elevation_deg is not None and not -90 <= elevation_deg <= 90:
            violations.append(
                (
                    "elevation_deg",
                    elevation_deg,
                    "must be between -90 and 90",
                )
            )

    elif sensor_type == "LIDAR":
        point_count = record.get("point_count")
        max_range_m = record.get("max_range_m")
        avg_intensity = record.get("avg_intensity")
        min_intensity = record.get("min_intensity")

        if point_count is not None and point_count < 0:
            violations.append(
                (
                    "point_count",
                    point_count,
                    "must be greater than or equal to 0",
                )
            )

        if max_range_m is not None and max_range_m < 0:
            violations.append(
                (
                    "max_range_m",
                    max_range_m,
                    "must be greater than or equal to 0",
                )
            )

        if avg_intensity is not None and avg_intensity < 0:
            violations.append(
                (
                    "avg_intensity",
                    avg_intensity,
                    "must be greater than or equal to 0",
                )
            )

        if min_intensity is not None and min_intensity < 0:
            violations.append(
                (
                    "min_intensity",
                    min_intensity,
                    "must be greater than or equal to 0",
                )
            )

        if (
            min_intensity is not None
            and avg_intensity is not None
            and min_intensity > avg_intensity
        ):
            violations.append(
                (
                    "min_intensity",
                    min_intensity,
                    "must not exceed avg_intensity",
                )
            )

    elif sensor_type == "TELEMETRY":
        sequence_number = record.get("sequence_number")

        if sequence_number is not None and sequence_number < 0:
            violations.append(
                (
                    "sequence_number",
                    sequence_number,
                    "must be greater than or equal to 0",
                )
            )

        parameter_name = record.get("parameter_name")
        value = record.get("value")

        if (
            parameter_name == "battery_pct"
            and value is not None
            and not 0 <= value <= 100
        ):
            violations.append(
                (
                    "value",
                    value,
                    "battery_pct must be between 0 and 100",
                )
            )

    return violations


def validate_dataset(dataset_path, parsed_schema, schema_fields):
    """
    Run schema, completeness, null and range checks across
    an entire JSON Lines dataset.
    """

    results = {
        "dataset": str(dataset_path),
        "total_records": 0,
        "invalid_json": 0,
        "schema_failures": 0,
        "missing_required": 0,
        "required_nulls": 0,
        "range_violations": 0,
        "sensor_types": Counter(),
        "missing_fields": Counter(),
        "null_fields": Counter(),
        "range_fields": Counter(),
        "examples": [],
    }

    for line_number, record, json_error in read_jsonl(dataset_path):
        results["total_records"] += 1

        if json_error is not None:
            results["invalid_json"] += 1

            if len(results["examples"]) < 20:
                results["examples"].append(
                    {
                        "line": line_number,
                        "check": "JSON",
                        "message": json_error,
                    }
                )

            continue

        sensor_type = record.get("sensor_type", "UNKNOWN")
        results["sensor_types"][sensor_type] += 1

        try:
            schema_passed = validate_schema_round_trip(
                record,
                parsed_schema,
                schema_fields,
            )

            if not schema_passed:
                results["schema_failures"] += 1

        except Exception as error:
            results["schema_failures"] += 1

            if len(results["examples"]) < 20:
                results["examples"].append(
                    {
                        "line": line_number,
                        "check": "Schema",
                        "message": str(error),
                    }
                )

        missing_fields = check_completeness(record)

        if missing_fields:
            results["missing_required"] += 1
            results["missing_fields"].update(missing_fields)

            if len(results["examples"]) < 20:
                results["examples"].append(
                    {
                        "line": line_number,
                        "check": "Completeness",
                        "message": ", ".join(missing_fields),
                    }
                )

        null_fields = check_required_nulls(record)

        if null_fields:
            results["required_nulls"] += 1
            results["null_fields"].update(null_fields)

            if len(results["examples"]) < 20:
                results["examples"].append(
                    {
                        "line": line_number,
                        "check": "Null",
                        "message": ", ".join(null_fields),
                    }
                )

        range_violations = check_ranges(record)

        if range_violations:
            results["range_violations"] += len(range_violations)

            for field, value, message in range_violations:
                results["range_fields"][field] += 1

                if len(results["examples"]) < 20:
                    results["examples"].append(
                        {
                            "line": line_number,
                            "check": "Range",
                            "message": f"{field}={value}: {message}",
                        }
                    )

    return results


def print_results(results):
    """
    Print a readable validation summary for one dataset.
    """

    print()
    print("=" * 72)
    print(f"Dataset: {results['dataset']}")
    print("=" * 72)
    print(f"Total records: {results['total_records']}")
    print(f"Invalid JSON records: {results['invalid_json']}")
    print(f"Schema failures: {results['schema_failures']}")
    print(f"Records with missing required fields: {results['missing_required']}")
    print(f"Records with required null fields: {results['required_nulls']}")
    print(f"Range violations: {results['range_violations']}")
    print(f"Sensor types: {dict(results['sensor_types'])}")

    if results["examples"]:
        print()
        print("Example violations:")

        for example in results["examples"]:
            print(
                f"- Line {example['line']} "
                f"[{example['check']}]: {example['message']}"
            )


def main():

    # Validate command-line arguments:
    # 1. Path to the Avro schema
    # 2. One or more JSON Lines dataset paths
    if len(sys.argv) < 3:
        print(
            "Usage: python scripts/data_quality_check.py "
            "<schema.avsc> <dataset1.jsonl> [dataset2.jsonl ...]"
        )
        sys.exit(1)

    schema_path = Path(sys.argv[1])
    dataset_paths = [Path(path) for path in sys.argv[2:]]

    try:
        schema, parsed_schema = load_schema(schema_path)
        schema_fields = get_schema_field_names(schema)

        all_results = []

        for dataset_path in dataset_paths:
            results = validate_dataset(
                dataset_path,
                parsed_schema,
                schema_fields,
            )

            all_results.append(results)
            print_results(results)

        total_failures = sum(
            result["invalid_json"]
            + result["schema_failures"]
            + result["missing_required"]
            + result["required_nulls"]
            + result["range_violations"]
            for result in all_results
        )

        print()
        print("=" * 72)

        if total_failures == 0:
            print("PASS: All datasets passed all data-quality checks")
            sys.exit(0)

        print(f"FAIL: Data-quality checks found {total_failures} issue(s)")
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