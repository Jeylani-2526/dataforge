# DataForge — Schema Evolution Policy



---

> **Why this document exists**  
> All three DataForge Avro schemas were locked on 25 June 2026. From Milestone 4 onward, pipeline code in Modules 3–9 will be compiled and tested against these schemas. An undocumented schema change — even a small one — can silently break a downstream consumer that has no visibility into the change. This policy makes every change traceable, intentional, and safe.

---

## 1. Backward Compatibility Rules

All schema changes must be evaluated for backward compatibility before they are committed. The following rules apply to all three schemas.

### Allowed without a MAJOR version bump (backward-compatible)

These changes can be made as MINOR version increments and deployed to the existing Kafka topic without breaking existing consumers:

- **Adding a new optional field** — the new field must use an Avro union type `["null", <type>]` with a default of `null`. Existing consumers that do not know about the field will continue to deserialize records correctly.
- **Adding a new enum symbol** — a new value may be appended to the end of an existing enum's symbol list. Existing consumers that do not handle the new symbol must be updated before the producing module is deployed, but they will not crash on deserialization.
- **Widening a numeric type** — for example, promoting an `int` field to a `long`. This is safe in Avro with schema resolution and does not break readers built against the older schema.
- **Updating a `doc` annotation** — documentation-only changes have no serialization impact.

### Never allowed without a MAJOR version bump (breaking changes)

Any of the following constitute a breaking change and require a MAJOR version increment, a new Kafka topic, and a migration note appended to this document:

- **Removing a field** — even an unused-looking field may be consumed downstream. No field may be removed without completing the full deprecation process described in Section 3.
- **Renaming a field** — Avro has no concept of field aliases for the schemaless writer pattern used in this project. Renaming is equivalent to removing the old field and adding a new one — it is always breaking.
- **Changing a field's type** — for example, changing `latency_ms` from `long` to `float`. Any change that alters the binary encoding of a field is breaking.
- **Removing an enum symbol** — existing records that carry the removed symbol become undeserializable against the new schema.
- **Changing the field order** — the schemaless writer encodes fields positionally. Field order changes are always breaking.
- **Adding a new required field** (i.e., without a default) — existing records that pre-date the change will fail to deserialize because the field is absent.

---

## 2. Version Numbering Convention

All DataForge schemas use **MAJOR.MINOR** version numbering. The version is tracked in two places: the filename and the `schema_version` field within the record.

### Filename versioning (MAJOR only)

The filename tracks the MAJOR version only:

```
{data_source}_schema_v{MAJOR}.avsc
```

Examples:
- `alice_event_schema_v1.avsc` — current locked version
- `alice_event_schema_v2.avsc` — would be created on the first breaking change

The filename does not encode the MINOR version. The `schema_version` field inside the record is the authoritative source of the full MAJOR.MINOR version.

### Internal field versioning (MAJOR.MINOR)

The `schema_version` string field present in every DataForge schema record encodes the full version:

| Change type | Example | Version before | Version after |
|---|---|---|---|
| Breaking change | Field removed | `1.2` | `2.0` |
| Backward-compatible addition | New optional field added | `1.0` | `1.1` |
| Documentation-only change | `doc` annotation updated | `1.0` | `1.0` (no bump) |

### Starting version

All three schemas were locked at version `1.0` on 25 June 2026. The first backward-compatible addition to any schema produces version `1.1`. The first breaking change produces version `2.0` and requires a new file and a new Kafka topic.

---

## 3. Field Deprecation Process

No field may be removed from a DataForge schema without first going through this deprecation process. The process ensures that all downstream consumers have time to stop using the field before it is deleted.

### Step 1 — Mark the field as deprecated

Add `"deprecated"` to the beginning of the field's `doc` annotation in the schema file. Increment the MINOR version. Example:

```json
{
  "name": "legacy_field",
  "type": ["null", "string"],
  "default": null,
  "doc": "DEPRECATED as of schema version 1.1. Will be removed in version 2.0. Use replacement_field instead."
}
```

Commit the change with a migration note appended to this document (see Section 5).

### Step 2 — Notify all consumers

All team members must be informed at the next Tuesday team meeting. The deprecation must also be flagged in the Friday update to Emrah if it affects a milestone deliverable.

### Step 3 — Maintain through one full MAJOR version

The deprecated field must remain in the schema for the entirety of the current MAJOR version. For example, a field deprecated in `v1.1` may not be removed until `v2.0`. This gives all consuming modules — in this project, Modules 4, 5, 6, 7, 8, and 9 — at least one full milestone cycle to remove their dependency on the field.

### Step 4 — Remove in the next MAJOR version bump

When a MAJOR version bump occurs for any reason (breaking change), all fields that have been deprecated for at least one full MAJOR version are removed at the same time. This batches removals to minimize disruption.

---

## 4. Kafka Topic Criteria

### Base rule — applies to all three topics

| Change type | Action |
|---|---|
| MINOR version bump (backward-compatible) | Evolve the existing topic. Avro schema resolution handles old and new records on the same topic. No topic rename. |
| MAJOR version bump (breaking change) | Create a new topic with a version suffix. Example: `fused_events` → `fused_events_v2`. The old topic remains readable until all consumers have migrated. |

**Current topics and their schemas:**

| Kafka Topic | Schema | Current Version |
|---|---|---|
| `alice_events` | `alice_event_schema_v1.avsc` | 1.0 |
| `sensor_events` | `sensor_schema_v1.avsc` | 1.0 |
| `fused_events` | `fused_event_schema_v1.avsc` | 1.0 |

### Cascade rule — fused_events only

`fused_events` is architecturally downstream of both `alice_events` and `sensor_events`. It has three consumers (Modules 7, 8, and 9), more than any other topic in the pipeline. Because of this, the following additional rule applies:

> **Any MAJOR version bump to `alice_events` or `sensor_events` automatically triggers a mandatory compatibility review of `fused_event_schema` before the upstream change is deployed.**

This review must produce one of two outcomes, documented in writing by Abdullah before the upstream schema change is committed:

1. **"No impact" sign-off** — a written note confirming that the upstream change does not affect any field in the fused schema, committed as a migration note to this document.
2. **A corresponding version bump on `fused_events`** — if the upstream change affects a field referenced in the fused schema (for example, a change to the `sensor_type` enum), the fused schema must be updated, versioned, and a new `fused_events` topic created in the same deployment.

**Rationale:** Without this rule, a MAJOR bump to `sensor_schema` could silently invalidate the `sensor_type` enum definition embedded in `fused_event_schema`, breaking Modules 7, 8, and 9 with no visible warning at the schema level.

### Consumer migration protocol

When a new topic is created following a MAJOR bump:

1. The producing module writes to **both** the old and new topic simultaneously during a transition window (minimum: one full week of testing in the relevant milestone).
2. Each consuming module is updated and confirmed working against the new topic before the old topic is retired.
3. The old topic is retired only when all consumers have migrated and confirmed — not before.

---

## 5. Post-Lock Change Process

The schema lock date is **25 June 2026**. After this date, no changes may be made to any schema file in `/schemas/` without completing all of the following steps. This applies to every change, including documentation-only updates.

### Required steps for any post-lock change

**Step 1 — Raise the change request**  
The team member proposing the change must describe it in writing: which field, which schema, why the change is needed, and whether it is backward-compatible. This is raised at the Tuesday team meeting or, for urgent changes, in the team chat with a written summary.

**Step 2 — Abdullah sign-off**  
Abdullah reviews the proposed change against Section 1 (backward compatibility rules) and Section 4 (Kafka topic criteria). Sign-off is required before any file is edited. If Abdullah is unavailable, the change is held — no exceptions.

**Step 3 — Version bump**  
Increment the `schema_version` field in the schema file according to Section 2. If the change is a MAJOR bump, create a new `.avsc` file with the incremented MAJOR version in the filename.

**Step 4 — Run validation**  
Run `validate_schema.py` against the updated schema with all relevant test records from `/schemas/test_records/`. All records must produce PASS before the change is committed. For sensor schema changes, all three subtype test records (RADAR, LIDAR, TELEMETRY) must be run.

**Step 5 — Append a migration note to this document**  
Add a dated entry to the Migration Log section below. Include: the date, the schema changed, the old and new version, a one-sentence description of the change, and whether a new Kafka topic was required.

**Step 6 — Commit and tag**  
Commit the updated schema file and this policy document together in the same commit. Apply a tag in the format `schema-change-{schema}-v{MAJOR}-{MINOR}` (example: `schema-change-fused-v1-1`).

**Step 7 — Notify Emrah**  
If the change affects a milestone deliverable or alters a field visible in the API response contracts or dashboard, it must be reported in the next Friday update to Emrah. Schema changes that are purely internal to the pipeline (e.g., adding a pipeline metadata field not surfaced in the API) do not require a separate Emrah notification.

---

## Migration Log

*This section is append-only. Each entry records a post-lock schema change. No entries may be modified or deleted.*
| Date | Schema | Old Version | New Version | Change Summary | New Topic Required? | Sign-off |
|---|---|---|---|---|---|---|
| 14 July 2026 | alice_event_schema_v1.avsc | 1.0 | 1.0 (no bump — doc-only per Section 2) | Corrected `run_number` doc string from 139038 to 139465 to match the verified acquired ALICE sample, per M3W10T1 team decision (see alice_discrepancy_resolution.md) | No | Abdullah |

---


