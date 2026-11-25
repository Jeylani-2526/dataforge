# M8W29T1 — XAI Design Note

**Owner:** Abdalla
**Milestone:** M8 · Week 29 · Task M8W29T1
**Date:** 25 November 2026
**Status:** Signed — decisions X1–X4 taken by Abdalla on 25 November 2026
**Builds on:** model v2 (`services/ml/model_v2.py`), M8 decisions D1–D4, `erd_final.md`,
`api_contracts_final.md` Sections 8 and 10
**Figures:** `services/ml/xai_probe.py` (test-set alarms, model v2)
**Used by:** M8W29T4 (tables), M8W29T5 (contract), M8W30T1 (`xai.py`), M8W30T2 (live writer),
M8W30T4 (write-path conformance), M8W31T1–T2 (fidelity, cause-effect text)

---

## 1. What this note fixes

What an explanation **means** before any of it is built: what the numbers are, which sign is
which, one stored shape for every alarm, and what is shown when several detectors fire.
Wording of the operator text is drafted here and finalised in M8W31T2.

---

## 2. Decisions

| # | Decision | Chosen |
|---|---|---|
| **X1** | Method for RADAR and LIDAR | SHAP over the stream's Isolation Forest for **every** alarm, whichever detector fired. A z-score sentence is added to the text when the z-score check fired. |
| **X2** | Stored value and direction | `shap_value` = **−SHAP** (sign flipped), so positive = pushes toward the alarm. `direction` keeps the contract's enum: `positive` = toward alarm, `negative` = toward normal. |
| **X3** | Field name | `shap_value`, as in the ERD and the API contract. `dashboard_data_fields` row 10 changes (M8W29T5). |
| **X4** | `model_version` | The scoring model's version, `combined-m7w28t1-v2` (19 characters, fits `VARCHAR(20)`). The XAI logic is versioned by this note and git. No schema change. |

Taken from the M8 charter, not decided here: explanations stored in `anomaly_alerts` +
`xai_explanations` (D1), alarm rows only (D2), code in `services/ml/` (D4).

---

## 3. What SHAP measures on an Isolation Forest

| Question | Answer (test-set alarms) |
|---|---|
| What do the values add up to? | The record's **expected path length** E[h]: base value + sum of SHAP = E[h], max error 1.2×10⁻¹³. Not `risk_score`. |
| Base value (average path length) | RADAR 11.405, LIDAR 12.028 |
| Sign on alarms | The sum is **negative on 100%** of alarms: an anomaly is isolated in fewer splits than average. |
| Units | Splits (tree depth). Comparable inside one stream, not across streams. |
| Cost | 2–3.3 ms per alarm, depending on the machine (RADAR 1.9, LIDAR 2.1 in a Linux sandbox; RADAR 3.3, LIDAR 3.2 on Abdalla's Windows laptop). At ~1% alarms, negligible. |

**Conversion (X2):** for each feature, `shap_value = −SHAP`. Then:
- `shap_value > 0` → the feature pushes **toward** the alarm → `direction = "positive"`;
- `shap_value ≤ 0` → it pulls **toward** normal → `direction = "negative"`;
- `sum(shap_value)` = base − E[h] = how many splits shorter than average this record's path is.

**Direction is not side.** `direction` says what a feature did to the alarm. Whether the value is
*above or below* normal is a different fact — read from `value − median` — and appears only in
the text ("far **above** normal"). A velocity far below normal still has `direction = positive`.

---

## 4. One stored shape

### 4.1 `xai_explanations` row

| Column | Value |
|---|---|
| `time` | Event time of the fused row (`fused_events.timestamp_ms` → TIMESTAMPTZ). Same value as the paired `anomaly_alerts.time`. |
| `fused_event_id` | The fused row's id |
| `shap_values` | JSONB array, **every** feature of the stream, sorted by `shap_value` descending: `[{"feature", "shap_value", "direction"}]`. `shap_value` rounded to 4 decimals. Empty array `[]` for TELEMETRY (Section 5.2). |
| `top_features` | JSONB array of **names only**, **up to 3**: the features with `shap_value > 0`, highest first. Can hold 1 or 2 — 116 of 388 RADAR and 12 of 375 LIDAR alarms have fewer than three features pushing toward the alarm. |
| `explanation_text` | Operator text (Section 6) |
| `model_version` | `combined-m7w28t1-v2` |
| `generated_at` | Time the explanation was written |

### 4.2 Fields on the paired `anomaly_alerts` row that this note defines

| Column | Value |
|---|---|
| `time`, `fused_event_id` | As above — the pair is joined on both |
| `source_type` | `fused_events.sensor_type` as stored (`RADAR`, `LIDAR`, `TELEMETRY`) |
| `anomaly_label`, `risk_score`, `confidence` | Copied from the scored fused row; `anomaly_label` is always 1 |
| `model_version` | `combined-m7w28t1-v2` |
| `status` | `active` on insert |
| `explanation_summary` | The first sentence of `explanation_text` — what the AI Alerts table shows in one line |

One alarm → exactly one `anomaly_alerts` row and one `xai_explanations` row. Non-alarm rows get
neither.

---

## 5. Per alarm source

`V2Scorer.score()` already returns a `reason` per row: `isolation_forest`, `zscore:<feature>` and
`rule:<name>`, joined with `+` when more than one fires.

### 5.1 RADAR and LIDAR — SHAP for every alarm (X1)

| Detector(s) fired | RADAR | LIDAR | Stored attribution | Text |
|---|---|---|---|---|
| Both | 270 | 275 | SHAP | SHAP lead + z-score sentence |
| Forest only | 44 | 84 | SHAP | SHAP lead |
| z-score only | 74 | 16 | SHAP | SHAP lead + z-score sentence |

**Why one method is safe:** SHAP's top feature was a feature the anomaly actually changed in
**100%** of alarms of every type (Section 8). When only the z-score fired, SHAP named the same
feature in 72 of 74 (RADAR) and 16 of 16 (LIDAR). The forest is explained even when it did not
fire on its own: its ranking still points at the changed feature.

**The z-score part is not an additive attribution** (corrects the M8 charter's wording). The
z-score detector scores a record by its single worst feature, `max(|value − median| / MAD)`, so
the attribution is winner-takes-all: one feature, no split across the others. `|z|` also drops
the sign — above or below normal comes from `value − median`. It is therefore used for one
exact sentence, not stored in `shap_values`.

**When SHAP and z name different features** — `ghost_target` (73 of 103 differ) and
`noise_burst` (63 of 100) — both are correct: those anomalies change 4–6 fields at once, and both
detectors always name one of them. The text leads with SHAP's feature and states the z-score
feature in its own sentence; nothing is hidden.

### 5.2 TELEMETRY — no SHAP

The TELEMETRY forest has one feature, `value_z`. `shap.TreeExplainer` raises `IndexError` on a
single-feature Isolation Forest (shap 0.54.1), and with one feature an attribution would be 100%
that feature anyway.

| Alarm source | `shap_values` | `top_features` | Text |
|---|---|---|---|
| `isolation_forest` and/or `zscore:value_z` only (186 of 380) | `[]` | `[<parameter_name>]`, e.g. `["cpu_temp_c"]` | Value sentence: parameter, reading, typical value, above / below |
| `rule:sequence_gap` | `[]` | `["sequence_number"]` | Template: readings missing between two sequence numbers |
| `rule:timestamp_not_advancing` | `[]` | `["timestamp_ms"]` | Template: timestamp did not advance |
| Rule and value together (2 of 380) | `[]` | Rule field, then parameter | Rule sentence first, then value sentence |

`top_features` uses the **parameter name**, not `value_z`, because the chip is read by an
operator. The dashboard's SHAP bar chart has nothing to draw for TELEMETRY; the panel shows the
text only (M9).

### 5.3 Ordering saturated alarms (input to M8W31T2)

About 78% of alarms have `risk_score` = 1.0 (RADAR 298, LIDAR 300, TELEMETRY 302), so they tie
(M7 Limit 5). For RADAR and LIDAR, `sum(shap_value)` separates them: 298 of 298 and 299 of 300
distinct. It is stored inside `shap_values`, so the tie-break needs no new column. TELEMETRY's
tie-break is M8W31T2's to settle.

---

## 6. Text structure (draft — wording finalised in M8W31T2)

```
<SENSOR> alarm: <feature> is far <above|below> normal (<value>; typical <median>).
[Also contributing: <feature 2>[, <feature 3>].]
[z-score check: <z feature> is <z> times its normal spread <above|below> typical.]
[<rule sentence>]
```

- The first sentence becomes `explanation_summary`.
- Feature names are shown as stored until M8W31T2 maps each feature to a plain cause per sensor —
  including the derived LIDAR features (`log_point_count` ← point count;
  `centroid_range_ratio` ← centroid distance ÷ max range).
- Numbers: values to 2 decimals with units where the feature has one; z to 1 decimal.

---

## 7. Worked example — RADAR `velocity_spike`

Test record `f35f7db0-6e34-4c9e-a9b7-2cdafd71db3f`.

**Scored:** `risk_score` 1.0, `confidence` 1.0, `reason` = `isolation_forest+zscore:velocity_ms`.

| Feature | Value | Median | z | SHAP (raw) | `shap_value` (−SHAP) | `direction` |
|---|---|---|---|---|---|---|
| `velocity_ms` | 1,400.68 | 100.25 | 13.0 | −3.0813 | **3.0813** | positive |
| `bearing_deg` | 3.22 | 181.20 | 2.0 | −0.9006 | **0.9006** | positive |
| `signal_strength_db` | −76.21 | −55.34 | 1.2 | 0.1637 | −0.1637 | negative |
| `range_m` | 3,150.81 | 2,538.39 | 0.5 | 0.1682 | −0.1682 | negative |
| `elevation_deg` | 9.99 | −0.07 | 0.7 | 0.2504 | −0.2504 | negative |

Check: base 11.4053 − E[h] 8.0057 = **3.3996** = sum of `shap_value`. Only two features push
toward the alarm, so `top_features` holds two.

**`xai_explanations` row:**
```json
{
  "fused_event_id": "<the fused row's id>",
  "shap_values": [
    {"feature": "velocity_ms",        "shap_value":  3.0813, "direction": "positive"},
    {"feature": "bearing_deg",        "shap_value":  0.9006, "direction": "positive"},
    {"feature": "signal_strength_db", "shap_value": -0.1637, "direction": "negative"},
    {"feature": "range_m",            "shap_value": -0.1682, "direction": "negative"},
    {"feature": "elevation_deg",      "shap_value": -0.2504, "direction": "negative"}
  ],
  "top_features": ["velocity_ms", "bearing_deg"],
  "explanation_text": "RADAR alarm: velocity_ms is far above normal (1400.68 m/s; typical 100.25 m/s). Also contributing: bearing_deg. z-score check: velocity_ms is 13.0 times its normal spread above typical.",
  "model_version": "combined-m7w28t1-v2"
}
```
**`anomaly_alerts.explanation_summary`:** `RADAR alarm: velocity_ms is far above normal
(1400.68 m/s; typical 100.25 m/s).`

This is the example M8W29T5 puts into `api_contracts_final.md` Section 10.

---

## 8. Evidence — explanation names a changed feature

Changed features per type from `scripts/generators/anomaly_injection.py`, mapped onto model
features. Test-set alarms of each type.

| Stream | Type | Alarms | SHAP top-1 changed | z top-1 changed | Same feature |
|---|---|---|---|---|---|
| RADAR | `velocity_spike` | 94 | 94 | 94 | 94 |
| RADAR | `sensor_dropout` | 100 | 100 | 100 | 100 |
| RADAR | `ghost_target` | 103 | 103 | 103 | 30 |
| LIDAR | `point_cloud_dropout` | 97 | 97 | 97 | 97 |
| LIDAR | `ghost_point` | 100 | 100 | 100 | 99 |
| LIDAR | `noise_burst` | 100 | 100 | 100 | 37 |

This is a design check, not M8W31T1's fidelity measurement — that runs on `xai.py`'s real output
and reports per type, as measured.

---

## 9. What an explanation does not prove

- **The top feature is what made the model alarm — not the physical cause.** "velocity far above
  normal" says why the record looks unusual, not why the sensor produced it.
- **The 100% match is on synthetic anomalies** that sit far outside normal by construction.
  Real faults will be subtler and the match lower (M7 Limits 1–2).
- **Per sensor only.** An explanation covers one sensor record; nothing crosses sensors
  (`open_items_m6.md` Item 14).
- **Alarms on normal records are explained too.** 91 RADAR and 78 LIDAR test alarms are false;
  they still get a confident-looking explanation.

---

## 10. Agreed with Beyza — Wednesday 25 November checkpoint

For M8W29T4 and M8W29T5:

- [ ] `xai_explanations`: columns as Section 4.1; key `(time, fused_event_id)`; `shap_values`
      and `top_features` JSONB NOT NULL — `[]` is valid for `shap_values`
- [ ] `anomaly_alerts`: fields as Section 4.2; `explanation_summary` filled on insert
- [ ] `model_version` stays `VARCHAR(20)` in both tables
- [ ] `direction` enum stays `positive` / `negative`, defined as Section 3
- [ ] Contract Section 10: the example from Section 7; `shap_values` described as sorted, every
      feature; `top_features` as up to 3 names
- [ ] `dashboard_data_fields` XAI panel: row 10 field `shap_values.shap_value`; row 11 colour by
      meaning — `positive` (toward alarm) red, `negative` green; row 8 "up to 3"

---

## 11. Handed to Week 30 (M8W30T1)

`xai.py` must pass tests for:
1. Additivity: `sum(shap_value)` = base − E[h] within 1×10⁻⁶ for RADAR and LIDAR.
2. Sign: every alarm in the test set has `sum(shap_value) > 0`.
3. Shape: every feature present, sorted descending; `top_features` = positive features only, ≤ 3.
4. TELEMETRY never calls `TreeExplainer`; rule alarms produce the template text.
5. The worked example in Section 7 reproduces exactly.
6. `model_version` ≤ 20 characters.

---

## 12. Reproduce

```bash
python services/ml/model_v2.py train     # rebuilds the gitignored .joblib models
python services/ml/xai_probe.py          # Sections 3, 5 and 8
```
`shap==0.54.1` is needed locally (`pip install shap==0.54.1`); M8W29T8 adds it to
`services/ml/requirements.txt`.
