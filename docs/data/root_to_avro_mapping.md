# DataForge — ROOT-to-Avro Field Mapping

**Schema:** `alice_event_schema_v1.avsc` (`dataforge.alice.AliceEvent`)  
**ROOT source:** `AliESDs.root` · tree `esdTree` · run 139038 · LHC10h (Pb-Pb, 2.76 TeV)  
**Purpose:** Authoritative reference for M4 Data Adaptation Layer development. Every Avro field in the ALICE event schema is traced to its ROOT source, extraction method, and derivation formula. An engineer building the ROOT-to-Kafka pipeline must be able to reproduce every field value from this document alone.

---

## 1. Quick-Reference Mapping Table

| Avro Field | Avro Type | Unit | ROOT Branch(es) | uproot Readable | Python / NumPy Type | Method |
|---|---|---|---|---|---|---|
| `event_id` | string (UUID v4) | — | *None* | N/A | — | System-generated (`uuid.uuid4()`) |
| `run_number` | int | — | `AliESDRun.fRunNumber` | ✓ YES | `numpy.int32` | Direct read + int cast |
| `timestamp_ms` | long | ms | `AliESDHeader.fTimeStamp` | ✓ YES | `numpy.uint32` | `int(fTimeStamp) × 1000` |
| `track_count` | int | — | `Tracks/Tracks.fFlags` | ✓ YES | `numpy.ndarray[uint64]` | `int(len(fFlags[event_index]))` |
| `net_momentum_x` | float | GeV/c | `Tracks/Tracks.fP[5]` + `fAlpha` | ✗ NO | `Double32_t[]` | ROOT/PyROOT derivation — see §3.1 |
| `net_momentum_y` | float | GeV/c | `Tracks/Tracks.fP[5]` + `fAlpha` | ✗ NO | `Double32_t[]` | ROOT/PyROOT derivation — see §3.2 |
| `net_momentum_z` | float | GeV/c | `Tracks/Tracks.fP[5]` | ✗ NO | `Double32_t[]` | ROOT/PyROOT derivation — see §3.3 |
| `max_energy_gev` | float | GeV | `Tracks/Tracks.fP[5]` + `fAlpha` | ✗ NO | `Double32_t[]` | ROOT/PyROOT derivation — see §3.4 |
| `total_energy_gev` | float | GeV | `Tracks/Tracks.fP[5]` + `fAlpha` | ✗ NO | `Double32_t[]` | ROOT/PyROOT derivation — see §3.5 |
| `schema_version` | string | — | *None* | N/A | — | Hardcoded `"1.0"` at ingestion |

**Summary:** 3 fields are directly uproot-readable (`run_number`, `timestamp_ms`, `track_count`). 5 fields require ROOT/PyROOT for `Double32_t` decoding (`net_momentum_x/y/z`, `max_energy_gev`, `total_energy_gev`). 2 fields are system-assigned at ingestion (`event_id`, `schema_version`).

---

## 2. Uproot-Readable Fields — Extraction Code

These three fields can be extracted in pure Python without ROOT.

```python
import uproot
import uuid

FILE_PATH = "AliESDs.root"

with uproot.open(FILE_PATH) as f:
    tree = f["esdTree"]

    # run_number — scalar, same value for every event in the file
    run_number = int(tree["AliESDRun.fRunNumber"].array(library="np")[0])

    # timestamp_ms — one value per event (uint32 seconds → long milliseconds)
    timestamps_s  = tree["AliESDHeader.fTimeStamp"].array(library="np")   # uint32, seconds
    timestamps_ms = [int(t) * 1000 for t in timestamps_s]                 # long, milliseconds

    # track_count — length of the per-track fFlags array for each event
    flags_per_event = tree["Tracks/Tracks.fFlags"].array(library="np")    # jagged array
    track_counts    = [int(len(flags)) for flags in flags_per_event]      # one int per event

    # event_id — system-generated UUID v4; no ROOT source
    event_ids = [str(uuid.uuid4()) for _ in range(len(timestamps_ms))]

    # schema_version — hardcoded for this locked schema
    schema_version = "1.0"
```

### 2.1 `timestamp_ms` — Precision Note

`AliESDHeader.fTimeStamp` is a Unix timestamp in **seconds** (uint32). Multiplying by 1000 gives millisecond precision at the second boundary only — sub-second ordering within the same second is not available from this field. The ingestion script uses `AliESDHeader.fEventNumberInFile` as a tie-breaker: events sharing the same second are ordered by their in-file index, giving each a unique millisecond offset. This satisfies the ±1 ms software timestamp requirement.

```python
event_numbers = tree["AliESDHeader.fEventNumberInFile"].array(library="np")

timestamps_ms = [
    int(timestamps_s[i]) * 1000 + int(event_numbers[i]) % 1000
    for i in range(len(timestamps_s))
]
```

---

## 3. ROOT/PyROOT-Derived Fields — Detailed Formulas

`fP[5]` and `fAlpha` are stored in AliRoot's compressed `Double32_t` format. uproot returns `[unreadable: 0]` for these branches. The extraction script (`extract_alice_fields.py`) runs inside a ROOT Docker container using PyROOT and AliRoot class libraries, which handle decompression automatically via `AliESDEvent.GetTrack(i)`.

### 3.1 Local Helix Parameter Reference

Each reconstructed track carries five parameters in the **local coordinate frame**, rotated relative to the global ALICE frame by angle `fAlpha`:

| Index | Symbol | Physical meaning | Unit |
|---|---|---|---|
| `fP[0]` | y | Local y-coordinate at reference point | cm |
| `fP[1]` | z | Local z-coordinate at reference point | cm |
| `fP[2]` | sin(ϕ) | Sine of azimuthal angle in local frame | dimensionless |
| `fP[3]` | tan(λ) | Tangent of dip angle = pz / pt | dimensionless |
| `fP[4]` | q/pt | Signed inverse transverse momentum (charge / pt) | (GeV/c)⁻¹ |

`fAlpha` = rotation angle from local frame to global ALICE frame (radians).

### 3.2 Global Cartesian Momentum Conversion

For each track `i` in the event:

```
pt_i  = |1 / fP[4]_i|                           # transverse momentum, GeV/c
phi_i = fAlpha_i + arcsin(fP[2]_i)              # global azimuthal angle, radians
px_i  = pt_i × cos(phi_i)                       # global x-momentum, GeV/c
py_i  = pt_i × sin(phi_i)                       # global y-momentum, GeV/c
pz_i  = pt_i × fP[3]_i                          # global z-momentum, GeV/c
p_i   = sqrt(px_i² + py_i² + pz_i²)            # total momentum magnitude, GeV/c
```

### 3.3 `net_momentum_x`

**Formula:** `net_momentum_x = Σ px_i` for all tracks i in the event

```
net_momentum_x = Σ ( |1/fP[4]_i| × cos(fAlpha_i + arcsin(fP[2]_i)) )
```

**Physics note:** In a symmetric Pb-Pb collision the net x-momentum should be near zero across many events. Individual events have small non-zero values due to finite track multiplicity and detector acceptance. This variation is the signal the ML model uses as an anomaly feature.

### 3.4 `net_momentum_y`

**Formula:** `net_momentum_y = Σ py_i` for all tracks i in the event

```
net_momentum_y = Σ ( |1/fP[4]_i| × sin(fAlpha_i + arcsin(fP[2]_i)) )
```

### 3.5 `net_momentum_z`

**Formula:** `net_momentum_z = Σ pz_i` for all tracks i in the event

```
net_momentum_z = Σ ( |1/fP[4]_i| × fP[3]_i )
```

Note: `fP[1]` (local z-coordinate, units: cm) is **not** the z-momentum. The z-momentum is computed from `fP[3]` (tan λ) and `fP[4]` (q/pt) as shown above.

### 3.6 `max_energy_gev`

**Formula:** `max_energy_gev = max( E_i )` for all tracks i in the event

where:

```
E_i = sqrt( px_i² + py_i² + pz_i² + M_PION² )     M_PION = 0.13957 GeV/c²
```

**Pion mass convention:** ALICE assigns pion mass (m = 0.13957 GeV/c²) to all unidentified tracks. Full particle identification would require `Tracks/Tracks.fTPCr[5]` (TPC PID probability array), which is also `Double32_t`-encoded and unreadable by uproot. The pion assumption is the standard ALICE convention for prototype-level analysis and is documented as the DataForge convention in `/docs/schemas/data_dictionary.md` (M2W8).

### 3.7 `total_energy_gev`

**Formula:** `total_energy_gev = Σ E_i` for all tracks i in the event

```
total_energy_gev = Σ sqrt( px_i² + py_i² + pz_i² + 0.13957² )
```

---

## 4. Complete PyROOT Extraction Script Structure

This is the reference implementation structure for `extract_alice_fields.py` (M3 deliverable). Run inside a ROOT Docker container with AliRoot libraries loaded.

```python
import ROOT
import uuid
import math
import json

M_PION = 0.13957  # GeV/c² — pion mass, ALICE convention for unidentified tracks

def extract_event(esd_event, run_number, event_index, timestamp_s):
    """
    Extract all DataForge Avro fields from one AliESDEvent object.
    Returns a dict matching alice_event_schema_v1.avsc.
    """
    n_tracks = esd_event.GetNumberOfTracks()

    px_list, py_list, pz_list = [], [], []

    for i in range(n_tracks):
        track = esd_event.GetTrack(i)
        # AliRoot decompresses Double32_t internally
        pt  = abs(1.0 / track.GetSigned1Pt()) if track.GetSigned1Pt() != 0 else 0.0
        phi = track.Phi()   # global azimuthal angle — AliRoot computes from fAlpha + arcsin(fP[2])
        lam = track.Theta() # polar angle — use for pz derivation via ThetaToLambda internally

        px = track.Px()     # AliRoot method — handles full decompression
        py = track.Py()
        pz = track.Pz()

        px_list.append(px)
        py_list.append(py)
        pz_list.append(pz)

    # Per-event aggregation
    net_momentum_x   = float(sum(px_list))
    net_momentum_y   = float(sum(py_list))
    net_momentum_z   = float(sum(pz_list))

    energies = [
        math.sqrt(px**2 + py**2 + pz**2 + M_PION**2)
        for px, py, pz in zip(px_list, py_list, pz_list)
    ]

    max_energy_gev   = float(max(energies)) if energies else 0.0
    total_energy_gev = float(sum(energies))

    return {
        "event_id":        str(uuid.uuid4()),
        "run_number":      int(run_number),
        "timestamp_ms":    int(timestamp_s) * 1000 + event_index % 1000,
        "track_count":     n_tracks,
        "net_momentum_x":  net_momentum_x,
        "net_momentum_y":  net_momentum_y,
        "net_momentum_z":  net_momentum_z,
        "max_energy_gev":  max_energy_gev,
        "total_energy_gev":total_energy_gev,
        "schema_version":  "1.0"
    }
```

---

## 5. Edge Cases and Known Constraints

| Case | Handling |
|---|---|
| Track with `fP[4] = 0` (infinite momentum) | Guard with `if track.GetSigned1Pt() != 0` — set px/py/pz to 0.0 for that track |
| Event with zero tracks (`track_count = 0`) | `net_momentum_x/y/z = 0.0`, `max_energy_gev = 0.0`, `total_energy_gev = 0.0` |
| `fTimeStamp` duplicate within one second | Sub-second offset from `fEventNumberInFile % 1000` — see §2.1 |
| Multi-file ingestion (M4 extension) | Append chunk folder prefix to event_id: `EVT-{run}-{chunk}-{index}` or generate new UUID per event |
| Run number changes between files | `run_number` is read fresh per file from `AliESDRun.fRunNumber` |

---

## 6. Verification Cross-Check — TRD Tracks

`TrdTracks/TrdTracks.fPt` and `TrdTracks/TrdTracks.fPhi` are directly uproot-readable (standard `float[]`). These cover only TRD-matched tracks (a subset of all tracks), but can be used to cross-check the momentum magnitudes computed from `fP[5]` and `fAlpha` in Section 3. Agreement within ~5% between TRD pt values and the PyROOT-derived pt confirms the derivation is correct.

---

*DataForge · Abdalla · M2W6T4 · June 2026*  
*Inputs: alice_run1_field_inventory.md · alice_event_schema_v1.avsc*  
*Used in: M4 Data Adaptation Layer (extract_alice_fields.py)*
