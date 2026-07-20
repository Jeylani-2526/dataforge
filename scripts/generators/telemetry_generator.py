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


# One synthetic physical TELEMETRY sensor is used per generator process.
# The sensor ID remains stable while each event receives a unique event ID.
SENSOR_ID = new_uuid()

# Human-readable identifier of the synthetic telemetry device.
DEVICE_ID = "SENSOR-UNIT-01"

# Sequence numbering starts at zero so the first record receives number one.
SEQUENCE_NUMBER = 0

# The base timestamp remains stable throughout the generator process.
BASE_TIME_MS = current_timestamp_ms()

# Each consecutive sequence number advances simulated event time by one second.
TIMESTAMP_INTERVAL_MS = 1_000


# Normal base-signal definitions for supported telemetry parameters.
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
    Return the next sequence number for the synthetic telemetry device.

    Returns:
        A monotonically increasing integer sequence number.
    """
    global SEQUENCE_NUMBER

    SEQUENCE_NUMBER += 1
    return SEQUENCE_NUMBER


def synchronize_sequence_number(record: dict) -> None:
    """
    Synchronize the generator counter after a sequence gap is injected.

    This ensures that records following a missing_reading anomaly continue
    from the mutated sequence number instead of returning to the old counter.

    Args:
        record: Generated and labeled TELEMETRY record.
    """
    global SEQUENCE_NUMBER

    if record.get("anomaly_type") != "missing_reading":
        return

    sequence_number = record.get("sequence_number")

    if not isinstance(sequence_number, int):
        raise ValueError(
            "A missing_reading anomaly requires an integer sequence_number."
        )

    SEQUENCE_NUMBER = max(
        SEQUENCE_NUMBER,
        sequence_number,
    )


def calculate_timestamp_ms(sequence_number: int) -> int:
    """
    Calculate a deterministic timestamp for a sequence number.

    The deterministic formula allows the timestamp_stall anomaly to replace
    the current timestamp with the timestamp corresponding to the previous
    sequence number without maintaining cross-record state.

    Args:
        sequence_number: Current telemetry sequence number.

    Returns:
        Timestamp calculated from the generator base time and fixed interval.
    """
    return BASE_TIME_MS + sequence_number * TIMESTAMP_INTERVAL_MS


def generate_telemetry_record(
    anomaly_rate: float = DEFAULT_INJECTION_RATE,
) -> dict:
    """
    Generate one labeled synthetic TELEMETRY sensor record.

    A normal base-signal record is generated first. The record timestamp is
    calculated deterministically from its sequence number. An anomaly is then
    injected with the configured probability.

    Args:
        anomaly_rate: Probability of injecting an anomaly into the record.
            The default value is 0.03.

    Returns:
        A labeled TELEMETRY record containing either normal values or one of
        the configured TELEMETRY anomaly patterns.

    Raises:
        ValueError: If anomaly_rate is outside the inclusive range [0.0, 1.0].
    """
    parameter_name = random.choice(
        list(TELEMETRY_PARAMETERS.keys())
    )
    parameter_config = TELEMETRY_PARAMETERS[parameter_name]

    parameter_value = round(
        random.uniform(
            parameter_config["min"],
            parameter_config["max"],
        ),
        2,
    )

    sequence_number = next_sequence_number()
    timestamp_ms = calculate_timestamp_ms(sequence_number)

    record = {
        # Common SensorEvent fields.
        "event_id": new_uuid(),
        "sensor_id": SENSOR_ID,
        "sensor_type": "TELEMETRY",
        "timestamp_ms": timestamp_ms,

        # RADAR-specific fields are not applicable to TELEMETRY records.
        "target_id": None,
        "range_m": None,
        "bearing_deg": None,
        "elevation_deg": None,
        "velocity_ms": None,
        "signal_strength_db": None,

        # LIDAR-specific fields are not applicable to TELEMETRY records.
        "scan_id": None,
        "point_count": None,
        "centroid_x_m": None,
        "centroid_y_m": None,
        "centroid_z_m": None,
        "max_range_m": None,
        "avg_intensity": None,
        "min_intensity": None,

        # TELEMETRY-specific fields.
        "device_id": DEVICE_ID,
        "parameter_name": parameter_name,
        "value": parameter_value,
        "unit": parameter_config["unit"],
        "sequence_number": sequence_number,

        # Locked SensorEvent schema version.
        "schema_version": SCHEMA_VERSION,
    }

    record = inject_anomaly(
        record,
        anomaly_rate=anomaly_rate,
        timestamp_interval_ms=TIMESTAMP_INTERVAL_MS,
    )

    synchronize_sequence_number(record)

    return record


def parse_args() -> argparse.Namespace:
    """
    Parse command-line arguments for telemetry generation.

    Returns:
        Parsed command-line arguments.
    """
    parser = argparse.ArgumentParser(
        description="Generate labeled synthetic TELEMETRY sensor events.",
    )

    parser.add_argument(
        "--mode",
        choices=["fixed", "continuous"],
        required=True,
        help="Generation mode: fixed JSONL file or continuous output.",
    )

    parser.add_argument(
        "--output",
        default="data/synthetic/telemetry.jsonl",
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
    Run the TELEMETRY generator in fixed-file or continuous mode.

    Both modes use the same configurable anomaly-injection logic.
    """
    args = parse_args()

    record_factory = partial(
        generate_telemetry_record,
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
