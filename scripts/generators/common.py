import json
import time
import uuid
from pathlib import Path
from typing import Any, Callable


# Default number of records required for the fixed training corpus.
RECORD_COUNT = 50_000

# Locked schema version defined in sensor_schema_v1.avsc.
SCHEMA_VERSION = "1.0"


def new_uuid() -> str:
    """Generate and return a new UUID v4 as a string."""
    return str(uuid.uuid4())


def current_timestamp_ms() -> int:
    """Return the current Unix timestamp in milliseconds."""
    return int(time.time() * 1000)


def write_fixed_file(
    output_path: str,
    record_factory: Callable[[], dict[str, Any]],
    count: int = RECORD_COUNT,
) -> None:
    """
    Generate a fixed number of base-signal records and write them
    to a JSON Lines file, with one JSON object per line.

    This mode is intended for the locked 50,000-record corpus
    required by the M7 training pipeline.
    """
    path = Path(output_path)

    # Create the parent directory automatically if it does not exist.
    path.parent.mkdir(parents=True, exist_ok=True)

    # Open the output file once and stream records line by line.
    with path.open("w", encoding="utf-8") as file:
        for _ in range(count):
            # The sensor-specific generator creates one base-signal record.
            record = record_factory()

            # JSONL format: one complete JSON object per line.
            file.write(json.dumps(record) + "\n")

    print(f"Generated {count} records -> {path}")


def run_continuous(
    record_factory: Callable[[], dict[str, Any]],
    interval_ms: int = 0,
) -> None:
    """
    Continuously generate base-signal records until interrupted.

    This mode is intended for later M5 throughput and load testing.
    An optional interval can be used to slow down event generation.
    """
    try:
        while True:
            # Generate one new sensor-specific base-signal record.
            record = record_factory()

            # Emit the record immediately to standard output.
            # flush=True prevents buffering delays in streaming scenarios.
            print(json.dumps(record), flush=True)

            # Sleep only when an interval is explicitly configured.
            if interval_ms > 0:
                time.sleep(interval_ms / 1000)

    except KeyboardInterrupt:
        # Allow clean shutdown with Ctrl+C during continuous generation.
        print("\nContinuous generation stopped.")