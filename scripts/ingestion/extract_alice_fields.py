"""
DataForge — ALICE ESD Extraction Script
Task: M3W10
Owner: Beyza Ülkümen
Source: docs/data/root_to_avro_mapping.md

Extracts uproot-readable fields from AliESDs.root and writes NDJSON.
Momentum/energy fields require PyROOT (set to 0.0 until ROOT Docker available).
"""

import json
import uuid
import argparse
import uproot
import numpy as np
from pathlib import Path


def extract_alice_events(root_file_path: str, output_path: str) -> int:
    """
    Extract ALICE events from AliESDs.root using uproot.
    Returns number of records written.
    """
    with uproot.open(root_file_path) as f:
        tree = f["esdTree;1"]

        # run_number — scalar, same for all events in file
        run_number = int(tree["AliESDRun.fRunNumber"].array(library="np")[0])

        # timestamp_ms — uint32 seconds → long ms + event index tie-breaker
        timestamps_s   = tree["AliESDHeader.fTimeStamp"].array(library="np")
        event_numbers  = tree["AliESDHeader.fEventNumberInFile"].array(library="np")
        timestamps_ms  = [
            int(timestamps_s[i]) * 1000 + int(event_numbers[i]) % 1000
            for i in range(len(timestamps_s))
        ]

        # track_count — length of per-track fFlags array per event
        flags_per_event = tree["Tracks/Tracks.fFlags"].array(library="np")
        track_counts    = [int(len(flags)) for flags in flags_per_event]

    n_events = len(timestamps_ms)

    # Write NDJSON
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    with open(output, "w", encoding="utf-8") as out:
        for i in range(n_events):
            record = {
                "event_id":         str(uuid.uuid4()),
                "run_number":       run_number,
                "timestamp_ms":     timestamps_ms[i],
                "track_count":      track_counts[i],
                "net_momentum_x":   0.0,  # PyROOT required — ROOT Docker M4
                "net_momentum_y":   0.0,  # PyROOT required — ROOT Docker M4
                "net_momentum_z":   0.0,  # PyROOT required — ROOT Docker M4
                "max_energy_gev":   0.0,  # PyROOT required — ROOT Docker M4
                "total_energy_gev": 0.0,  # PyROOT required — ROOT Docker M4
                "schema_version":   "1.0"
            }
            out.write(json.dumps(record) + "\n")

    print(f"Generated {n_events} records -> {output}")
    return n_events


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Extract ALICE ESD events to NDJSON using uproot."
    )
    parser.add_argument(
        "--input",
        default="data/alice/AliESDs.root",
        help="Path to AliESDs.root file"
    )
    parser.add_argument(
        "--output",
        default="data/synthetic/alice.jsonl",
        help="Output NDJSON path"
    )
    args = parser.parse_args()

    extract_alice_events(args.input, args.output)
