# M8W29T2 — Effective-Watermark Specification Decision

**Owner:** Abdalla
**Milestone:** M8 · Week 29 · Task M8W29T2
**Date:** 26 November 2026
**Status:** Signed — decisions W1–W3 taken by Abdalla on 26 November 2026
**Closes the decision half of:** `open_items_m6.md` Item 1 (implementation stays M10)
**Evidence:** `m6w23t2_sync_validation.md` (T4 — watermark boundary), `fusion_join_design_note.md`
Sections 5–6, `open_items_m5.md` Item 8
**No code change in this task.**

---

## 1. Decisions

| # | Question | Decided |
|---|---|---|
| **W1** | What the specification says about late data | **Adaptive, with a floor and a ceiling.** Every stream is given at least `WATERMARK_DELAY_SECONDS` (5 s). The threshold in force is that floor plus the lag of the slowest input stream plus up to one batch of delay, and it is reported, not hidden. |
| **W2** | `spark.sql.streaming.multipleWatermarkPolicy` | **Stays `min`.** |
| **W3** | When the adaptive threshold becomes a problem | **Warn above 30 s** between the watermark and the newest event time. |

---

## 2. What was measured (M6W23T4)

| Quantity | Value |
|---|---|
| Configured delay (`WATERMARK_DELAY_SECONDS`) | 5 s |
| Watermark gap behind the newest event time, three batches under injection | 13.47 s, 12.43 s, 13.40 s |
| Injected sensor delay in that run | 7–9 s |
| Batch commit time against a 5 s trigger (Item 3) | 8,033 ms and 9,876 ms |
| Records shifted 7–9 s | accepted |
| Records shifted 30 s (fraction 0.05) | **160 rows dropped** |

The surplus over 5 s tracked the injected delay. Two contributors, not fully separable from
that sample:

1. **`min` policy.** Fusion reads four streams — ALICE and three sensor topics — each with its
   own watermark. `min` makes the global watermark follow the slowest, so a lagging topic holds
   it back instead of losing records.
2. **Batch lag.** The watermark only advances between batches; batches took 8–10 s against a 5 s
   trigger.

---

## 3. The specification

> DataForge accepts a sensor or ALICE record into fusion if it arrives no later than the
> **effective lateness threshold**:
>
> **threshold = `WATERMARK_DELAY_SECONDS` (5 s) + lag of the slowest input stream + up to one
> batch interval.**
>
> - The 5 s floor is guaranteed to every stream.
> - The threshold rises when a stream falls behind, so a slow stream's records are kept, not
>   dropped.
> - The threshold in force is measured per batch as the gap between the newest event time and
>   the watermark, and reported.
> - A gap above **30 s** is a fault condition and raises a warning: a stream has fallen far
>   behind or stopped.
> - Records later than the threshold in force are dropped and counted
>   (`numRowsDroppedByWatermark`, already logged by `DroppedRowListener`).

The configuration value is the floor, not the threshold. Documentation and the dashboard must
not present 5 s as "the" lateness limit.

---

## 4. Why

### W1 — options considered

| Option | Keeps slow-stream records | Honest about the number | Cost |
|---|---|---|---|
| **Adaptive + floor + ceiling (chosen)** | Yes | Yes — measured and reported | No hard upper bound below the ceiling; latency grows with skew |
| Fixed at 5 s | No — not achievable under `min` when streams are skewed; forces `max` | Yes | Silent drops of the lagging stream |
| Fixed, raised (e.g. 15 s) | Yes | No — still adaptive above 15 s | +10 s latency on every event, more join state, a wider mis-pairing window (Section 5) |

For defense and industrial sensors, a record that is late but kept can still be scored and
explained; a record silently dropped cannot. The adaptive threshold is acceptable **because it
is measured and bounded**, not because it is invisible.

### W2 — why `min` stays

`max` lets the fastest stream drive the watermark. A topic running behind then has its records
dropped as late — `open_items_m5.md` Item 8, caveat 2 — and the 1 : 1 fused output breaks with
no error. The M6 design note (Section 5) locked `min` for this reason; the M6 measurements give
no reason to reverse it.

The accepted trade-off from the design note stands: if a producer stops, the watermark freezes
and fusion pauses until it returns.

### W3 — why 30 s

- It is the one point where drops were observed (30 s shift, 160 rows).
- Normal operation under a 7–9 s injected delay measured 12–13 s, so 30 s warns only when
  something is clearly wrong.
- It also catches the frozen watermark of a stopped producer — the design note's accepted
  trade-off — which nothing reports today: the gap grows past 30 s within seconds of the stall.

---

## 5. Consequences

| Item | Effect |
|---|---|
| `open_items_m6.md` Item 1 | Decision taken. Stays open for M10 with a new trigger: the per-batch gap logged and the 30 s warning working. |
| Item 2 — drop boundary not narrowed | **Closed — superseded.** Under W1 there is no fixed boundary to find: the threshold moves with stream lag. Per-batch measurement (M10) replaces it. |
| Item 3 — batch commit 8–10 s | Unchanged, M10. Reducing batch lag lowers the threshold directly. |
| Item 4 / **M8W31T3** — silent mis-pairing | A record shifted between 500 ms and the threshold in force survives the watermark and can fuse with an older ALICE event. The window for that error is the threshold itself, so M8W31T3 records the watermark gap during its injection run, next to the mis-pairing rate. |
| **M8W30T2** — live scoring and explanations | Alarms appear once the watermark passes the pair's window: at today's ~16 s fused-path latency (M6W23T1), an operator sees an explanation about that long after the event. Recorded, not changed. |

---

## 6. What M10 implements

1. Read `eventTime.watermark` and `eventTime.max` from each fusion query progress event (the
   existing `StreamingQueryListener` already reads progress) and log the gap per batch.
2. Warn when the gap exceeds 30 s; surface it where the heartbeat can report it. Whether that
   needs a new `fusion_status` column is a schema decision for M10, under
   `schema_evolution_policy.md`.
3. Update the README and the Fusion Monitor wording: the configured 5 s is a floor.

---

## 7. What this does not decide

- The value of the floor. 5 s stays; changing it is an M10 tuning question.
- Throughput and batch lag — `open_items_m5.md` Item 1 and `open_items_m6.md` Item 3, M10.
- Restart safety and retention — `open_items_m6.md` Item 11, M8W30T3.
