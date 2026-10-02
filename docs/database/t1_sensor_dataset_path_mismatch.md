# T1 Sensor Dataset Path Mismatch — Resolution Note

## Issue

During Abdullah's T7 review, a path mismatch was flagged between the original sensor dataset filenames and the current `data/synthetic/` contents.

## Root Cause

Ömer's commit `524f976` (M4W15T1) intentionally renamed and trimmed the sensor dataset files:

| Original | Renamed to | Action |
|---|---|---|
| `lidar50000data.jsonl` | `lidar.jsonl` | Renamed |
| `radar50000data.jsonl` | `radar.jsonl` | Renamed |
| `telemetry50000data.jsonl` | `telemetry.jsonl` | Renamed |
| `lidar_continuous_sample.jsonl` | — | Removed |
| `radar_continuous_sample.jsonl` | — | Removed |
| `telemetry_continuous_sample.jsonl` | — | Removed |

Result: `data/synthetic/` now contains exactly 4 files — `alice.jsonl`, `lidar.jsonl`, `radar.jsonl`, `telemetry.jsonl` — totalling 150,068 records.

## Resolution

No fix required. `staging_ingestion_script.py` uses content-based stream detection — filenames are irrelevant. Staging run confirmed clean against the renamed files:

```
alice.jsonl      stream=alice      loaded=68     failed=0
lidar.jsonl      stream=lidar      loaded=50000  failed=0
radar.jsonl      stream=radar      loaded=50000  failed=0
telemetry.jsonl  stream=telemetry  loaded=50000  failed=0
```
