# Repeat-Generation Mode & Device Diversity — Closure Note

**Task:** M5W19T8
**Date:** 19 September 2026
**Owner:** Beyza Ülkümen
**Resolves:** open_items_m4.md Item 2

---

## Background

`open_items_m4.md` Item 2 and the M5 milestone document both list "repeat-generation mode" and "device diversity" as unresolved for the sensor producer. This note closes Item 2 based on direct inspection of the committed code.

---

## Findings

### Device Diversity

`sensor_producer.py` defines the following stable device ID sets:

```python
RADAR_SENSOR_IDS     = ["radar-001", "radar-002", "radar-003"]        # 3 devices
LIDAR_SENSOR_IDS     = ["lidar-001", "lidar-002", "lidar-003"]        # 3 devices
TELEMETRY_DEVICE_IDS = ["UAV-01", "UAV-02", "SENSOR-UNIT-01",
                         "SENSOR-UNIT-02", "GCS-01"]                   # 5 devices
```

TELEMETRY_DEVICE_IDS matches the M4W13T8 scoping document's 5-device requirement exactly. RADAR and LIDAR device IDs are stable across runs — selected randomly per record, consistent with the scoping intent.

### Repeat-Generation Mode

The producer runs an unbounded `while _running:` loop, publishing indefinitely until a SIGTERM or SIGINT signal is received. There is no fixed batch size or record count ceiling. The loop terminates only on shutdown signal.

This is always-on behavior — there is no separate "repeat mode" flag to toggle; the producer is repeat-generation by design.

### Sequence Numbering

TELEMETRY records carry a per-device monotonically increasing `sequence_number`, maintained via `_sequence_counters`. This enables gap detection on the consumer side and is consistent with the M4W13T8 requirement.

---

## Resolution

**open_items_m4.md Item 2 is closed.**

Both sub-requirements are satisfied by the committed `sensor_producer.py` (commit `329fb02`):

- Device diversity: implemented and matches the M4W13T8 scoping document
- Repeat-generation mode: implemented as an always-on unbounded loop; no mode flag needed

**One gap to note for M5 open items:** the producer has not yet been verified under sustained multi-hour load in a containerized environment. The local validation (commit `329fb02`, schema validation pass) confirms correctness but not long-run stability. This is logged as a future verification item, not a blocker for closing Item 2.
