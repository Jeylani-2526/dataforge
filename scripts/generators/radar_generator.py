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


# One synthetic physical RADAR device is used per generator process.
# The sensor ID remains stable while each event receives a unique event ID.
SENSOR_ID = new_uuid()


def generate_radar_record(
    anomaly_rate: float = DEFAULT_INJECTION_RATE,
) -> dict:
    """
    Generate one labeled synthetic RADAR sensor record.

    A normal base-signal record is created first. An anomaly is then injected
    with the configured probability. The returned record always carries the
    generator-assigned ``label`` and ``anomaly_type`` metadata fields.

    Args:
        anomaly_rate: Probability of injecting an anomaly into the record.
            The default value is 0.03.

    Returns:
        A labeled RADAR record containing either normal base-signal values or
        one of the configured RADAR anomaly patterns.

    Raises:
        ValueError: If anomaly_rate is outside the inclusive range [0.0, 1.0].
    """
    record = {
        # Common SensorEvent fields.
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

        # LIDAR-specific fields are not applicable to RADAR records.
        "scan_id": None,
        "point_count": None,
        "centroid_x_m": None,
        "centroid_y_m": None,
        "centroid_z_m": None,
        "max_range_m": None,
        "avg_intensity": None,
        "min_intensity": None,

        # TELEMETRY-specific fields are not applicable to RADAR records.
        "device_id": None,
        "parameter_name": None,
        "value": None,
        "unit": None,
        "sequence_number": None,

        # Locked schema version carried by every SensorEvent record.
        "schema_version": SCHEMA_VERSION,
    }

    return inject_anomaly(
        record,
        anomaly_rate=anomaly_rate,
    )


def parse_args() -> argparse.Namespace:
    """
    Parse command-line arguments for fixed-file and continuous generation.

    Returns:
        Parsed command-line arguments.
    """
    parser = argparse.ArgumentParser(
        description="Generate labeled synthetic RADAR sensor events.",
    )

    parser.add_argument(
        "--mode",
        choices=["fixed", "continuous"],
        required=True,
        help="Generation mode: fixed JSONL file or continuous output.",
    )

    parser.add_argument(
        "--output",
        default="data/synthetic/radar.jsonl",
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
        help="Delay between records in continuous mode, in milliseconds.",
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
    Run the RADAR generator in fixed-file or continuous mode.

    The same configurable anomaly-injection logic is used in both modes.
    """
    args = parse_args()

    record_factory = partial(
        generate_radar_record,
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
