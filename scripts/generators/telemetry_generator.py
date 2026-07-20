import argparse
import random

from scripts.generators.anomaly_injection import inject_anomaly
from scripts.generators.common import (
    SCHEMA_VERSION,
    current_timestamp_ms,
    new_uuid,
    run_continuous,
    write_fixed_file,
)


# One synthetic physical TELEMETRY sensor per generator process.
# The sensor ID stays stable while individual event IDs change.
SENSOR_ID = new_uuid()

# Human-readable identifier for the synthetic device.
DEVICE_ID = "SENSOR-UNIT-01"

# Monotonically increasing sequence counter for this device.
# Starting at zero allows the first emitted record to use sequence number 1.
SEQUENCE_NUMBER = 0


# Base-signal definitions for supported telemetry parameters.
# Each parameter is mapped to its unit and a normal synthetic value range.
# These ranges represent base behavior only; no anomaly injection is applied.
TELEMETRY_PARAMETERS = {
    "cpu_temp_c": {
        "unit": "C",
        "min": 35.0,
        "max": 75.0,
    },
    "battery_pct": {
        "unit": "%",
        "min": 20.0,
        "max": 100.0,
    },
    "voltage_v": {
        "unit": "V",
        "min": 11.0,
        "max": 13.0,
    },
}


def next_sequence_number() -> int:
    """
    Return the next monotonically increasing sequence number
    for the current synthetic telemetry device.
    """
    global SEQUENCE_NUMBER

    SEQUENCE_NUMBER += 1
    return SEQUENCE_NUMBER


def generate_telemetry_record() -> dict:
    """
    Generate one synthetic TELEMETRY base-signal event.

    Only TELEMETRY-specific fields contain values.
    RADAR and LIDAR fields are explicitly set to None
    to match the unified SensorEvent Avro schema.
    """

    # Select one supported telemetry parameter at random.
    parameter_name = random.choice(
        list(TELEMETRY_PARAMETERS.keys())
    )

    # Retrieve the matching unit and normal base-signal range.
    parameter_config = TELEMETRY_PARAMETERS[parameter_name]

    # Generate a value inside the configured normal range.
    parameter_value = round(
        random.uniform(
            parameter_config["min"],
            parameter_config["max"],
        ),
        2,
    )

    # Create a normal TELEMETRY record
    record = {
        # Common fields required for every SensorEvent record.
        "event_id": new_uuid(),
        "sensor_id": SENSOR_ID,
        "sensor_type": "TELEMETRY",
        "timestamp_ms": current_timestamp_ms(),

        # RADAR fields must be null for TELEMETRY records.
        "target_id": None,
        "range_m": None,
        "bearing_deg": None,
        "elevation_deg": None,
        "velocity_ms": None,
        "signal_strength_db": None,

        # LIDAR fields must be null for TELEMETRY records.
        "scan_id": None,
        "point_count": None,
        "centroid_x_m": None,
        "centroid_y_m": None,
        "centroid_z_m": None,
        "max_range_m": None,
        "avg_intensity": None,
        "min_intensity": None,

        # TELEMETRY-specific base-signal fields.
        "device_id": DEVICE_ID,
        "parameter_name": parameter_name,
        "value": parameter_value,
        "unit": parameter_config["unit"],
        "sequence_number": next_sequence_number(),

        # Locked schema version from sensor_schema_v1.avsc.
        "schema_version": SCHEMA_VERSION,
    }

    # Apply anomaly injection before returning the record
    record = inject_anomaly(record)

    return record


def parse_args() -> argparse.Namespace:
    """
    Parse command-line arguments for fixed-file and continuous modes.
    """
    parser = argparse.ArgumentParser(
        description="Generate synthetic TELEMETRY base-signal events."
    )

    # Required output mode:
    # fixed      -> write a finite JSONL corpus
    # continuous -> emit records continuously
    parser.add_argument(
        "--mode",
        choices=["fixed", "continuous"],
        required=True,
        help="Generation mode: fixed file or continuous stream.",
    )

    # Output path used by fixed-file mode.
    parser.add_argument(
        "--output",
        default="data/synthetic/telemetry.jsonl",
        help="Output JSONL path for fixed-file mode.",
    )

    # The task requires a locked 50,000-record corpus by default.
    # A smaller value can still be passed explicitly for smoke tests.
    parser.add_argument(
        "--count",
        type=int,
        default=50_000,
        help="Number of records to generate in fixed mode.",
    )

    # Optional delay between events in continuous mode.
    # Zero means no intentional delay.
    parser.add_argument(
        "--interval-ms",
        type=int,
        default=0,
        help="Delay between continuous events in milliseconds.",
    )

    return parser.parse_args()


def main() -> None:
    """
    Run the TELEMETRY generator in the selected output mode.
    """
    args = parse_args()

    if args.mode == "fixed":
        # Generate a finite JSONL corpus.
        write_fixed_file(
            output_path=args.output,
            record_factory=generate_telemetry_record,
            count=args.count,
        )
    else:
        # Continuously emit fresh base-signal records.
        run_continuous(
            record_factory=generate_telemetry_record,
            interval_ms=args.interval_ms,
        )


if __name__ == "__main__":
    main()
