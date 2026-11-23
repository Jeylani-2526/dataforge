# M6W26T5 — Feature-Access Decision & Sign-Off

**Owner:** Abdalla (sign-off authority, `schema_evolution_policy.md`)
**Status:** SIGNED OFF — 5 November 2026
**Inputs:** M6W26T1 (conformance PASS), M6W26T2 (resolution), M6W26T4 (sync run)

Milestone 7 needs two things from every record it trains on or scores:
**feature values** and, for evaluation, a **ground-truth label**. This note
decides where each comes from. They have different answers, so they are
decided separately.

---

## 1. Evidence

| # | Fact | Source |
|---|---|---|
| E1 | `fused_event_schema_v1` carries no measurement. All 9 fields are ids, pipeline metrics or metadata | Schema file; Week 26–28 plan |
| E2 | 100% of fused rows resolve to `raw_sensor_events_staging` and `raw_alice_events_staging` (34,560 / 34,560 on Beyza's DB) | M6W26T2 |
| E3 | Sensor feature columns exist **only** in staging. `promote_to_production.py` copies just `sensor_type`, `label`, `anomaly_type` into `events`, which has no sensor measurement columns | `promote_to_production.py`, `init-db.sql` |
| E4 | Every streamed sensor record is written to staging with **`label = 0`, `anomaly_type = NULL`** — a hardcoded placeholder, not an M3 label | `spark_consumer.py` `make_sensor_batch_writer()` |
| E5 | Consequently 0 of 34,560 fused rows carry an anomaly. The live stream has **no positive class** | M6W26T2, `anomaly_type` count = 0 |
| E6 | The labeled M3 corpus exists and is committed: 50,000 records per stream, 1,482 / 1,486 / 1,483 anomalies (2.96–2.97%) | `data/synthetic/*.jsonl`, M3W11T1 |
| E7 | `labeled_training_data_spec.md` already locks M7 evaluation to the M3 per-stream 20% test split, and states labels are **not** part of the Avro wire schema because production sensor data has no ground truth | Spec Sections 1, 3 and 4 |
| E8 | ALICE contributes 68 distinct records, looped. They carry no label | `alice_producer.py`, `data/synthetic/alice.jsonl` |
| E9 | A fused row resolves only if spark-processor ran alongside fusion. The M6W26T4 run did not start spark-processor, so its 1,256 rows are not expected to resolve on that DB | M6W26T4 run script |

---

## 2. Decision A — Where features come from

| Option | What it means | Cost |
|---|---|---|
| **A1. Join back at scoring time** | Keep `fused_event_schema_v1`. M7 joins `sensor_event_id` → `raw_sensor_events_staging` for feature values | One join per record. Depends on staging rows being present |
| A2. Bump to `fused_event_schema_v2` | Copy feature columns into every fused row | New schema, writer, `enforce()` stream entry, DDL, conformance check — in a two-week milestone. Duplicates data that already resolves at 100% |

**Decision: A1.** E2 shows the join works. A2 would reopen a locked schema to
solve a problem the data does not have. M6's "no schema bump" position stands.

**The join target is staging, not `events`.** The Week 26–28 plan says
"events or staging". Per E3, `events` can never supply sensor features.

**Conditions attached to A1** — without these, the join decays:

1. **No staging cleanup may delete rows referenced by `fused_events`.** M6W22T7
   truncated 450,000 staging rows, and nothing in the database prevents an
   orphan (soft references, Option C). Any future cleanup must exclude
   referenced `event_id`s. Owner: Beyza.
2. **spark-processor must run whenever fusion runs** (E9). Otherwise fused rows
   reference sensor events that never reach staging.
3. **Live scoring (M7W28T3) must handle a missing join**: count it, skip the
   row, never score on nulls. Spark and fusion read Kafka independently, so a
   fused row can arrive before its staging row.

---

## 3. Decision B — Where labels come from

The fused stream cannot supply labels (E4, E5). This is not a data-loss
problem. The live stream was never designed to carry them (E7).

| Option | What it means | Verdict |
|---|---|---|
| **B1. Train and evaluate on the M3 corpus** | Per-stream 80/20 stratified split, as locked in the spec. Fused path used for live **scoring** only | **Chosen** |
| B2. Put labels into the live stream | Anomaly injection in `sensor_producer.py`, label carried through Kafka, Spark stops hardcoding 0 | Rejected for M7 — see below |
| B3. Train on fused rows, evaluate on M3 | Isolation Forest is unsupervised, so it can train without labels | Rejected — the two sets come from different generators, so a gap between them would be unexplainable |

**Why B1.** It is not a fallback. It is what `labeled_training_data_spec.md`
already specified (E7). The 450,000-row truncation and the orphan risk never
affected it, because the corpus is a committed file, not a database table.

**Why not B2 now.** It needs `label` in the Avro wire format, which the spec
rules out on purpose: a real sensor does not know whether it is anomalous. It
also touches the producer, the Spark writer and the schema inside a two-week
milestone. Carried to M10 as an option for end-to-end validation on a labeled
live stream.

**Consequence to state plainly in the M7 package:** the roadmap's "train on
fused data" wording is met as **"train on the corpus that feeds the fused
stream, score on the fused stream"**. That is an interpretation, and it is
recorded as one rather than assumed.

---

## 4. Model scope for Week 27

| Choice | Decision | Reason |
|---|---|---|
| Model instances | **One Isolation Forest per sensor stream** (RADAR, LIDAR, TELEMETRY) | Streams populate different columns. The spec's per-stream split was chosen for this |
| Features | Each stream's populated measurement columns from `sensor_schema_v1` | Only these exist in both the corpus and staging, so training and scoring see the same features |
| ALICE features | **Excluded from v1** | 68 distinct vectors (E8), no labels, and the ALICE–sensor pairing is a timing coincidence, not a physical relationship. Adding them would let the model learn which ALICE record a sensor event happened to pair with |
| Evaluation set | M3 20% test split, per stream: ~296 anomalous + ~9,700 normal | Locked in the spec, Section 4 |
| Bar | AUC ≥ 0.85, FPR ≤ 5%, per stream and pooled | Prototype performance bar |

The spec's own warning carries forward: ~300 anomalous test records per stream
is a small sample for a stable AUC. M7W27T2 reports confidence intervals, not
just a point figure.

---

## 5. Decision C — How the three models produce one decision

Each fused row carries **one** sensor event (1 ALICE : 1 sensor, locked). The
three models therefore never judge the same event together.

| Level | What it does | Decision |
|---|---|---|
| **1. Router** | Each fused row is scored by the model for its `sensor_type` | **M7** |
| **2. Common risk score** | Each model's raw score is converted to one 0–1 scale: the share of normal training scores it exceeds. One ranked alert list across sensors, and one system-wide AUC/FPR alongside the per-stream figures | **M7** — added to M7W27T2 |
| 3. True cross-sensor fusion | Anomalies visible only by combining sensors, e.g. radar sees a target and LIDAR at the same place does not | **Not feasible in M7.** Recorded as a known limitation, target M10 |

Level 2 is the late-fusion step M7 can honestly claim. Level 3 is not in the
data: sources are paired by time only, and anomalies are injected into each
stream independently. It needs a shared-scene generator, linked anomalies, a
join on target or location, and a change to the 1:1 fused schema.

**Live false-positive check (added to M7W28T3).** Every live fused row is
normal (E5). The share of live rows the trained models flag is therefore a
measured false-positive rate on real fused traffic — the one thing the M3
corpus cannot show.

## 6. ALICE's role

ALICE validates the **architecture** adapted from CERN ALICE O²: throughput,
timing, streaming and fusion mechanics. It does not take part in detection: it
has no labels, 68 distinct records, and no physical relationship to the
sensors. Stated as such in the M7 package rather than left implicit.

## 7. Raised with Emrah

Level 3 goes to Emrah directly, asking whether Prof. Dr. Ayben Karasu Uysal
expects cross-sensor detection for the project's scientific claim. If yes, M10
scope changes, and that must be known before M8 opens.

---

## 8. Effect on the plan

| Task | Change |
|---|---|
| M7W27T2 Isolation Forest | Adds the Level 2 common risk score and a pooled AUC/FPR |
| M7W27T1 Feature assembly | Two paths: training reads `data/synthetic/{radar,lidar,telemetry}.jsonl`; scoring joins fused → staging. Same feature function for both |
| M7W27T4 Training extraction (Beyza) | Re-scoped: class balance is checked on the **M3 split**, not on a database extraction. The fused join cannot change it |
| M7W28T3 Live inference | Must implement condition A3 (missing-join handling), and reports the live false-positive rate |
| `open_items_m6.md` Item 10 | Closed for M7 by A1 + B1. Staging-retention rule (A1 condition 1) stays open with Beyza |

---

## 9. Sign-off

| | |
|---|---|
| Decision A | A1 — join back to staging at scoring time, no schema bump |
| Decision B | B1 — train and evaluate on the M3 per-stream corpus |
| Decision C | Level 1 router + Level 2 common risk score in M7; Level 3 deferred to M10 |
| Model scope | Per-stream Isolation Forest, sensor features only; ALICE excluded |
| Signed | ☑ Abdalla — 5 November 2026 |
