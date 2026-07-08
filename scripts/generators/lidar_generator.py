import argparse
import random

from scripts.generators.common import (
    SCHEMA_VERSION,
    current_timestamp_ms,
    new_uuid,
    run_continuous,
    write_fixed_file,
)


# One synthetic physical LIDAR device per generator process.
# The sensor ID stays stable while individual event IDs change.
SENSOR_ID = new_uuid()


def generate_lidar_record() -> dict:
    """
    Generate one synthetic LIDAR base-signal event.

    Only LIDAR-specific fields contain values.
    RADAR and TELEMETRY fields are explicitly set to None
    to match the unified SensorEvent Avro schema.
    """
    return {
        # Common fields required for every SensorEvent record.
        "event_id": new_uuid(),
        "sensor_id": SENSOR_ID,
        "sensor_type": "LIDAR",
        "timestamp_ms": current_timestamp_ms(),

        # RADAR fields must be null for LIDAR records.
        "target_id": None,
        "range_m": None,
        "bearing_deg": None,
        "elevation_deg": None,
        "velocity_ms": None,
        "signal_strength_db": None,

        # LIDAR-specific base-signal fields.
        "scan_id": new_uuid(),
        "point_count": random.randint(10_000, 200_000),
        "centroid_x_m": round(random.uniform(-100.0, 100.0), 2),
        "centroid_y_m": round(random.uniform(-100.0, 100.0), 2),
        "centroid_z_m": round(random.uniform(-10.0, 50.0), 2),
        "max_range_m": round(random.uniform(50.0, 500.0), 2),
        "avg_intensity": round(random.uniform(80.0, 220.0), 2),
        "min_intensity": round(random.uniform(20.0, 100.0), 2),

        # TELEMETRY fields must be null for LIDAR records.
        "device_id": None,
        "parameter_name": None,
        "value": None,
        "unit": None,
        "sequence_number": None,

        # Locked schema version from sensor_schema_v1.avsc.
        "schema_version": SCHEMA_VERSION,
    }


def parse_args() -> argparse.Namespace:
    """
    Parse command-line arguments for fixed-file and continuous modes.
    """
    parser = argparse.ArgumentParser(
        description="Generate synthetic LIDAR base-signal events."
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
        default="data/synthetic/lidar.jsonl",
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
    Run the LIDAR generator in the selected output mode.
    """
    args = parse_args()

    if args.mode == "fixed":
        # Generate a finite JSONL corpus.
        write_fixed_file(
            output_path=args.output,
            record_factory=generate_lidar_record,
            count=args.count,
        )
    else:
        # Continuously emit fresh base-signal records.
        run_continuous(
            record_factory=generate_lidar_record,
            interval_ms=args.interval_ms,
        )


if __name__ == "__main__":
    main()