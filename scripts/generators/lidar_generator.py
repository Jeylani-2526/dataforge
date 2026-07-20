import argparse
import random
from functools import partial

from scripts.generators.anomaly_injection import (
    DEFAULT_INJECTION_RATE,
    inject_anomaly,
)
from scripts.generators.common import (
    SCHEMA_VERSION,
    current_timestamp_ms,
    new_uuid,
    run_continuous,
    write_fixed_file,
)


# One synthetic physical LIDAR device is used per generator process.
# The sensor ID remains stable while each event receives a unique event ID.
SENSOR_ID = new_uuid()


def generate_lidar_record(
    anomaly_rate: float = DEFAULT_INJECTION_RATE,
) -> dict:
    """
    Generate one labeled synthetic LIDAR sensor record.

    A normal base-signal record is created first. An anomaly is then injected
    with the configured probability. The returned record always carries the
    generator-assigned ``label`` and ``anomaly_type`` metadata fields.

    Args:
        anomaly_rate: Probability of injecting an anomaly into the record.
            The default value is 0.03.

    Returns:
        A labeled LIDAR record containing either normal base-signal values or
        one of the configured LIDAR anomaly patterns.

    Raises:
        ValueError: If anomaly_rate is outside the inclusive range [0.0, 1.0].
    """
    avg_intensity = round(
        random.uniform(80.0, 220.0),
        2,
    )

    min_intensity = round(
        random.uniform(
            20.0,
            min(100.0, avg_intensity),
        ),
        2,
    )

    record = {
        # Common SensorEvent fields.
        "event_id": new_uuid(),
        "sensor_id": SENSOR_ID,
        "sensor_type": "LIDAR",
        "timestamp_ms": current_timestamp_ms(),

        # RADAR-specific fields are not applicable to LIDAR records.
        "target_id": None,
        "range_m": None,
        "bearing_deg": None,
        "elevation_deg": None,
        "velocity_ms": None,
        "signal_strength_db": None,

        # LIDAR-specific fields.
        "scan_id": new_uuid(),
        "point_count": random.randint(10_000, 200_000),
        "centroid_x_m": round(random.uniform(-100.0, 100.0), 2),
        "centroid_y_m": round(random.uniform(-100.0, 100.0), 2),
        "centroid_z_m": round(random.uniform(-10.0, 50.0), 2),
        "max_range_m": round(random.uniform(50.0, 500.0), 2),
        "avg_intensity": avg_intensity,
        "min_intensity": min_intensity,

        # TELEMETRY-specific fields are not applicable to LIDAR records.
        "device_id": None,
        "parameter_name": None,
        "value": None,
        "unit": None,
        "sequence_number": None,

        # Locked SensorEvent schema version.
        "schema_version": SCHEMA_VERSION,
    }

    return inject_anomaly(
        record,
        anomaly_rate=anomaly_rate,
    )


def parse_args() -> argparse.Namespace:
    """
    Parse command-line arguments for LIDAR generation.

    Returns:
        Parsed command-line arguments.
    """
    parser = argparse.ArgumentParser(
        description="Generate labeled synthetic LIDAR sensor events.",
    )

    parser.add_argument(
        "--mode",
        choices=["fixed", "continuous"],
        required=True,
        help="Generation mode: fixed JSONL file or continuous output.",
    )

    parser.add_argument(
        "--output",
        default="data/synthetic/lidar.jsonl",
        help="Output JSONL path used in fixed mode.",
    )

    parser.add_argument(
        "--count",
        type=int,
        default=50_000,
        help="Number of records generated in fixed mode.",
    )

    parser.add_argument(
        "--interval-ms",
        type=int,
        default=0,
        help="Delay between emitted records in continuous mode.",
    )

    parser.add_argument(
        "--anomaly-rate",
        type=float,
        default=DEFAULT_INJECTION_RATE,
        help="Anomaly injection probability per record; default: 0.03.",
    )

    return parser.parse_args()


def main() -> None:
    """
    Run the LIDAR generator in fixed-file or continuous mode.

    Both modes use the same configurable anomaly-injection logic.
    """
    args = parse_args()

    record_factory = partial(
        generate_lidar_record,
        anomaly_rate=args.anomaly_rate,
    )

    if args.mode == "fixed":
        write_fixed_file(
            output_path=args.output,
            record_factory=record_factory,
            count=args.count,
        )
        return

    run_continuous(
        record_factory=record_factory,
        interval_ms=args.interval_ms,
    )


if __name__ == "__main__":
    main()
