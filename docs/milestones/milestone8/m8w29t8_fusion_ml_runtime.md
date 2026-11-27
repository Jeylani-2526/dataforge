# M8W29T8 — ML Runtime in the Fusion Image

**Owner:** Abdalla (reassigned from Omer's M8W30T5 and pulled forward one week)
**Milestone:** M8 · Week 29 · Task M8W29T8
**Date:** 26 November 2026
**Status:** Complete — verified on Abdalla's machine on 26 November 2026
**Used by:** M8W30T2 (live scoring and explanations in the fusion write path)

---

## Summary

- The fusion container can now load model v2 and run SHAP: all three streams pass
  `runtime_check.py` inside the container, with SHAP values identical to the host.
- **shap is pinned to 0.51.0, not 0.54.1.** shap 0.52 and later require Python 3.12; the fusion
  image runs Python 3.11, the last version PySpark 3.5.9 officially supports. 0.51.0 gives
  identical SHAP values.
- **CI moves from Python 3.10 to 3.11** — no shap release that works with the model installs on
  3.10. The full CI test suite passes on 3.11 (59 passed, 1 skipped).
- **Cost:** image 1.2 GB → 1.98 GB on disk (453 MB → 631 MB content).
- Fusion still writes rows on the new image — after a checkpoint reset caused by
  `open_items_m6.md` Item 11, which recurred during this check (Section 5.2).
- Nothing is scored live yet. That is M8W30T2.

---

## 1. What Changed

| File | Change |
|---|---|
| `services/fusion/requirements.txt` | Adds `numpy>=2.0,<3`, `scikit-learn==1.7.2`, `joblib>=1.4`, `shap==0.51.0` — the same pins as `services/ml` |
| `services/ml/requirements.txt` | Adds `shap==0.51.0` (M8W30T1's tests) |
| `docker-compose.yml` (fusion-engine) | Mounts `./services/ml` read-only at `/app/services/ml`; sets `PYTHONPATH=/app/services/ml` |
| `.github/workflows/ci.yml` | `python-version` 3.10 → 3.11 in the lint and test jobs |
| `services/ml/runtime_check.py` (new) | In-container proof: loads each stream's model, scores a typical and an extreme record, runs SHAP |
| `docs/milestones/milestone8/m8w29t1_xai_design.md` | Amended: shap 0.51.0 |
| `services/ml/xai_probe.py` | One message no longer names a shap version |

**No Dockerfile change.** The model code and the trained models reach the container through the
mount, not a copy:

- `model_v2.py` imports its neighbours directly (`import baseline`) → `PYTHONPATH`.
- `model_v2.py`, `isolation_forest.py` and `feature_assembly.py` read paths relative to the repo
  root (`services/ml/artifacts`). Mounted at `/app/services/ml` with `WORKDIR /app`, they resolve
  unchanged.
- The mount is read-only: nothing in the scoring path writes into `services/ml`.

**Before fusion can score**, each machine trains the models once on the host — the `.joblib`
files are gitignored:
```bash
python services/ml/model_v2.py train
```

---

## 2. Version Decision

| | Python needed | Fusion image (3.11) | CI before (3.10) | CI after (3.11) |
|---|---|---|---|---|
| shap 0.54.1 | ≥ 3.12 | ✗ will not install | ✗ | ✗ |
| **shap 0.51.0** | ≥ 3.11 | ✓ | ✗ | ✓ |

PySpark 3.5.9 lists Python 3.8–3.11. Moving the image to Python 3.12 to keep shap 0.54.1 was
rejected: an unsupported PySpark runtime under the streaming path the milestone depends on.

Decided by Abdalla on 25 November 2026: pin shap 0.51.0; CI to Python 3.11; amend the T1 note.

---

## 3. Equivalence — Checked Before Building

On Python 3.11 / Linux x86_64 with the fusion image's exact package set (sandbox; Docker Hub was
not reachable there, so the real build is Section 4):

| Check | Result |
|---|---|
| Packages install together | ✓ pyspark 3.5.9, numpy 2.4.6, scikit-learn 1.7.2, shap 0.51.0 |
| Raw SHAP values, 0.51.0 vs 0.54.1 | Identical — maximum difference 0.0 |
| `xai_probe.py` figures | Every figure in the T1 note identical |
| Single-feature TELEMETRY forest | `TreeExplainer` raises `IndexError` in both versions — handled by design (T1 Section 5.2) |
| Spark local job with numpy 2.4, pandas 3.1, numba present | Runs normally |
| CI test suite on Python 3.11 with shap installed | 59 passed, 1 skipped |

shap 0.51.0 pulls in `numba`, `llvmlite` and pandas 3.1. Fusion uses no pandas UDFs and no
`toPandas()`, so pandas 3 does not reach the Spark path.

---

## 4. Verification on Abdalla's Machine — 26 November 2026

### 4.1 Build (`--no-cache`)

| Step | Time |
|---|---|
| Java (`apt-get`) | 35.3 s |
| `pip install` | 182.3 s — of which the pyspark download is ~70 s and the new ML packages ~40 s of downloads plus install |
| Export to image | 67.2 s |
| **Total** | **4 min 53 s** |

The "before" build ran the same morning (image created 10:30) but its timings were not captured.

| | Before (unchanged `develop`) | After (M8W29T8) | Change |
|---|---|---|---|
| Image on disk | 1.2 GB | 1.98 GB | +0.78 GB |
| Content size | 453 MB | 631 MB | +178 MB |

### 4.2 Packages in the image

`joblib 1.6.0 · numpy 2.4.6 · pyspark 3.5.9 · scikit-learn 1.7.2 · shap 0.51.0`

### 4.3 Runtime check inside the container

```
python 3.11.18  numpy 2.4.6  scikit-learn 1.7.2  joblib 1.6.0  shap 0.51.0
model_version expected combined-m7w28t1-v2
OK    radar     loaded  typical -> label 0  extreme -> label 1 (isolation_forest+zscore:range_m)  SHAP push 7.2339, top velocity_ms
OK    lidar     loaded  typical -> label 0  extreme -> label 1 (isolation_forest+zscore:centroid_y_m)  SHAP push 8.3406, top centroid_y_m
OK    telemetry loaded  typical -> label 0  extreme -> label 1 (isolation_forest+zscore:value_z)  SHAP skipped (single feature, by design)
```

The models were trained on the Windows host (Python 3.12, numpy 2.2) and loaded in the Linux
container (Python 3.11, numpy 2.4). The output is identical, value for value, to the sandbox run.

### 4.4 Fusion still writes rows

After the checkpoint reset in Section 5.2, on the new image:

| | Value |
|---|---|
| `fused_events` before restart | 49,183 |
| `fused_events` after restart | 49,456, still rising |
| Micro-batches 74–76 | 10 written, 0 rejected, 0 duplicates each; `data_loss_pct` 0.0000% |
| Alignment, cumulative n = 801 | p50 50 ms, p95 96 ms, max 103 ms |

Counted by SQL through `docker exec`.

---

## 5. Findings During Verification

### 5.1 Truncated pyspark download

The first `--no-cache` build failed in `pip install`: the 318 MB pyspark download stopped at
127 MB on a slow connection (~345 kB/s), and pip rejected it on the hash check. pyspark was
already in the image before this task; a retry on a stable connection succeeded. Not caused by
M8W29T8, but every `--no-cache` build carries the risk.

### 5.2 `open_items_m6.md` Item 11 recurred

On the first start, fusion stopped with `OffsetOutOfRangeException` on `sensor-radar-0`: its
checkpoint held an offset (4,706,503) that Kafka's 7-day retention had deleted. The container
exited with **code 0**, so nothing restarted it. Both halves of Item 11, unchanged since
M6W26T4.

Recovered with the M6W21T2 procedure — container removed, `dataforgerepo_fusion-checkpoints`
deleted, fusion restarted. `startingOffsets` is `latest`, so messages still in Kafka from before
the reset were not fused. The fix is M8W30T3.

### 5.3 Heartbeat reports `critical` at 0% data loss

Seen in the fusion logs, unrelated to this task: `open_items_m6.md` Item 6 (heartbeat contract,
mismatch 3), Beyza, M9.

---

## 6. Not Done Here

- Scores and explanations are not written by fusion — **M8W30T2**.
- The `services/ai-ml` stubs and the `anomaly-detection` / `xai-service` compose blocks remain —
  Omer's **M8W30T5**, now without the ML-dependency part.
- CI still builds no image (`docker compose config` only) — `open_items_m7.md` Item 11.

---

## 7. Reproduce

```bash
python services/ml/model_v2.py train
docker compose --profile m6-and-above build --no-cache fusion-engine
docker compose --profile m6-and-above run --rm --no-deps --entrypoint pip fusion-engine list
docker compose --profile m6-and-above run --rm --no-deps --entrypoint python \
    fusion-engine services/ml/runtime_check.py
```
