import json
import sys
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
    batch_size: int = 1_000,
) -> None:
    """
    Continuously generate records until interrupted.

    Records are emitted in batches when no interval is configured. Batching
    reduces stdout overhead during M5 throughput tests. When an interval is
    configured, records are emitted individually to preserve the delay.
    """
    if interval_ms < 0:
        raise ValueError("interval_ms must not be negative.")

    if batch_size <= 0:
        raise ValueError("batch_size must be greater than zero.")

    buffered_lines: list[str] = []

    try:
        while True:
            record = record_factory()
            serialized_record = json.dumps(record) + "\n"

            if interval_ms > 0:
                sys.stdout.write(serialized_record)
                sys.stdout.flush()
                time.sleep(interval_ms / 1000)
                continue

            buffered_lines.append(serialized_record)

            if len(buffered_lines) >= batch_size:
                sys.stdout.write("".join(buffered_lines))
                sys.stdout.flush()
                buffered_lines.clear()

    except KeyboardInterrupt:
        if buffered_lines:
            sys.stdout.write("".join(buffered_lines))
            sys.stdout.flush()

        print("Continuous generation stopped.", file=sys.stderr)
