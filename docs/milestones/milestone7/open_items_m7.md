# DataForge — M7 Open Items Log

**Originating Task ID:** M8W29T7 (planned as M7W28T4)
**Owner:** Abdalla
**Milestone:** M7 · closed 22 November 2026, package written in M8 Week 29
**Status:** Open — eleven items. Item 2 closed (M8W29T3), Item 3 closed by design. Items 1 and 4–11
open.
**GitHub Path:** `/docs/milestones/milestone7/open_items_m7.md`

**Amendment history:**
- M8W29T7 (25 November 2026) — Document created. Items 1–3 from M7W28T3, Item 4 from M7W28T8,
  Items 5–9 from the M7 evaluation report (Section 10), Item 10 moved from `open_items_m6.md`
  Item 10, Item 11 found while writing the package.
- M8W29T3 (26 November 2026) — Item 2 closed: cause established; 2,058 further orphans from
  26 November recorded.

---

> **Why this document exists**
> Same convention as `open_items_m5.md` and `open_items_m6.md`: every item logged with an honest
> scope, a named owner, a target milestone and a trigger for resolution. M7 closes as
> **closed-with-open-items**.
>
> Three committed M7 documents already point here — `m7_evaluation_report.md` (Section 10),
> `m7w28t3_batch_scoring.md` (Section 3) and `m7_database_contribution.md` (Section B). Item
> wording follows those documents so the references resolve.

---

## Item 1 — Live Scoring Inside the Fusion Stream

**Finding (M7W28T3):** the 18 November trigger was missed. M7 scores fused rows with a one-off
batch scorer (`batch_score.py`), not inside the fusion stream.

**Owner:** Abdalla · **Target:** M8 (M8W30T2, decision D3)
**Trigger:** live scoring and explanations working in the fusion write path by Wednesday
2 December. If not, scoring stays batch (`batch_score.py` plus an explanation backfill) and live
wiring moves to M9.

## Item 2 — 37,060 Orphaned Fused Rows on Abdalla's Machine

**Finding (M7W28T3):** every fused row written before 12 November (25,419 on 15 October,
11,641 on 5 November) points to a staging row that does not exist. Fusion reads sensor events
from Kafka directly; staging is written separately by `spark-processor`. The cause is not
established. M6W26T2's 100% resolution was measured on Beyza's database, so the two results do
not contradict each other — but `open_items_m6.md` Item 10's orphan risk is real on at least one
machine.

**Owner:** Abdalla · **Target:** M8 (M8W29T3)
**Trigger:** staging checked for rows from 15 October and 5 November. None → the cause is
`open_items_m6.md` Item 12.3 (fusion ran without `spark-processor`) and this item closes. Rows
that exist but do not match → re-logged as a new orphan cause.

**Closed (M8W29T3, 26 November 2026) — cause established.** Read-only SQL through `docker exec`
on Abdalla's database:

```sql
-- staging rows by the day spark-processor wrote them
SELECT load_timestamp::date AS load_day, COUNT(*), MIN(load_id), MAX(load_id)
FROM raw_sensor_events_staging GROUP BY 1 ORDER BY 1;
```

| Load day | Staging rows | `load_id` range |
|---|---|---|
| 1 October | 16,566 | 6,085,349 – 6,101,914 |
| 2 October | 81 | 6,101,915 – 6,101,995 |
| *3 October – 11 November* | *none* | — |
| 12 November | 30,225 | 6,101,996 – 6,132,220 |

- **spark-processor wrote no staging rows between 2 October and 12 November.** The `load_id`
  sequence runs on without a gap (6,101,995 → 6,101,996), and its last value equals the highest
  id, so no rows were written on 15 October or 5 November and deleted later. Deletion is ruled
  out.
- The three `load_id` gaps that do exist (2,117,500 ids, 20–24 September) and the missing first
  450,000 ids (the M6W22T7 cleanup) all predate 15 October.
- The orphans' `alice_event_id` values all resolve in `events` (37,060 of 37,060); none of their
  `sensor_event_id` values is in `events` or staging. Only the sensor side is missing.

**Cause:** fusion and `spark-processor` read Kafka independently. On 15 October and 5 November
fusion wrote fused rows while `spark-processor` wrote nothing. The data cannot tell whether it
was not started (`open_items_m6.md` Item 12.3) or had stopped (Item 11).

**Reproduced on 26 November** during M8W29T8's verification: `spark-processor` started, failed
with `OffsetOutOfRangeException` on `sensor-telemetry-0` (checkpoint offset 4,706,410 past
Kafka's 7-day retention) and exited with code 0. Fusion, recovered by its own checkpoint reset,
kept writing alone — **2,058 more orphans** (`fused_events` on 26 November, none resolving).
Fusion was stopped to end it. Orphans on this machine now total 39,118; all lie outside the
scoring window or cannot be scored, and stay NULL.

**Carried, not closed:** preventing it is `open_items_m6.md` Item 11 (silent exit, retention),
extended to `spark-processor` (M8W30T3), and Item 12.3 (README, M8W29T6). Input to M8W30T2:
scoring that joins back to staging (M6W26T5) finds no features whenever `spark-processor` is
down, so live scoring must not assume a staging row exists.

## Item 3 — Rows Before the Producer Alignment Stay Unscored — Closed by Design

**Finding (M7W28T3):** the live producer was aligned to the corpus ranges at `8af19aa`
(12 November). Before that, the corpus-trained model flagged 93.9% of LIDAR's normal live
records (M7W27T1). Rows before the scoring window (2026-11-12 07:06 UTC) stay NULL.

**Status:** closed by design — recorded, not a defect.

## Item 4 — Aligned-Data Scoring Not Verified on a Second Machine

**Finding (M7W28T8):** aligned data was verified on Abdalla's machine only (plan B). Beyza's run
scored her 34,560 pre-alignment rows by mistake; the scores were reverted on 20 November. It
shows the write path works on a second database. It does not show scoring of aligned data there.

**Owner:** Beyza · **Target:** M8 (M8W29T9)
**Trigger:** Beyza's locally trained `model_card_v2.json` matches the committed one, and her
aligned rows pass the six Section A checks of `m7_database_contribution.md`, with
pre-alignment rows left NULL.

## Item 5 — Saturated Risk Scores Cannot Be Ranked (Limit 5)

**Finding (M7 evaluation report, Limit 5):** a record more unusual than every normal training
record gets exactly 1.0, so the strongest alarms tie.

**Owner:** Abdalla · **Target:** M8 (M8W31T2)
**Trigger:** a tie-break in the explanation layer — SHAP or the raw detector scores — that orders
alarms with `risk_score` = 1.0.

## Item 6 — `critical_count` Does Not Fit the v2 Risk Scale (Limit 7)

**Finding (M7 evaluation report, Limit 7):** the API contract defines `critical_count` as
`risk_score > 0.7`. On the test set 32–41% of **normal** records score above 0.7 (RADAR 40.5%,
LIDAR 41.4%, TELEMETRY 32.2%).

**Owner:** Beyza · **Target:** proposal M8 (M8W29T5), implementation M9
**Trigger:** a definition agreed with Abdalla — for example on `anomaly_label = 1` and
`confidence` — and written into `api_contracts_final.md`.

## Item 7 — Telemetry Rules Assume Timestamps Advance (Limit 8)

**Finding (M7 evaluation report, Limit 8):** at the producer's 200 ms interval they do. A
back-to-back run of 20,000 records flagged 97.5% of them as `timestamp_not_advancing`.

**Owner:** Abdalla · **Target:** M10
**Trigger:** the throughput benchmark aimed at the ≥10,000 events/sec bar — the rule is checked
before that benchmark's records are scored.

## Item 8 — Harder Evaluation Set

**Finding (M7 evaluation report, Limits 1–2):** every injected anomaly sits far outside the
normal range, and train and test come from the same generator. AUC 0.997 measures separation on
this corpus, not performance on real faults.

**Owner:** Abdalla · **Target:** M10, with `open_items_m6.md` Item 14
**Trigger:** subtler and correlated anomalies added to the corpus and the model re-evaluated on
them.

## Item 9 — PyTorch Deep Model (M7W28T2)

**Finding:** the 15 November trigger was not met; the deep model was never started. The
prototype bar does not depend on it — model v2 meets it.

**Owner:** Abdalla · **Target:** M10
**Trigger:** M10 planning decides whether it is built or dropped.

## Item 10 — Staging Retention Rule (moved from `open_items_m6.md` Item 10)

**Finding:** nothing in the database stops a staging cleanup from orphaning fused rows (soft
references, Option C). The rule was due in M7W27T4 and is not in any committed document.
Item 2 shows the risk is real.

**Owner:** Beyza · **Target:** M9
**Trigger:** the rule "no cleanup deletes staging rows referenced by `fused_events`" written into
the staging documentation. Item 2's cause is known first, so the rule covers what actually
happened.

## Item 11 — CI Does Not Build Images or Check the Model

**Finding (M8W29T7):** in `.github/workflows/ci.yml` the "Docker Compose Build" job runs
`docker compose config --quiet` only — it validates the compose file and builds no image. The
"Model AUC validation" stage, marked to activate in M7, is still commented out.

**Owner:** Abdalla · **Target:** M10
**Trigger:** either job activated, or formally dropped with the reason recorded.

---

## Recorded, Not Carried

- **Three `timestamp_stall` misses** on `SENSOR-UNIT-01` (M7 evaluation report, Section 5): each
  follows a `missing_reading` on the same device. A corpus artefact; recorded, not fixed.

## Inherited From `open_items_m6.md`

M6 items stay in their own log. Those in M8's scope are carried by the M8 charter: Item 1
(watermark decision, M8W29T2), Item 4 (mis-pairing, M8W31T3), Item 11 (fusion resilience,
M8W30T3) and Item 12 (compose operability, M8W29T6). Items 8 and 13 were closed and Item 10's
residual moved here by the M8W29T7 amendment to that log.

---

## Summary

| Item | Status | Owner | Target | Trigger |
|---|---|---|---|---|
| 1 Live scoring in fusion | Open | Abdalla | M8 | Working by 2 December, else M9 |
| 2 37,060 orphaned rows | **Closed** (M8W29T3) — cause established | Abdalla | — | Met: staging empty 3 Oct – 11 Nov |
| 3 Pre-alignment rows unscored | **Closed by design** | — | — | — |
| 4 Second-machine aligned scoring | Open | Beyza | M8 | Model card matches; Section A checks pass |
| 5 Saturated risk scores | Open | Abdalla | M8 | Tie-break in the explanation layer |
| 6 `critical_count` on v2 scale | Open | Beyza | M8 → M9 | Definition agreed and in the contract |
| 7 Telemetry timestamp rule | Open | Abdalla | M10 | Throughput benchmark |
| 8 Harder evaluation set | Open | Abdalla | M10 | Subtler anomalies, re-evaluation |
| 9 PyTorch deep model | Deferred | Abdalla | M10 | M10 planning |
| 10 Staging retention rule | Open | Beyza | M9 | Rule written into staging docs |
| 11 CI image build + model gate | Open | Abdalla | M10 | Activated or formally dropped |
