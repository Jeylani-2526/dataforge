import random
from collections.abc import Callable
from typing import Any


# A generated sensor record is represented as a Python dictionary.
Record = dict[str, Any]

# All mutation functions share the same callable interface.
AnomalyFunction = Callable[[Record, int], Record]

# Three percent of generated records contain anomalies by default.
DEFAULT_INJECTION_RATE = 0.03

# Default deterministic interval between TELEMETRY timestamps.
DEFAULT_TIMESTAMP_INTERVAL_MS = 1_000


def require_numeric_field(record: Record, field_name: str) -> float:
    """
    Return a required numeric field as a float.

    Args:
        record: Sensor record containing the requested field.
        field_name: Name of the required numeric field.

    Returns:
        Numeric field value converted to float.

    Raises:
        ValueError: If the field is missing or is not numeric.
    """
    value = record.get(field_name)

    if not isinstance(value, (int, float)):
        raise ValueError(
            f"Record must contain a numeric {field_name} field."
        )

    return float(value)


# ---------------------------------------------------------------------------
# RADAR anomaly functions
# ---------------------------------------------------------------------------


def radar_ghost_target(
    record: Record,
    timestamp_interval_ms: int,
) -> Record:
    """
    Inject a geometrically unrealistic RADAR ghost target.

    The target is placed outside the normal RADAR operating envelope and is
    paired with an abnormally weak signal strength.

    Args:
        record: Normal RADAR base-signal record.
        timestamp_interval_ms: Unused timestamp interval.

    Returns:
        Mutated RADAR record.
    """
    del timestamp_interval_ms

    record["range_m"] = round(random.uniform(7_500.0, 12_000.0), 2)
    record["bearing_deg"] = round(random.uniform(380.0, 720.0), 2)
    record["elevation_deg"] = round(random.uniform(60.0, 90.0), 2)
    record["signal_strength_db"] = round(
        random.uniform(-145.0, -120.0),
        2,
    )

    return record


def radar_velocity_spike(
    record: Record,
    timestamp_interval_ms: int,
) -> Record:
    """
    Replace RADAR velocity with an implausibly large isolated value.

    Only velocity_ms is changed so downstream SHAP attribution can isolate
    velocity as the anomalous feature.

    Args:
        record: Normal RADAR base-signal record.
        timestamp_interval_ms: Unused timestamp interval.

    Returns:
        Mutated RADAR record.
    """
    del timestamp_interval_ms

    direction = random.choice([-1.0, 1.0])
    record["velocity_ms"] = round(
        direction * random.uniform(800.0, 1_500.0),
        2,
    )

    return record


def radar_sensor_dropout(
    record: Record,
    timestamp_interval_ms: int,
) -> Record:
    """
    Collapse RADAR signal strength toward the noise floor.

    Args:
        record: Normal RADAR base-signal record.
        timestamp_interval_ms: Unused timestamp interval.

    Returns:
        Mutated RADAR record.
    """
    del timestamp_interval_ms

    record["signal_strength_db"] = round(
        random.uniform(-160.0, -145.0),
        2,
    )

    return record


# ---------------------------------------------------------------------------
# LIDAR anomaly functions
# ---------------------------------------------------------------------------


def lidar_noise_burst(
    record: Record,
    timestamp_interval_ms: int,
) -> Record:
    """
    Inject abnormal intensity variation and centroid jitter.

    Args:
        record: Normal LIDAR base-signal record.
        timestamp_interval_ms: Unused timestamp interval.

    Returns:
        Mutated LIDAR record.
    """
    del timestamp_interval_ms

    centroid_x = require_numeric_field(record, "centroid_x_m")
    centroid_y = require_numeric_field(record, "centroid_y_m")
    centroid_z = require_numeric_field(record, "centroid_z_m")

    record["avg_intensity"] = round(
        random.uniform(350.0, 600.0),
        2,
    )
    record["min_intensity"] = round(
        random.uniform(250.0, 340.0),
        2,
    )
    record["centroid_x_m"] = round(
        centroid_x + random.uniform(-300.0, 300.0),
        2,
    )
    record["centroid_y_m"] = round(
        centroid_y + random.uniform(-300.0, 300.0),
        2,
    )
    record["centroid_z_m"] = round(
        centroid_z + random.uniform(-150.0, 150.0),
        2,
    )

    return record


def lidar_point_cloud_dropout(
    record: Record,
    timestamp_interval_ms: int,
) -> Record:
    """
    Collapse the LIDAR point cloud and degrade minimum intensity.

    Args:
        record: Normal LIDAR base-signal record.
        timestamp_interval_ms: Unused timestamp interval.

    Returns:
        Mutated LIDAR record.
    """
    del timestamp_interval_ms

    record["point_count"] = random.randint(0, 10)
    record["min_intensity"] = round(
        random.uniform(0.0, 5.0),
        2,
    )

    return record


def lidar_ghost_point(
    record: Record,
    timestamp_interval_ms: int,
) -> Record:
    """
    Generate a geometrically inconsistent single-point LIDAR return.

    The centroid is placed far beyond the assigned maximum range while the
    point cloud contains exactly one point.

    Args:
        record: Normal LIDAR base-signal record.
        timestamp_interval_ms: Unused timestamp interval.

    Returns:
        Mutated LIDAR record.
    """
    del timestamp_interval_ms

    record["point_count"] = 1
    record["centroid_x_m"] = round(
        random.uniform(600.0, 1_000.0),
        2,
    )
    record["centroid_y_m"] = round(
        random.uniform(600.0, 1_000.0),
        2,
    )
    record["centroid_z_m"] = round(
        random.uniform(300.0, 600.0),
        2,
    )
    record["max_range_m"] = round(
        random.uniform(10.0, 25.0),
        2,
    )

    return record


# ---------------------------------------------------------------------------
# TELEMETRY anomaly functions
# ---------------------------------------------------------------------------


def telemetry_out_of_range_value(
    record: Record,
    timestamp_interval_ms: int,
) -> Record:
    """
    Set TELEMETRY value outside the parameter's valid physical range.

    Args:
        record: Normal TELEMETRY base-signal record.
        timestamp_interval_ms: Unused timestamp interval.

    Returns:
        Mutated TELEMETRY record.

    Raises:
        ValueError: If parameter_name is unsupported.
    """
    del timestamp_interval_ms

    parameter_name = record.get("parameter_name")

    anomalous_ranges = {
        "cpu_temp_c": (125.0, 180.0),
        "battery_pct": (110.0, 150.0),
        "voltage_v": (20.0, 30.0),
    }

    if parameter_name not in anomalous_ranges:
        raise ValueError(
            f"Unsupported telemetry parameter: {parameter_name}"
        )

    minimum, maximum = anomalous_ranges[parameter_name]
    record["value"] = round(random.uniform(minimum, maximum), 2)

    return record


def telemetry_timestamp_stall(
    record: Record,
    timestamp_interval_ms: int,
) -> Record:
    """
    Replace the timestamp with the previous sequence timestamp.

    The mutation reproduces the value generated by the deterministic formula
    for sequence_number minus one. The sequence number itself is unchanged.

    Args:
        record: Normal TELEMETRY base-signal record.
        timestamp_interval_ms: Deterministic interval between timestamps.

    Returns:
        Mutated TELEMETRY record.

    Raises:
        ValueError: If timestamp_ms is missing or not numeric.
    """
    timestamp_ms = require_numeric_field(record, "timestamp_ms")

    record["timestamp_ms"] = int(
        timestamp_ms - timestamp_interval_ms
    )

    return record


def telemetry_missing_reading(
    record: Record,
    timestamp_interval_ms: int,
) -> Record:
    """
    Introduce a gap in the TELEMETRY sequence number.

    Args:
        record: Normal TELEMETRY base-signal record.
        timestamp_interval_ms: Unused timestamp interval.

    Returns:
        Mutated TELEMETRY record.
    """
    del timestamp_interval_ms

    sequence_number = require_numeric_field(
        record,
        "sequence_number",
    )
    record["sequence_number"] = int(
        sequence_number + random.randint(2, 10)
    )

    return record


# Each stream has exactly three uniformly selectable anomaly types.
ANOMALIES: dict[str, dict[str, AnomalyFunction]] = {
    "RADAR": {
        "ghost_target": radar_ghost_target,
        "velocity_spike": radar_velocity_spike,
        "sensor_dropout": radar_sensor_dropout,
    },
    "LIDAR": {
        "noise_burst": lidar_noise_burst,
        "point_cloud_dropout": lidar_point_cloud_dropout,
        "ghost_point": lidar_ghost_point,
    },
    "TELEMETRY": {
        "out_of_range_value": telemetry_out_of_range_value,
        "timestamp_stall": telemetry_timestamp_stall,
        "missing_reading": telemetry_missing_reading,
    },
}


def add_default_labels(record: Record) -> Record:
    """
    Copy a sensor record and attach normal-record labels.

    Args:
        record: Unlabeled base-signal record.

    Returns:
        Copied record with label zero and a null anomaly type.
    """
    output = record.copy()
    output["label"] = 0
    output["anomaly_type"] = None

    return output


def get_sensor_anomalies(
    record: Record,
) -> tuple[str, dict[str, AnomalyFunction]]:
    """
    Validate sensor_type and return its anomaly mapping.

    Args:
        record: Sensor record containing sensor_type.

    Returns:
        Normalized sensor type and its supported anomaly mapping.

    Raises:
        ValueError: If sensor_type is missing or unsupported.
    """
    sensor_type = record.get("sensor_type")

    if not isinstance(sensor_type, str):
        raise ValueError(
            "Record must contain a valid sensor_type."
        )

    sensor_type = sensor_type.upper()
    sensor_anomalies = ANOMALIES.get(sensor_type)

    if sensor_anomalies is None:
        raise ValueError(
            f"Unsupported sensor type: {sensor_type}"
        )

    return sensor_type, sensor_anomalies


def apply_anomaly(
    record: Record,
    anomaly_type: str,
    timestamp_interval_ms: int = DEFAULT_TIMESTAMP_INTERVAL_MS,
) -> Record:
    """
    Apply one selected anomaly and attach anomalous labels.

    Args:
        record: Base-signal sensor record.
        anomaly_type: Stream-specific snake_case anomaly identifier.
        timestamp_interval_ms: Deterministic TELEMETRY timestamp interval.

    Returns:
        Copied and mutated record with anomalous labels.

    Raises:
        ValueError: If the sensor or anomaly type is unsupported.
    """
    if timestamp_interval_ms <= 0:
        raise ValueError(
            "timestamp_interval_ms must be greater than zero."
        )

    output = add_default_labels(record)
    sensor_type, sensor_anomalies = get_sensor_anomalies(output)

    anomaly_function = sensor_anomalies.get(anomaly_type)

    if anomaly_function is None:
        raise ValueError(
            f"Unsupported anomaly type for {sensor_type}: "
            f"{anomaly_type}"
        )

    output = anomaly_function(
        output,
        timestamp_interval_ms,
    )
    output["label"] = 1
    output["anomaly_type"] = anomaly_type

    return output


def inject_anomaly(
    record: Record,
    anomaly_rate: float = DEFAULT_INJECTION_RATE,
    timestamp_interval_ms: int = DEFAULT_TIMESTAMP_INTERVAL_MS,
) -> Record:
    """
    Randomly inject a stream-specific anomaly into a sensor record.

    The record is selected through a Bernoulli trial using anomaly_rate.
    Selected records receive one of the stream's three anomaly types with
    uniform probability. Non-selected records retain their base-signal values.

    Args:
        record: Unlabeled base-signal sensor record.
        anomaly_rate: Probability of injecting an anomaly.
        timestamp_interval_ms: Deterministic TELEMETRY timestamp interval.

    Returns:
        Labeled normal or anomalous sensor record.

    Raises:
        ValueError: If anomaly_rate or timestamp_interval_ms is invalid.
    """
    if not 0.0 <= anomaly_rate <= 1.0:
        raise ValueError(
            "anomaly_rate must be between 0.0 and 1.0."
        )

    if timestamp_interval_ms <= 0:
        raise ValueError(
            "timestamp_interval_ms must be greater than zero."
        )

    output = add_default_labels(record)

    if random.random() >= anomaly_rate:
        return output

    _, sensor_anomalies = get_sensor_anomalies(output)
    anomaly_type = random.choice(
        list(sensor_anomalies.keys())
    )

    return apply_anomaly(
        output,
        anomaly_type,
        timestamp_interval_ms=timestamp_interval_ms,
    )
