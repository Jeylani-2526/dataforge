# DataForge — Avro Schema Naming Conventions & Folder Structure

---

## Purpose

This document defines the canonical naming conventions, Avro namespace rules, folder layout, and version policy for all schema files in the DataForge project. All schema work in M2 and every later milestone must follow these conventions.

**Every team member must read this document before creating or editing any `.avsc` file.**

---

## 1. File Naming Convention

**Format:** `{data_source}_schema_v{MAJOR}.avsc`

| Component | Rule | Example |
|---|---|---|
| `{data_source}` | Lowercase, underscore-separated identifier for the data origin | `alice_event`, `sensor`, `fused_event` |
| `_schema_` | Fixed literal — always present | — |
| `v{MAJOR}` | MAJOR version number only (see Section 4 for versioning rules) | `v0`, `v1`, `v2` |
| `.avsc` | Fixed extension — all Avro schemas use `.avsc` | — |

### Confirmed Filenames for M2

| Schema | Provisional Filename (v0) | Locked Filename (v1) |
|---|---|---|
| ALICE event | `alice_event_schema_v0.avsc` | `alice_event_schema_v1.avsc` |
| Sensor (all types) | `sensor_schema_v0.avsc` | `sensor_schema_v1.avsc` |
| Fused event | `fused_event_schema_v0.avsc` | `fused_event_schema_v1.avsc` |

### Why Only MAJOR in the Filename?

Minor version increments — backward-compatible field additions — do **not** produce a new file. The `schema_version` field inside the record tracks the full `MAJOR.MINOR` string internally (e.g., `"1.1"`). A new filename (`_v2.avsc`) is only created when a **breaking change** occurs: a field removal, a type change, or an incompatible structural modification.

This keeps the number of files stable under normal iteration while still making breaking changes explicit and traceable in the file system.

---

## 2. Avro Namespace Convention

**Format:** `dataforge.{source}`

| Schema | Namespace | Record Name |
|---|---|---|
| ALICE event | `dataforge.alice` | `AliceEvent` |
| Sensor (all types) | `dataforge.sensor` | `SensorEvent` |
| Fused event | `dataforge.fused` | `FusedEvent` |

### Namespace Rules

- Namespaces are **all lowercase** — no hyphens, no underscores, no special characters
- The `dataforge.` prefix is fixed for the entire project — do not substitute `project.`, `prototype.`, or any other prefix
- Record names use **PascalCase** (UpperCamelCase): `AliceEvent`, `SensorEvent`, `FusedEvent`
- Sensor subtypes (radar, LIDAR, telemetry) are represented via a `sensor_type` enum field **within** `SensorEvent` — they do not get separate namespaces or separate files

### Example: Correct Avro Record Header

```json
{
  "type": "record",
  "name": "AliceEvent",
  "namespace": "dataforge.alice",
  "doc": "Per-event ALICE Run 1 record with aggregated track fields.",
  "fields": [...]
}
```

---

## 3. Folder Layout

The `/schemas/` directory is **flat** — all `.avsc` files and supporting scripts live at the root level. No subfolders are created at prototype scale.

```
/schemas/
├── alice_event_schema_v0.avsc       ← ALICE event schema (provisional, Week 5)
├── sensor_schema_v0.avsc            ← Sensor schema (provisional, Week 6)
├── fused_event_schema_v0.avsc       ← Fused event schema (provisional, Week 6)
├── alice_event_test_record.json     ← Test record for round-trip validation
├── sensor_test_record.json          ← Test record for round-trip validation
├── fused_event_test_record.json     ← Test record for round-trip validation
├── avro_tool_test.py                ← Omer's fastavro smoke-test (Week 5)
└── validate_schema.py               ← Omer's round-trip validation script (Week 6)
```

**Supporting documentation** — schema notes, evolution policy, data dictionary, tooling guides — lives in `/docs/schemas/`, not in `/schemas/` itself.

```
/docs/schemas/
├── schema_conventions.md            ← This document
├── avro_tooling_setup.md            ← Omer's fastavro setup + usage guide
├── schema_evolution_policy.md       ← Abdalla's Week 7 deliverable
└── data_dictionary.md               ← Abdalla's Week 7–8 deliverable
```

### Why Flat?

At prototype scale (3 schemas), subfolders add navigational overhead with no benefit. A flat directory is also easier to scan programmatically when the M4–M5 pipeline code resolves schema paths at runtime. If the schema count grows beyond six in a later milestone, this policy will be revisited.

---

## 4. Version Policy

| Version State | Meaning | Who Can Modify | Process Required |
|---|---|---|---|
| `v0` | Provisional draft | Abdalla (schema owner) | Free to edit; no team sign-off; no changelog entry |
| `v1` | First locked version | Requires full team agreement | Team review meeting + Abdalla sign-off; changelog entry in evolution policy |
| MINOR bump (e.g., `1.0` → `1.1`) | Backward-compatible addition | Abdalla, with Beyza cross-check | New field added to existing file; `schema_version` default updated; no new filename |
| MAJOR bump (e.g., `1.x` → `2.0`) | Breaking change | Requires full team agreement + Abdalla sign-off | New filename (`_v2.avsc`); migration note in evolution policy; all pipeline references updated |

### Schema Lock Date

**Wednesday 25 June 2026 (Week 7)** — all three schemas must be reviewed and agreed by the full team on this date. After the lock:

- No field may be removed, renamed, or have its type changed without a MAJOR version bump
- No MAJOR bump proceeds without Abdalla's explicit sign-off
- Silent schema changes that break pipeline code are a critical project risk — this boundary prevents them

---

## 5. The `schema_version` Field — Mandatory in Every Schema

Every schema record **must** include a `schema_version` field as the **last field** in the `fields` array. This rule has no exceptions.

```json
{
  "name": "schema_version",
  "type": "string",
  "doc": "Schema version in MAJOR.MINOR format. Increment MINOR for backward-compatible additions; MAJOR for breaking changes. Example: '1.0', '1.1', '2.0'.",
  "default": "0.1"
}
```

| Situation | `schema_version` default | Filename changes? |
|---|---|---|
| Initial v0 draft | `"0.1"` | No |
| First locked v1 release | `"1.0"` | Yes: rename to `_v1.avsc` |
| New field added (backward-compatible) | `"1.1"` | No |
| Second new field added | `"1.2"` | No |
| Breaking change (field removal, type change) | `"2.0"` | Yes: new file `_v2.avsc` |

---

## 6. Test Record Files

Each schema must have a corresponding JSON test record file for use with Omer's `validate_schema.py` validation script. Test records live in `/schemas/` alongside the schema they validate.

**Naming format:** `{data_source}_test_record.json`

| Schema | Test Record File |
|---|---|
| `alice_event_schema_v*.avsc` | `alice_event_test_record.json` |
| `sensor_schema_v*.avsc` | `sensor_test_record.json` |
| `fused_event_schema_v*.avsc` | `fused_event_test_record.json` |

**Test record requirements:**
- All required fields must be populated with **realistic placeholder values** — not nulls, empty strings, or zeroes
- Example realistic values: `"event_id": "EVT-00001"`, `"track_count": 42`, `"net_momentum_x": 0.317`
- A test record full of nulls will not catch type mismatches during serialization

---

## 7. Quick Reference Card

| Rule | Value |
|---|---|
| File format | `{source}_schema_v{MAJOR}.avsc` |
| Namespace | `dataforge.{source}` (all lowercase) |
| Record name style | PascalCase — e.g., `AliceEvent`, `SensorEvent` |
| Folder | Flat `/schemas/` — no subfolders |
| `v0` meaning | Provisional draft — free to edit |
| `v1+` meaning | Locked — full team sign-off required to change |
| Lock date | Wednesday 25 June 2026 (Week 7) |
| MINOR bump trigger | New field added (backward-compatible) — same filename |
| MAJOR bump trigger | Field removed, renamed, or type changed — new filename |
| `schema_version` field | Mandatory, last field in every schema, `MAJOR.MINOR` string |
| Test record format | `{source}_test_record.json` in `/schemas/` |
| Supporting docs location | `/docs/schemas/` (not `/schemas/`) |

---

