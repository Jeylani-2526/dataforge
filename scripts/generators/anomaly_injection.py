import random
from typing import Any


# A sensor record is stored as a Python dictionary
Record = dict[str, Any]


# Task requirement:
# 3% of generated records must contain anomalies
DEFAULT_INJECTION_RATE = 0.03


# ---------------------------------------------------------------------------
# RADAR anomaly functions
# ---------------------------------------------------------------------------


def radar_range_spike(record: Record) -> Record:

    # Increase the radar range significantly
    if record.get("range_m") is not None:
        record["range_m"] = float(record["range_m"] * 5.0)

    return record


def radar_velocity_spike(record: Record) -> Record:

    # Increase the measured radar velocity
    if record.get("velocity_ms") is not None:
        record["velocity_ms"] = float(record["velocity_ms"] * 8.0)

    return record


def radar_signal_loss(record: Record) -> Record:

    # Set a very low signal strength to simulate signal loss
    record["signal_strength_db"] = -150.0

    return record


# ---------------------------------------------------------------------------
# LIDAR anomaly functions
# ---------------------------------------------------------------------------


def lidar_point_dropout(record: Record) -> Record:

    # Keep only 10% of the original LIDAR points
    if record.get("point_count") is not None:
        record["point_count"] = max(
            1,
            int(record["point_count"] * 0.10),
        )

    return record


def lidar_obstruction(record: Record) -> Record:

    # Reduce the maximum visible range
    if record.get("max_range_m") is not None:
        record["max_range_m"] = float(
            record["max_range_m"] * 0.10
        )

    # Set very low return intensity
    record["min_intensity"] = 0.0

    return record


def lidar_centroid_shift(record: Record) -> Record:

    # Move the point-cloud centroid to an abnormal position
    if record.get("centroid_x_m") is not None:
        record["centroid_x_m"] = float(
            record["centroid_x_m"] + 100.0
        )

    if record.get("centroid_y_m") is not None:
        record["centroid_y_m"] = float(
            record["centroid_y_m"] + 100.0
        )

    return record


# ---------------------------------------------------------------------------
# TELEMETRY anomaly functions
# ---------------------------------------------------------------------------


def telemetry_value_spike(record: Record) -> Record:

    # Increase the telemetry value significantly
    if record.get("value") is not None:
        record["value"] = float(record["value"] * 5.0)

    return record


def telemetry_value_drop(record: Record) -> Record:

    # Reduce the telemetry value to 5% of its original value
    if record.get("value") is not None:
        record["value"] = float(record["value"] * 0.05)

    return record


def telemetry_sequence_gap(record: Record) -> Record:

    # Create a gap in the telemetry sequence
    if record.get("sequence_number") is not None:
        record["sequence_number"] = int(
            record["sequence_number"] + 10
        )

    return record


# Store all anomaly functions by sensor type
ANOMALIES = {
    "RADAR": {
        "range_spike": radar_range_spike,
        "velocity_spike": radar_velocity_spike,
        "signal_loss": radar_signal_loss,
    },
    "LIDAR": {
        "point_dropout": lidar_point_dropout,
        "obstruction": lidar_obstruction,
        "centroid_shift": lidar_centroid_shift,
    },
    "TELEMETRY": {
        "value_spike": telemetry_value_spike,
        "value_drop": telemetry_value_drop,
        "sequence_gap": telemetry_sequence_gap,
    },
}


def add_default_labels(record: Record) -> Record:

    # Copy the record so the original dictionary is not changed
    output = record.copy()

    # Normal records use label 0 and no anomaly type
    output["label"] = 0
    output["anomaly_type"] = None

    return output


def apply_anomaly(
    record: Record,
    anomaly_type: str,
) -> Record:

    # Add default normal labels first
    output = add_default_labels(record)

    # Read and normalize the sensor type
    sensor_type = output.get("sensor_type")

    if not isinstance(sensor_type, str):
        raise ValueError(
            "Record must contain a valid sensor_type."
        )

    sensor_type = sensor_type.upper()

    # Check that the sensor type is supported
    if sensor_type not in ANOMALIES:
        raise ValueError(
            f"Unsupported sensor type: {sensor_type}"
        )

    # Check that the anomaly exists for this sensor type
    if anomaly_type not in ANOMALIES[sensor_type]:
        raise ValueError(
            f"Unsupported anomaly type: {anomaly_type}"
        )

    # Apply the selected anomaly function
    anomaly_function = ANOMALIES[sensor_type][anomaly_type]
    output = anomaly_function(output)

    # Mark the record as anomalous
    output["label"] = 1
    output["anomaly_type"] = anomaly_type

    return output


def inject_anomaly(
    record: Record,
    injection_rate: float = DEFAULT_INJECTION_RATE,
) -> Record:

    # Validate the anomaly rate
    if not 0.0 <= injection_rate <= 1.0:
        raise ValueError(
            "injection_rate must be between 0.0 and 1.0."
        )

    # Add normal labels before making the random decision
    output = add_default_labels(record)

    # Keep the record normal in 97% of cases
    if random.random() >= injection_rate:
        return output

    # Read and normalize the sensor type
    sensor_type = output.get("sensor_type")

    if not isinstance(sensor_type, str):
        raise ValueError(
            "Record must contain a valid sensor_type."
        )

    sensor_type = sensor_type.upper()

    # Get the three anomaly types for this sensor
    sensor_anomalies = ANOMALIES.get(sensor_type)

    if sensor_anomalies is None:
        raise ValueError(
            f"Unsupported sensor type: {sensor_type}"
        )

    # Select one anomaly type with equal probability
    anomaly_type = random.choice(
        list(sensor_anomalies.keys())
    )

    # Apply and label the selected anomaly
    return apply_anomaly(output, anomaly_type)
