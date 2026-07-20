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


# One synthetic physical RADAR device per generator process.
# The sensor ID stays stable while individual event IDs change.
SENSOR_ID = new_uuid()


def generate_radar_record() -> dict:
    """
    Generate one synthetic RADAR base-signal event.
    """

    # Create a normal RADAR record
    record = {
        # Common fields required for every SensorEvent record.
        "event_id": new_uuid(),
        "sensor_id": SENSOR_ID,
        "sensor_type": "RADAR",
        "timestamp_ms": current_timestamp_ms(),

        # RADAR-specific fields.
        "target_id": f"TARGET-{random.randint(1, 500):04d}",
        "range_m": round(random.uniform(50.0, 5000.0), 2),
        "bearing_deg": round(random.uniform(0.0, 360.0), 2),
        "elevation_deg": round(random.uniform(-30.0, 30.0), 2),
        "velocity_ms": round(random.uniform(-100.0, 300.0), 2),
        "signal_strength_db": round(random.uniform(-90.0, -20.0), 2),

        # LIDAR fields
        "scan_id": None,
        "point_count": None,
        "centroid_x_m": None,
        "centroid_y_m": None,
        "centroid_z_m": None,
        "max_range_m": None,
        "avg_intensity": None,
        "min_intensity": None,

        # TELEMETRY fields
        "device_id": None,
        "parameter_name": None,
        "value": None,
        "unit": None,
        "sequence_number": None,

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
        description="Generate synthetic RADAR base-signal events."
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
        default="data/synthetic/radar.jsonl",
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
    Run the RADAR generator in the selected output mode.
    """
    args = parse_args()

    if args.mode == "fixed":
        # Generate a finite JSONL corpus.
        write_fixed_file(
            output_path=args.output,
            record_factory=generate_radar_record,
            count=args.count,
        )
    else:
        # Continuously emit fresh base-signal records.
        run_continuous(
            record_factory=generate_radar_record,
            interval_ms=args.interval_ms,
        )
if __name__ == "__main__":
    main()
