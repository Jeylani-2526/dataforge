# DataForge — CERN Open Data Exploration Notes




## Q1 — Which datasets are available, what sizes?

The portal lists ALICE primary datasets at: [opendata.cern.ch/search?experiment=ALICE&type=Dataset](https://opendata.cern.ch/search?experiment=ALICE&type=Dataset)

After applying the ALICE experiment filter, ~10 primary datasets visible — split between pp (LHC10c period, 7 TeV) and PbPb (LHC10h period, 2.76 TeV) from 2010.

### Recommended candidate datasets (2010 Run 1, ESD format)

| Record | Period | Collision | Run # | Events | Files | Total size |
|---|---|---|---|---|---|---|
| [1102](https://opendata.cern.ch/record/1102) | LHC10h | PbPb 2.76 TeV | 139038 | TBC | ~5000 | ~1.3 TiB |
| [1106](https://opendata.cern.ch/record/1106) | LHC10h | PbPb 2.76 TeV | 139465 | **1,076,914** | **5,062** | **1.3 TiB** |
| (others) | LHC10h | PbPb | 139437, 139438, 139173 | similar | similar | similar |
| (others) | LHC10c | pp 7 TeV | 120822, 120616, 120505, 120244, 120076 | TBC | TBC | TBC |

**DOI for record 1106:** `10.7483/OPENDATA.ALICE.QBG8.J7GZ`

**For our 1–5 GB target subset:** Download a **single file** from a dataset, not the entire record. Each individual ESD file is roughly **125–280 MiB** — perfect prototype size.

**Concrete file we downloaded:**
- Source: record 1106 → "List files" → smallest file (page 1, file 1)
- Size: **132,690,635 bytes = 126.5 MiB**
- Provenance: `https://opendata.cern.ch` (browser download)

**Recommended starter sample for the prototype:** 1 PbPb file (~126 MiB, this file) + 1 pp file from LHC10c (~150–250 MiB, TBC) = ~300–400 MiB total. Enough events to test end-to-end pipeline without flooding our laptops.

---

## Q2 — What file format?

**Format:** ROOT, specifically the ALICE-specific **ESD (Event Summary Data)** layout.

- File extension: `.root` (single file format)
- Binary, columnar, compressed
- Tree-based: each ROOT file contains one or more *TTrees*
- **Two trees observed in our test file:**
  - `esdTree` — main ALICE event-summary tree (707 branches, 287 events in this 126.5 MiB file)
  - `HLTesdTree` — High-Level Trigger ESD tree (online reconstruction output)
- Each entry in `esdTree` = one collision event
- Contents per event: list of reconstructed tracks (with momentum, position), calorimeter clusters (with energy), vertex info, trigger info, plus event-level metadata (timestamp, run number)

**Not human-readable without a library.** Excel / text editors cannot open `.root` files.

Format reference: [ROOT format docs](https://root.cern.ch/doc/v608/alice__esd_8C.html) · [About ALICE Data](https://opendata.cern.ch/docs/about-alice)

---

## Q3 — What fields are present? (Mapping to Abdullah's Module 1 schema)

**Critical insight from inspection:** ALICE ESD is **not a flat tree** — it is a serialized C++ object hierarchy. Fields like `fRunNumber` are not accessible at the tree root; they live at nested paths.

### Top-level branch families observed (first 30 of 707 branches)

| Branch family | Contains |
|---|---|
| `AliESDRun.` | Run-level metadata (beam energy, magnetic field, run/period number, beam type, trigger classes, detector activation, EMCal/PHOS calibration matrices, T0 spread) |
| `AliESDHeader.` | Event-level header (event name, trigger info, timestamp — nested inside `AliVHeader.TNamed.TObject`) |
| `AliESDtracks` (likely) | Reconstructed particle tracks (collection per event) |
| `AliESDcaloClusters` (likely) | Calorimeter clusters |
| `AliESDvertices` (likely) | Reconstructed vertices |

### Abdullah's Module 1 schema mapping (ESD path TBC)

| Abdullah's field | Likely ESD path | Status |
|---|---|---|
| `event_id` | Synthesized: `f"{fRunNumber}-{fPeriodNumber}-{fEventNumberInFile}"` | TBC — ALICE has no native UUID |
| `timestamp_ms` | `AliESDHeader./AliESDHeader.fTimeStamp` (likely) | Verify in next inspection pass |
| `position_x` | `AliESDvertices.fPosition[0]` (primary vertex) | Verify |
| `position_y` | `AliESDvertices.fPosition[1]` | Verify |
| `position_z` | `AliESDvertices.fPosition[2]` | Verify |
| `momentum_x` | `AliESDtracks.fP[0]` (per track) | Verify |
| `momentum_y` | `AliESDtracks.fP[1]` (per track) | Verify |
| `momentum_z` | `AliESDtracks.fP[2]` (per track) | Verify |
| `energy_gev` | `AliESDcaloClusters.fE` (per cluster) | Verify |
| `source_type` | Synthesized constant `"alice"` | Per Abdullah's spec |

**Important:** ESD has many more fields than Module 1 needs (full detector hit list, particle identification, trigger details). The Module 3 (Data Adaptation) script will be a **field-selection + flattening** transform from ESD → Avro/Parquet.

---

## Q4 — Which Python library?

**Recommendation: `uproot` (confirmed working with ALICE ESD files).**

**Confirmed working installation (22 May 2026):**
- `uproot 5.7.4`
- `awkward 2.9.0`
- `numpy 2.4.6`
- `awkward_cpp 52`, `cramjam 2.11.0`, `fsspec 2026.4.0`, `packaging 26.2`, `xxhash 3.7.0` (transitive)
- Installed via: `pip install uproot awkward numpy` (used `--user` automatically on Windows)
- Environment: Python 3.12, Windows 10

**Why uproot, not PyROOT:** Pure Python, no C++ ROOT install needed (~30 MB package vs multi-GB ALICE VM); works on any OS; integrates cleanly with pandas/PySpark for our Module 3 pipeline.

**Trade-off:** uproot can READ ROOT files reliably; writing ROOT has limitations. For our use case (ROOT → Parquet conversion), we only read.

### Minimal verification snippet (tested and working)

```python
import uproot

with uproot.open("AliESDs.root") as f:
    # List all trees in the file
    print("Trees:", f.keys())  # ['esdTree;1', 'HLTesdTree;1']

    # Open the main ALICE tree
    tree = f["esdTree"]
    print("Total events:", tree.num_entries)  # 287 in our test file
    print("Total branches:", len(tree.keys()))  # 707
    print("First 20 branches:", tree.keys()[:20])
```

**Real output from our test file:**
```
Opening: AliESDs.root
============================================================
STEP 1 -- Top-level keys
============================================================
  esdTree;1
  HLTesdTree;1
============================================================
STEP 2 -- esdTree inspection
============================================================
Total events in this file: 287
Total branches in esdTree: 707
First 20 branch names:
  AliESDRun.
  AliESDRun./AliESDRun.TObject
  AliESDRun./AliESDRun.fCurrentL3
  AliESDRun./AliESDRun.fCurrentDip
  AliESDRun./AliESDRun.fBeamEnergy
  AliESDRun./AliESDRun.fMagneticField
  AliESDRun./AliESDRun.fMeanBeamInt[2][2]
  AliESDRun./AliESDRun.fDiamondXY[2]
  AliESDRun./AliESDRun.fDiamondCovXY[3]
  AliESDRun./AliESDRun.fPeriodNumber
  AliESDRun./AliESDRun.fRunNumber
  AliESDRun./AliESDRun.fBeamType
  AliESDRun./AliESDRun.fTriggerClasses
  ...
Done in 1.3 seconds.
```

### Library alternatives considered

| Library | Verdict |
|---|---|
| **uproot 5.7.4** | ✅ Recommended. Pure Python, fast, parse of 126.5 MiB file in 1.3 seconds. |
| PyROOT | ❌ Heavy — requires full ROOT C++ install (>1 GB). Overkill for our needs. |
| ALICE VM (CernVM with AliPhysics) | ❌ Massive (multi-GB VM image), only needed if we required the full ALICE analysis framework. We don't. Portal's "How to use these data?" section recommends VM — we explicitly bypass this for the prototype. |
| `cbourjau/alice-rs` (Rust) | ❌ Not our stack — but proves ALICE ESD can be analyzed without ALICE framework, validating uproot choice. |

References: [uproot docs](https://uproot.readthedocs.io/en/stable/basic.html) · [HSF uproot tutorial](https://hsf-training.github.io/hsf-training-uproot-webpage/03-trees/index.html) · [REANA ALICE demo](https://github.com/reanahub/reana-demo-alice-pt-analysis)

---

## Q5 — How long does downloading a sample take?

**Test method:** Downloaded a single ESD file from CERN's Open Data portal record 1106 (LHC10h_PbPb_ESD_139465) via the in-page Download button.

**Measured result (22 May 2026):**

| Metric | Value |
|---|---|
| File | `AliESDs.root` (one of 5062 files in record 1106) |
| Source record | https://opendata.cern.ch/record/1106 |
| File size (actual bytes) | **132,690,635 bytes** |
| File size (display) | **126.5 MiB** |
| Download channel | Browser (Chrome/Edge in-page Download button) |
| Connection speed at test | **3.5 Mbps** (fast.com, 22 May 2026) |
| Calculated download time | **~5–6 minutes** (1,061 Mbit / 3.5 Mbps theoretical = 303 s; actual with TCP/protocol overhead ≈ 5–7 min) |

CERN's EOS supports HTTP range requests, so resumable downloads work via `curl -C -` if interrupted. No login required for open data.

**Implication for prototype design:** At 3.5 Mbps, downloading the full 1.3 TiB record would take ~36 days non-stop. This confirms the single-file (or few-file) subset approach is the only realistic path for laptop-based prototype work. For team members on faster connections (e.g. 100 Mbps office connection), the same file would download in ~25 seconds — so during M5 implementation, bulk-prep on a faster connection then share via shared drive is recommended.

---

## Hands-On Walk-Through — Completed 22 May 2026

### What was done

1. ✅ Browsed CERN Open Data portal, filtered to ALICE experiment, located the 2010 ESD primary datasets (LHC10c pp + LHC10h PbPb).
2. ✅ Opened record 1106 (LHC10h_PbPb_ESD_139465, PbPb 2.76 TeV, 1,076,914 events, 5,062 files, 1.3 TiB total).
3. ✅ Downloaded one ESD file (126.5 MiB / 132,690,635 bytes) to local Desktop. ~5–6 min at 3.5 Mbps.
4. ✅ Installed Python packages: `uproot 5.7.4`, `awkward 2.9.0`, `numpy 2.4.6` (via `pip install --user`).
5. ✅ Ran the `inspect_esd.py` script on the downloaded file. Parse completed in 1.3 seconds.

### What the inspection revealed

**Two trees found at file root:**
- `esdTree;1` — main ALICE event-summary tree
- `HLTesdTree;1` — High-Level Trigger ESD tree (online reconstruction output)

**`esdTree` statistics (this 126.5 MiB file):**
- **Events: 287**
- **Branches: 707**

### Critical finding for Module 3 design

ALICE ESD is **not a flat tree** — it is a serialized C++ object hierarchy. Fields like `fRunNumber` are not accessible at the tree root; they live at nested paths such as:

```
AliESDRun./AliESDRun.fRunNumber
AliESDRun./AliESDRun.fPeriodNumber
AliESDRun./AliESDRun.fBeamEnergy
```

**Implication for Abdullah's `data_flow_spec.md` Module 3 (Data Adaptation):**
The spec describes Module 3 as a "format conversion" (ROOT → Avro/Parquet). In practice, it must also **flatten** the nested ESD object hierarchy into the unified flat schema (`event_id, source_type, timestamp_ms, energy_gev, momentum_x/y/z, ...`). This is an extra 50–100 lines of Python per source type:

```python
# Conceptual example — Module 3 flattening step
with uproot.open("AliESDs.root") as f:
    tree = f["esdTree"]
    arrays = tree.arrays([
        "AliESDRun./AliESDRun.fRunNumber",
        "AliESDRun./AliESDRun.fPeriodNumber",
        "AliESDHeader./AliESDHeader.fTimeStamp",   # path TBC — needs verification
        "AliESDtracks.fP[0]",                       # momentum_x per track
        "AliESDtracks.fP[1]",
        "AliESDtracks.fP[2]",
        "AliESDcaloClusters.fE",                   # cluster energy
    ])
    # Then: rename, reshape (per-track vs per-event), join, serialize to Avro/Parquet
```

This should be raised at the Wednesday Abdullah sync — it does not change the schema, but it changes the **complexity estimate** for Module 3.

### Original practical steps (kept for reference / reproducibility)

A 30-minute hands-on to confirm everything works end-to-end:

1. **Browse the portal:** [opendata.cern.ch](https://opendata.cern.ch/) → click "Focus on: ALICE" → use ALICE experiment filter. Take 1 screenshot.
2. **Open a dataset record:** Click [LHC10h_PbPb_ESD_139465 (record 1106)](https://opendata.cern.ch/record/1106). Note the DOI, dataset characteristics (1.07M events / 5062 files / 1.3 TiB), and file listing structure. Take 1 screenshot.
3. **Download one file (~125–280 MiB):**
   ```cmd
   mkdir %USERPROFILE%\dataforge\data\alice\raw
   cd %USERPROFILE%\dataforge\data\alice\raw
   curl -O https://opendata.cern.ch/record/1106
   ```
   Or use the in-page Download button (simpler).
4. **Install uproot:**
   ```cmd
   pip install uproot awkward numpy
   ```
5. **Open in Python:** Run `inspect_esd.py` against the downloaded file. Confirm `esdTree` is listed and branch names appear. Take 1 screenshot of the terminal output.
6. **Commit notes:** This file + screenshots to `/docs/data/` on GitHub by Friday 23 May (per M1W2T16 deadline).





---

## References

- [CERN Open Data Portal — home](https://opendata.cern.ch/)
- [About ALICE Open Data](https://opendata.cern.ch/docs/about-alice)
- [Getting Started with ALICE Open Data](https://opendata.cern.ch/docs/alice-getting-started)
- [ALICE dataset search (filtered)](https://opendata.cern.ch/search?experiment=ALICE&type=Dataset)
- [Record 1102 — LHC10h Run 139038 PbPb](https://opendata.cern.ch/record/1102)
- [Record 1106 — LHC10h Run 139465 PbPb](https://opendata.cern.ch/record/1106)
- [uproot documentation](https://uproot.readthedocs.io/en/stable/basic.html)
- [HSF uproot tutorial](https://hsf-training.github.io/hsf-training-uproot-webpage/03-trees/index.html)
- [REANA ALICE pt-analysis demo](https://github.com/reanahub/reana-demo-alice-pt-analysis)
- [cbourjau/alice-rs (reference: ESD reading without ALICE framework)](https://github.com/cbourjau/alice-rs)

---


*Draft updated 14 july 2026. Practical walk-through executed by Beyza on 22 May 2026 (Python 3.12 / Windows 10).*
