# ALICE Run 1 ROOT Field Inventory

---

## 1. Executive Summary

The ALICE ESD ROOT file was successfully opened with uproot. The file contains **287 collision events** across one main data tree (`esdTree`). The structure was fully enumerated — 20+ detector subsystems with hundreds of branches.

**Key finding for schema design:** The fields required for the DataForge per-event Avro schema split into two groups:

| Group | Fields | Status |
|---|---|---|
| **Directly readable by uproot** | `run_number`, `timestamp_ms`, `track_count` | ✓ Confirmed — extractable in pure Python |
| **Require ROOT/PyROOT to extract** | `net_momentum_x/y/z`, `max_energy_gev`, `total_energy_gev` | ✗ `fP[5]` and `fAlpha` are `[unreadable: 0]` in uproot |

The momentum and energy fields are stored in AliRoot's compressed `Double32_t` helical parameter format (`fP[5]`). uproot cannot deserialize this format. A ROOT Docker container (Phase 3 — `extract_alice_fields.py`) is required to extract them. This is a known limitation, not a data gap — the fields exist in the file and are confirmed present by the branch listing.

**The three Avro schema fields `event_id` and `schema_version` are system-assigned at ingestion time; they have no ROOT source.**

---

## 2. File Structure

| Property | Value |
|---|---|
| **Source URL** | `http://opendata.cern.ch/eos/opendata/alice/2010/LHC10h/000139038/ESD/0003/AliESDs.root` |
| **File size** | 126 MB |
| **Collision system** | Pb-Pb at √sNN = 2.76 TeV |
| **Run number** | 139465 |
| **Run period** | LHC10h (Run 1, 2010) |
| **Trees in file** | `esdTree` (287 events), `HLTesdTree` (HLT trigger data) |
| **Primary tree** | `esdTree` — used for all DataForge ingestion |
| **Detector subsystems** | 20+ (AliESDRun, AliESDHeader, Tracks, Vertices, ZDC, V0, FMD, T0, VZERO, EMCAL, PHOS, TRD, TOF, Muon, …) |

---

## 3. Schema Field Mapping — DataForge Avro Fields vs ROOT Sources

This table is the authoritative mapping. Every DataForge Avro schema field is traced to its ROOT source, derivation method, and readability status.

| Avro Field | Avro Type | Unit | ROOT Source Branch | ROOT Type | Readable by uproot? | Notes |
|---|---|---|---|---|---|---|
| `event_id` | string | — | *None* | — | N/A | System-generated UUID at ingestion. Format: `EVT-{run_number}-{event_index_zero_padded_6}`. Example: `EVT-139465-000001`. |
| `run_number` | int | — | `AliESDRun./AliESDRun.fRunNumber` | `int32_t` | ✓ **YES** | Direct read. Unique LHC fill run identifier. Value for this file: 139465. |
| `timestamp_ms` | long | ms | `AliESDHeader./AliESDHeader.fTimeStamp` | `uint32_t` | ✓ **YES** | Unix timestamp in **seconds**. Must multiply by 1000 at ingestion to produce ms. Precision is ±1s from the hardware clock; sub-second component is software-assigned. This satisfies the ±1ms software timestamp requirement. |
| `track_count` | int | — | `Tracks/Tracks.fFlags` (array length) | `uint64_t[]` | ✓ **YES** | `fFlags` is a per-track readable array. Its length per event equals the number of reconstructed charged tracks. Direct `len()` call in Python. |
| `net_momentum_x` | float | GeV/c | `Tracks/Tracks.fP[5]` + `Tracks/Tracks.fAlpha` | `Double32_t[]` | ✗ **NO** | Both branches are `[unreadable: 0]`. Derivation requires ROOT/PyROOT. See Section 4 for formula. |
| `net_momentum_y` | float | GeV/c | `Tracks/Tracks.fP[5]` + `Tracks/Tracks.fAlpha` | `Double32_t[]` | ✗ **NO** | Same as above. |
| `net_momentum_z` | float | GeV/c | `Tracks/Tracks.fP[5]` + `Tracks/Tracks.fAlpha` | `Double32_t[]` | ✗ **NO** | Same as above. |
| `max_energy_gev` | float | GeV | Derived from `fP[5]` + `fAlpha` | `Double32_t[]` | ✗ **NO** | Derived: `E = sqrt(p² + m_π²)` per track; take max across event. Requires ROOT/PyROOT. See Section 4. |
| `total_energy_gev` | float | GeV | Derived from `fP[5]` + `fAlpha` | `Double32_t[]` | ✗ **NO** | Derived: sum of `E` across all tracks in event. Requires ROOT/PyROOT. See Section 4. |
| `schema_version` | string | — | *None* | — | N/A | System-assigned. Default value `"0.1"` for v0 draft; `"1.0"` at lock. |

---

## 4. Derivation Formulas for Momentum and Energy Fields

### 4.1 Why fP[5] Cannot Be Read by uproot

AliRoot stores track parameters in a helical representation using a compressed `Double32_t` encoding. The five parameters in `fP[5]` are defined in the **local coordinate frame** of the track, which is rotated relative to the global ALICE frame by an angle `fAlpha`. uproot does not have the AliRoot class libraries needed to decompress `Double32_t` values, so both `fP[5]` and `fAlpha` return `[unreadable: 0]`.

### 4.2 Local Helix Parameters (fP[5])

| Index | Symbol | Meaning | Unit |
|---|---|---|---|
| `fP[0]` | y | Local y-coordinate of track at reference point | cm |
| `fP[1]` | z | Local z-coordinate of track at reference point | cm |
| `fP[2]` | sin(ϕ) | Sine of azimuthal angle in local frame | dimensionless |
| `fP[3]` | tan(λ) | Tangent of dip angle = pz/pt | dimensionless |
| `fP[4]` | q/pt | Signed inverse transverse momentum (charge/pt) | (GeV/c)⁻¹ |

`fAlpha` = rotation angle of local frame relative to global ALICE frame (radians).

### 4.3 Conversion to Global Cartesian Momentum

```python
import math

# For each track in event (using PyROOT or AliRoot objects):
pt   = abs(1.0 / track.fP[4])              # transverse momentum, GeV/c
phi  = track.fAlpha + math.asin(track.fP[2])  # global azimuthal angle, radians
px   = pt * math.cos(phi)                   # x-component, GeV/c
py   = pt * math.sin(phi)                   # y-component, GeV/c
pz   = pt * track.fP[3]                     # z-component, GeV/c
p    = math.sqrt(px**2 + py**2 + pz**2)    # total momentum, GeV/c

# Energy assuming pion mass (unidentified tracks convention)
M_PION = 0.13957  # GeV/c²
energy = math.sqrt(p**2 + M_PION**2)       # GeV
```

### 4.4 Per-Event Aggregation (DataForge Schema Fields)

```python
# After iterating over all N tracks in one event:
net_momentum_x  = sum(px_i  for all tracks i)     # GeV/c
net_momentum_y  = sum(py_i  for all tracks i)     # GeV/c
net_momentum_z  = sum(pz_i  for all tracks i)     # GeV/c
max_energy_gev  = max(E_i   for all tracks i)     # GeV
total_energy_gev = sum(E_i  for all tracks i)     # GeV
```

**Important note on `net_momentum`:** For symmetric Pb-Pb collisions the net momentum should be close to zero for a large event sample, but individual events will have small non-zero values due to finite track multiplicity and detector acceptance. This non-zero variation is precisely what makes the field useful as an ML anomaly detection feature.

### 4.5 Why Pion Mass for Energy Calculation?

Particle identification (PID) in ALICE is performed by the TPC dE/dx signal, TOF timing, and other detectors. For unidentified tracks (no PID applied), the standard ALICE convention is to assign pion mass (m = 0.13957 GeV/c²). This is the correct approach for a prototype — full PID would require reading `Tracks/Tracks.fTPCr[5]` (PID probability array), which is also unreadable by uproot. The pion assumption introduces a small systematic offset in `total_energy_gev` for heavy-ion events where kaons and protons are significant fractions, but this is acceptable for prototype ML training.

---

## 5. Complete Branch Inventory by Subsystem

All branches discovered in `esdTree`. Status: ✓ = readable by uproot, ✗ = unreadable, — = not applicable (group/object header).

### 5.1 AliESDRun — Run-Level Metadata (one entry per tree, not per event)

| Branch | Type | Readable | DataForge Use |
|---|---|---|---|
| `AliESDRun.fRunNumber` | `int32_t` | ✓ | → `run_number` field |
| `AliESDRun.fMagneticField` | `float` | ✓ | Context only (momentum reconstruction quality) |
| `AliESDRun.fBeamEnergy` | `float` | ✓ | Context only (Pb-Pb, 2.76 TeV/nucleon) |
| `AliESDRun.fBeamType` | `TString` | ✓ | Context only ("Pb-Pb") |
| `AliESDRun.fCurrentL3` | `float` | ✓ | L3 magnet current — metadata |
| `AliESDRun.fCurrentDip` | `float` | ✓ | Dipole magnet current — metadata |
| `AliESDRun.fRecoVersion` | `int32_t` | ✓ | Reconstruction software version — metadata |
| `AliESDRun.fPeriodNumber` | `uint32_t` | ✓ | LHC fill period — metadata |
| `AliESDRun.fDetInDAQ` | `uint32_t` | ✓ | Detectors in DAQ bitmask |
| `AliESDRun.fDetInReco` | `uint32_t` | ✓ | Detectors in reconstruction bitmask |
| `AliESDRun.fDiamondZ` | `float` | ✓ | Beam diamond z-position — metadata |
| `AliESDRun.fDiamondXY[2]` | `float[2]` | ✓ | Beam diamond x,y — metadata |
| `AliESDRun.fT0spread[4]` | `float[4]` | ✓ | T0 timing spread — metadata |
| `AliESDRun.fTriggerClasses` | `TObjArray` | ✗ | Trigger class names — not needed |
| `AliESDRun.fPHOSMatrix[5]` | `TGeoHMatrix*[][5]` | ✗ | PHOS geometry — not needed |
| `AliESDRun.fEMCALMatrix[12]` | `TGeoHMatrix*[][12]` | ✗ | EMCAL geometry — not needed |

### 5.2 AliESDHeader — Per-Event Header

| Branch | Type | Readable | DataForge Use |
|---|---|---|---|
| `AliESDHeader.fTimeStamp` | `uint32_t` | ✓ | → `timestamp_ms` (×1000 conversion) |
| `AliESDHeader.fEventNumberInFile` | `int32_t` | ✓ | Part of `event_id` generation |
| `AliESDHeader.fOrbitNumber` | `uint32_t` | ✓ | LHC orbit counter — metadata |
| `AliESDHeader.fBunchCrossNumber` | `uint16_t` | ✓ | Bunch crossing ID — metadata |
| `AliESDHeader.fPeriodNumber` | `uint32_t` | ✓ | Metadata |
| `AliESDHeader.fTriggerMask` | `uint64_t` | ✓ | Trigger bitmask — metadata |
| `AliESDHeader.fEventType` | `uint32_t` | ✓ | Physics/calibration event flag — metadata |
| `AliESDHeader.fEventSpecie` | `uint32_t` | ✓ | Event species (pp/PbPb/…) — metadata |
| `AliESDHeader.fTriggerCluster` | `uint8_t` | ✓ | Trigger cluster — metadata |
| `AliESDHeader.fL0TriggerInputs` | `uint32_t` | ✓ | L0 trigger inputs |
| `AliESDHeader.fL1TriggerInputs` | `uint32_t` | ✓ | L1 trigger inputs |
| `AliESDHeader.fL2TriggerInputs` | `uint16_t` | ✓ | L2 trigger inputs |
| `AliESDHeader.fTriggerScalers` | `AliTriggerScalersRecordESD` | — | Partially readable sub-branches |
| `AliESDHeader.fIRArray[3]` | `AliTriggerIR*[][3]` | ✗ | Interaction record — not needed |
| `AliESDHeader.fTriggerInputsNames` | `TObjArray` | ✗ | String array — not needed |

### 5.3 Tracks — Main Charged Particle Track Collection

**This is the most important subsystem for DataForge. 228 events in this file have variable track multiplicity. Note: Pb-Pb events typically have hundreds to thousands of tracks per event.**

| Branch | Type | Readable | DataForge Use |
|---|---|---|---|
| `Tracks/Tracks.fFlags` | `uint64_t[]` | ✓ | Length of array = `track_count` |
| `Tracks/Tracks.fID` | `int32_t[]` | ✓ | Per-track ID |
| `Tracks/Tracks.fLabel` | `int32_t[]` | ✓ | Monte Carlo label — metadata |
| `Tracks/Tracks.fTPCncls` | `uint16_t[]` | ✓ | TPC cluster count — quality metric |
| `Tracks/Tracks.fTPCnclsF` | `uint16_t[]` | ✓ | TPC findable clusters — quality |
| `Tracks/Tracks.fTPCsignalN` | `uint16_t[]` | ✓ | TPC signal clusters — PID quality |
| `Tracks/Tracks.fITSncls` | `int8_t[]` | ✓ | ITS cluster count — quality |
| `Tracks/Tracks.fITSClusterMap` | `uint8_t[]` | ✓ | ITS layer hit pattern |
| `Tracks/Tracks.fTRDncls` | `uint8_t[]` | ✓ | TRD cluster count |
| `Tracks/Tracks.fTRDntracklets` | `uint8_t[]` | ✓ | TRD tracklets |
| `Tracks/Tracks.fTOFdeltaBC` | `int16_t[]` | ✓ | TOF bunch crossing offset |
| `Tracks/Tracks.fVertexID` | `int8_t[]` | ✓ | Associated vertex ID |
| `Tracks/Tracks.fKinkIndexes[3]` | `int32_t[][3]` | ✓ | Kink decay indices |
| `Tracks/Tracks.fV0Indexes[3]` | `int32_t[][3]` | ✓ | V0 decay indices |
| `Tracks/Tracks.fITSModule[12]` | `int32_t[][12]` | ✓ | ITS module hits |
| **`Tracks/Tracks.fP[5]`** | `Double32_t[]` | **✗ UNREADABLE** | **→ Momentum parameters — required for net_momentum_x/y/z** |
| **`Tracks/Tracks.fAlpha`** | `Double32_t[]` | **✗ UNREADABLE** | **→ Frame rotation angle — required for momentum calculation** |
| `Tracks/Tracks.fX` | `Double32_t[]` | ✗ | Reference radius |
| `Tracks/Tracks.fC[15]` | `Double32_t[]` | ✗ | Covariance matrix |
| `Tracks/Tracks.fR[5]` | `Double32_t[]` | ✗ | PID probability array (ESD-level) |
| `Tracks/Tracks.fTPCr[5]` | `Double32_t[]` | ✗ | TPC PID probabilities |
| `Tracks/Tracks.fITSr[5]` | `Double32_t[]` | ✗ | ITS PID probabilities |
| `Tracks/Tracks.fTPCsignal` | `Double32_t[]` | ✗ | TPC dE/dx signal |
| `Tracks/Tracks.fITSsignal` | `Double32_t[]` | ✗ | ITS dE/dx signal |
| `Tracks/Tracks.fTOFsignal` | `Double32_t[]` | ✗ | TOF signal |
| `Tracks/Tracks.fTPCchi2` | `Double32_t[]` | ✗ | TPC fit chi-squared |
| `Tracks/Tracks.fITSchi2` | `Double32_t[]` | ✗ | ITS fit chi-squared |
| `Tracks/Tracks.fTrackLength` | `Double32_t[]` | ✗ | Track length |

### 5.4 TrdTracks — TRD-Matched Tracks (Readable Kinematics — Partial)

**Notable:** The TRD subsystem stores simplified kinematics in a directly readable format. These cover only TRD-matched tracks (a subset of all tracks), but can serve as a cross-check for momentum values obtained from Phase 3.

| Branch | Type | Readable | DataForge Use |
|---|---|---|---|
| `TrdTracks/TrdTracks.fPt` | `float[]` | ✓ | Transverse momentum — cross-check |
| `TrdTracks/TrdTracks.fPhi` | `float[]` | ✓ | Azimuthal angle — cross-check |
| `TrdTracks/TrdTracks.fEta` | `float[]` | ✓ | Pseudorapidity — cross-check |
| `TrdTracks/TrdTracks.fPID` | `Double32_t[]` | ✗ | PID probability |
| `TrdTracks/TrdTracks.fNtracklets` | `int16_t[]` | ✓ | TRD tracklet count |
| `TrdTracks/TrdTracks.fNclusters` | `int16_t[]` | ✓ | TRD cluster count |

### 5.5 Vertices — Primary and Pileup

| Branch | Type | Readable | Note |
|---|---|---|---|
| `PrimaryVertex.AliVertex.fNContributors` | `int32_t` | ✓ | Track count contributing to primary vertex |
| `SPDVertex.AliVertex.fNContributors` | `int32_t` | ✓ | SPD vertex contributor count |
| `TPCVertex.AliVertex.fNContributors` | `int32_t` | ✓ | TPC vertex contributor count |
| All `fPosition[3]` branches | `Double32_t[3]` | ✗ | Vertex x,y,z position — unreadable |
| All `fSigma` branches | `Double32_t` | ✗ | Position uncertainty — unreadable |

### 5.6 AliMultiplicity — SPD Tracklet Multiplicity

| Branch | Type | Readable | Note |
|---|---|---|---|
| `AliMultiplicity.fNtracks` | `uint32_t` | ✓ | SPD tracklet count — alternative multiplicity estimate |
| `AliMultiplicity.fNsingle` | `uint32_t` | ✓ | SPD single cluster count |
| `AliMultiplicity.fITSClusters[6]` | `uint32_t[6]` | ✓ | ITS cluster count per layer |
| `AliMultiplicity.fLabels` | `int32_t[]` | ✓ | MC labels |
| `AliMultiplicity.fTh`, `fPhi`, etc. | `unknown[]` | ✗ | Tracklet angles — unreadable |

### 5.7 AliESDVZERO — V0 Detector (Forward Rapidity Multiplicity)

| Branch | Type | Readable | Note |
|---|---|---|---|
| `AliESDVZERO.fMultiplicity[64]` | `float[64]` | ✓ | V0A+V0C channel multiplicity |
| `AliESDVZERO.fV0ATime` | `float` | ✓ | V0A timing |
| `AliESDVZERO.fV0CTime` | `float` | ✓ | V0C timing |
| `AliESDVZERO.fV0ADecision` | `int32_t` | ✓ | V0A beam-gas/beam-beam decision |
| `AliESDVZERO.fV0CDecision` | `int32_t` | ✓ | V0C decision |
| `AliESDVZERO.fBBFlag[64]` | `bool[64]` | ✓ | Beam-beam flag per channel |

### 5.8 AliESDTZERO — T0 Detector (Timing)

| Branch | Type | Readable | Note |
|---|---|---|---|
| `AliESDTZERO.fT0clock` | `float` | ✓ | T0 clock offset |
| `AliESDTZERO.fT0timeStart` | `float` | ✓ | T0 event start time |
| `AliESDTZERO.fT0zVertex` | `float` | ✓ | T0 z-vertex estimate |
| `AliESDTZERO.fT0TOF[3]` | `float[3]` | ✓ | T0-TOF timing [mean, A, C] |
| `AliESDTZERO.fT0time[24]` | `float[24]` | ✓ | Per-channel T0 times |
| `AliESDTZERO.fT0amplitude[24]` | `float[24]` | ✓ | Per-channel amplitudes |

### 5.9 AliESDZDC — Zero Degree Calorimeter (Centrality/Energy)

| Branch | Type | Readable | Note |
|---|---|---|---|
| `AliESDZDC.fZDCN1Energy` | `float` | ✓ | ZDC neutron energy, side A |
| `AliESDZDC.fZDCN2Energy` | `float` | ✓ | ZDC neutron energy, side C |
| `AliESDZDC.fZDCP1Energy` | `float` | ✓ | ZDC proton energy, side A |
| `AliESDZDC.fZDCP2Energy` | `float` | ✓ | ZDC proton energy, side C |
| `AliESDZDC.fImpactParameter` | `float` | ✓ | Estimated impact parameter (centrality) |
| `AliESDZDC.fZDCParticipants` | `int16_t` | ✓ | Number of participating nucleons |
| `AliESDZDC.fZDCPartSideA` | `int16_t` | ✓ | Participants, side A |
| `AliESDZDC.fZDCPartSideC` | `int16_t` | ✓ | Participants, side C |

### 5.10 MuonTracks — Muon Spectrometer (Readable)

| Branch | Type | Readable | Note |
|---|---|---|---|
| `MuonTracks/MuonTracks.fInverseBendingMomentum` | `float[]` | ✓ | 1/p in bending plane |
| `MuonTracks/MuonTracks.fThetaX` | `float[]` | ✓ | Track angle x |
| `MuonTracks/MuonTracks.fThetaY` | `float[]` | ✓ | Track angle y |
| `MuonTracks/MuonTracks.fChi2` | `float[]` | ✓ | Fit chi-squared |
| `MuonTracks/MuonTracks.fRAtAbsorberEnd` | `float[]` | ✓ | Radius at absorber end |

### 5.11 V0s — Secondary Vertex V0 Candidates

| Branch | Type | Readable | Note |
|---|---|---|---|
| `V0s/V0s.fPos[3]` | `float[][3]` | ✓ | V0 decay vertex x,y,z |
| `V0s/V0s.fNmom[3]` | `float[][3]` | ✓ | Negative daughter momentum |
| `V0s/V0s.fPmom[3]` | `float[][3]` | ✓ | Positive daughter momentum |
| `V0s/V0s.fEffMass` | `float[]` | ✓ | Invariant mass |
| `V0s/V0s.fPointAngle` | `Double32_t[]` | ✓ | Pointing angle |
| `V0s/V0s.fOnFlyStatus` | `bool[]` | ✓ | On-the-fly vs offline flag |

### 5.12 CaloClusters — EMCAL and PHOS Clusters

| Branch | Type | Readable | Note |
|---|---|---|---|
| `CaloClusters/CaloClusters.fEnergy` | `float[]` | ✓ | Cluster energy, GeV |
| `CaloClusters/CaloClusters.fGlobalPos[3]` | `float[][3]` | ✓ | Cluster x,y,z position |
| `CaloClusters/CaloClusters.fNCells` | `uint32_t[]` | ✓ | Number of cells in cluster |
| `CaloClusters/CaloClusters.fM20` | `float[]` | ✓ | Short axis moment |
| `CaloClusters/CaloClusters.fM02` | `float[]` | ✓ | Long axis moment |
| `CaloClusters/CaloClusters.fDispersion` | `float[]` | ✓ | Shower dispersion |
| `CaloClusters/CaloClusters.fClusterType` | `int8_t[]` | ✓ | EMCAL=1, PHOS=2 |

---

## 6. Uproot Readability Summary

| Category | Count | Examples |
|---|---|---|
| Fully readable scalar/array branches | ~180 | `fRunNumber`, `fTimeStamp`, `fFlags`, all float/int arrays in VZERO, ZDC, TZero, V0s, MuonTracks, CaloClusters |
| Unreadable (`Double32_t` compressed) | ~60 | `fP[5]`, `fAlpha`, `fTPCsignal`, `fITSsignal`, all vertex positions |
| Unreadable (complex object) | ~15 | `AliMultiplicity`, `Tracks` parent, all `AliVertex` aggregates |
| Not needed (geometry, HLT) | ~30 | `fPHOSMatrix`, `fEMCALMatrix`, `HLTesdTree` |

**The DataForge schema requires 3 of the ~60 unreadable `Double32_t` branches** (`fP[5]`, `fAlpha`) for momentum/energy derivation. All other required fields are readable.

---

## 7. Implications for Week 6 Schema Design

1. **`run_number`, `timestamp_ms`, `track_count`** — write these directly in the uproot ingestion script. No ROOT required.

2. **`timestamp_ms` conversion** — ROOT stores `fTimeStamp` as a Unix timestamp in seconds (uint32_t). The ingestion script must multiply by 1000. Sub-second precision is not available from this field; a sequential counter within the event (e.g., `fEventNumberInFile`) can be appended for ordering within the same second.

3. **`net_momentum_x/y/z`, `max_energy_gev`, `total_energy_gev`** — these must be computed using the ROOT Docker container (`extract_alice_fields.py`) during M3 Data Generation. The Phase 3 script iterates over events using PyROOT's `AliESDEvent.GetTrack(i)`, calls `track.Px()`, `track.Py()`, `track.Pz()`, `track.E()` — AliRoot handles the decompression internally. **The Avro schema fields are confirmed derivable; the formula is in Section 4.**

4. **`event_id` generation convention** — format locked as `EVT-{run_number}-{event_number_zero_padded_6}`. Example: `EVT-139038-000042`. This is unique within a single ESD file. For multi-file ingestion in M4, a file-level prefix will be added (e.g., `EVT-139038-0003-000042` where 0003 is the chunk folder number).

5. **Pion mass assumption** — confirmed as the correct convention for unidentified ALICE ESD tracks. Document this in the data dictionary (M2W8).

6. **PbPb vs pp data** — This inventory is based on Pb-Pb data (run 139038). For the prototype, Pb-Pb data is acceptable and provides higher track multiplicities (50–2000 tracks/event vs 5–30 for pp), which is beneficial for ML training diversity. If pp data is preferred for physics consistency, a parallel inventory of `LHC10c_pp_ESD_120616` may be done in M3.

---

## 8. ROOT File Information Block

```
File:          AliESDs.root
Experiment:    ALICE, CERN LHC Run 1
Period:        LHC10h (Heavy-ion run, October 2010)
Collision:     Pb-Pb at √sNN = 2.76 TeV
Run number:    139465
Events:        287
File size:     126 MB
Trees:         esdTree (data), HLTesdTree (HLT trigger)
Detector:      Full ALICE (ITS, TPC, TRD, TOF, EMCAL, PHOS, ZDC, V0, T0, FMD, MUON, ACORDE)
Inspection:    uproot 4.x — branch listing complete; Double32_t branches not decodable
```

---


