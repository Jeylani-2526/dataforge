import json
import math
import uuid
import argparse
import ROOT
from pathlib import Path

M_PION = 0.13957  # GeV/c^2 - pion mass, ALICE convention for unidentified tracks


def derive_track_momenta(tree):
    """
    Direct TLeaf.GetValue() decoding of Double32_t Tracks.fP / Tracks.fAlpha
    for the current event (per docs/data/root_to_avro_mapping.md Section 3),
    the method proven in the M3W11T2 conformance audit. Returns per-track
    (px, py, pz) lists in the global ALICE frame.
    """
    fP_leaf = tree.GetLeaf("Tracks.fP")
    fAlpha_leaf = tree.GetLeaf("Tracks.fAlpha")
    n_tracks = fAlpha_leaf.GetLen()

    px_list, py_list, pz_list = [], [], []
    for t in range(n_tracks):
        fP4 = fP_leaf.GetValue(t * 5 + 4)  # q/pt, (GeV/c)^-1
        fP2 = fP_leaf.GetValue(t * 5 + 2)  # sin(phi)
        fP3 = fP_leaf.GetValue(t * 5 + 3)  # tan(lambda)
        fAlpha = fAlpha_leaf.GetValue(t)

        if fP4 == 0.0:
            px_list.append(0.0)
            py_list.append(0.0)
            pz_list.append(0.0)
            continue

        pt = abs(1.0 / fP4)
        phi = fAlpha + math.asin(fP2)
        px_list.append(pt * math.cos(phi))
        py_list.append(pt * math.sin(phi))
        pz_list.append(pt * fP3)

    return px_list, py_list, pz_list


def extract_alice_events(root_file_path: str, output_path: str) -> int:
    """
    Extract ALICE events from AliESDs.root using PyROOT direct TLeaf.GetValue()
    branch access. Filters to fEventType=7 (genuine physics events only).
    Returns number of records written.
    """
    root_file = ROOT.TFile.Open(root_file_path)
    tree = root_file.Get("esdTree")

    n_entries = tree.GetEntries()

    # run_number — scalar, same for all events in file
    tree.GetEntry(0)
    run_number = int(tree.GetLeaf("AliESDRun.fRunNumber").GetValue(0))

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    written = 0
    with open(output, "w", encoding="utf-8") as out:
        for i in range(n_entries):
            tree.GetEntry(i)

            event_type = int(tree.GetLeaf("AliESDHeader.fEventType").GetValue(0))
            if event_type != 7:
                continue

            # timestamp_ms — uint32 seconds -> long ms + event index tie-breaker
            timestamp_s = int(tree.GetLeaf("AliESDHeader.fTimeStamp").GetValue(0))
            event_number = int(tree.GetLeaf("AliESDHeader.fEventNumberInFile").GetValue(0))
            timestamp_ms = timestamp_s * 1000 + event_number % 1000

            # track_count — length of the per-track fFlags array for this event
            track_count = int(tree.GetLeaf("Tracks.fFlags").GetLen())

            px_list, py_list, pz_list = derive_track_momenta(tree)

            net_momentum_x = float(sum(px_list))
            net_momentum_y = float(sum(py_list))
            net_momentum_z = float(sum(pz_list))

            energies = [
                math.sqrt(px ** 2 + py ** 2 + pz ** 2 + M_PION ** 2)
                for px, py, pz in zip(px_list, py_list, pz_list)
            ]
            max_energy_gev = float(max(energies)) if energies else 0.0
            total_energy_gev = float(sum(energies))

            record = {
                "event_id":         str(uuid.uuid4()),
                "run_number":       run_number,
                "timestamp_ms":     timestamp_ms,
                "track_count":      track_count,
                "net_momentum_x":   net_momentum_x,
                "net_momentum_y":   net_momentum_y,
                "net_momentum_z":   net_momentum_z,
                "max_energy_gev":   max_energy_gev,
                "total_energy_gev": total_energy_gev,
                "schema_version":   "1.0"
            }
            out.write(json.dumps(record) + "\n")
            written += 1

    print(f"Total events in file : {n_entries}")
    print(f"Physics events (fEventType=7): {written}")
    print(f"Output: {output}")
    return written


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Extract ALICE ESD events to NDJSON using PyROOT."
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
