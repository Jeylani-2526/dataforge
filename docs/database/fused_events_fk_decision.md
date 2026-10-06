# FK-Target Decision Note — fused_events Foreign Keys

---

## Problem

`erd_final.md` defines:

```
fused_events.alice_event_id  → events.event_id
fused_events.sensor_event_id → events.event_id
```

But streamed records from M5 land in `raw_sensor_events_staging`, not `events`. The `promote_to_production.py` script moves records from staging to `events`, but it is not called in the streaming path. A DB-level FK pointing at `events` would fail on insert for any fused row whose source records have not yet been promoted.

---

## Options

### Option A — FK to `events` (ERD as written)

Requires records to exist in `events` before a fused row is inserted. This means promotion must happen inside the streaming path, or the join must wait for promotion to complete before writing.

**Trade-offs:**
- Referential integrity enforced at DB level — M7/M8 queries join cleanly against `events`
- Adds latency: fusion blocked until promotion completes
- Promotion inside the streaming path was not designed or tested in M5
- Introduces tight coupling between Module 5 and Module 6

### Option B — FK to `raw_sensor_events_staging`

Point FKs at staging instead of production. Records are guaranteed to exist there at join time.

**Trade-offs:**
- FK is satisfiable immediately — no latency added
- M7/M8 queries must join against staging, which is a high-volume table with no retention policy
- Staging is a transient layer by design — long-term FK dependency breaks the intended staging/production separation
- ERD requires a change

### Option C — Soft reference (no DB-level FK)

Store `alice_event_id` and `sensor_event_id` as plain `uuid` columns with no FK constraint. Application-level integrity only.

**Trade-offs:**
- No insert latency — fused rows written immediately after join
- No DB-level cascade on delete — orphaned fused rows possible if staging is cleaned
- M7/M8 queries rely on application-level joins; no DB guarantee
- Simplest implementation path for M6 Week 22

---

## Recommendation

**Option C — soft reference for M6, with a path to Option A in M7.**

Reasoning:

1. Streaming records are never promoted in the current path. Option A requires a streaming-path change that is out of scope for M6 and untested.
2. Option B ties M6 and M7 permanently to the staging table, which has no retention policy — a structural risk.
3. Option C unblocks Week 22 join build with zero schema changes. The `uuid` columns remain semantically correct FKs; only the DB constraint is deferred.
4. When M7 is designed, the team can decide whether to enforce the FK (Option A, with promotion built into the streaming path) or retain the soft reference with an application-level integrity check.

**DDL consequence for T6:** `alice_event_id` and `sensor_event_id` are declared `uuid NOT NULL` with no `REFERENCES` clause. A comment documents the soft-reference intent.

---

## Sign-off Required

This note must be reviewed and signed off by Abdullah before T1 (join design) and T6 (DDL) are finalised. Both depend on the FK decision.
