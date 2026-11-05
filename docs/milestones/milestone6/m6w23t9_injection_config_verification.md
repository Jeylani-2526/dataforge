# M6W23T9 — Injection Configuration, Default-Off Proof & Build Verification

**Week:** M6W23  **Task:** T9  **Executed by:** Abdalla
**Date:** 15 October 2026  **Branch:** develop

## Ownership note

T9 was planned for Omer. It was carried out by the project lead, together with
T3 which was also reassigned. The task's final requirement was worded as
confirming the build on a second machine; what is recorded here is verification
on the **lead's machine only**. Cross-machine verification has not been
performed, and this note states that rather than implying wider coverage.

## Scope

Four parts: wire the injection environment variables through Compose, prove the
mode is genuinely off by default so existing benchmarks stay comparable, run one
injected configuration end to end, and confirm the m6-and-above stack still
builds and runs.

## 1. Compose wiring — complete

Six variables added to the `sensor-generators` service in `docker-compose.yml`,
each defaulting to `0` (or empty for the seed), plus `WATERMARK_DELAY_SECONDS`
shared with `fusion-engine` so both sides use one definition of "late":

```
SENSOR_LATE_FRACTION, SENSOR_LATE_MIN_MS, SENSOR_LATE_MAX_MS,
SENSOR_DISORDER_FRACTION, SENSOR_DISORDER_BUFFER, SENSOR_INJECTION_SEED
```

`.env.example` documents all six plus `FUSION_PROGRESS_DEBUG`.

No Dockerfile change was needed: `sensor-generators.Dockerfile` already copies
the whole `src/` directory, so `injection.py` is picked up automatically.

## 2. Default-off — proven three ways

**At config level**, Compose resolves the variables without a `.env` entry:

```
SENSOR_LATE_FRACTION=0      SENSOR_LATE_MIN_MS=0     SENSOR_LATE_MAX_MS=0
SENSOR_DISORDER_FRACTION=0  SENSOR_DISORDER_BUFFER=0 SENSOR_INJECTION_SEED=
```

**At runtime**, the producer states it on startup:

```
Injection mode OFF — records published unmodified.
```

**At code level**, when injection is off no `timestamp` argument is passed to
`producer.produce()` at all — the call is identical to the pre-injection code
path, not merely passing a zero. The injector also uses a private random number
generator, so enabling it cannot alter generated sensor values; an injected run
stays comparable with an ordinary one.

## 3. Injected configuration through the service definition — complete

Earlier M6W23T4 phases used one-off `docker compose run` containers. This test
exercises the committed service definition instead:

```
SENSOR_LATE_FRACTION=0.1 SENSOR_LATE_MIN_MS=30000 SENSOR_LATE_MAX_MS=30000 \
  docker compose up -d --force-recreate sensor-generators
```

```
Injection mode ON — late_fraction=0.1 delay=30000-30000ms
(watermark line 5000ms) | disorder_fraction=0.0 buffer=0 | seed=None
```

Recreating without the overrides returned the service to `Injection mode OFF`,
confirming the configuration path is reversible and leaves no residue.

## 4. Build verification — complete, with a finding

Full stack built and started from a stopped state: **14 of 14 services up**,
`timescaledb` and `kafka` both healthy.

### Finding — the Week 23 plan is wrong about profiles

The plan states that `--profile m6-and-above` brings up the ALICE producer, three
sensor producers, spark-processor and fusion-engine. It does not. Tested
directly, that profile alone started only:

```
kafka, timescaledb, kafka-ui, adminer, fusion-engine
```

No producers and no spark-processor — a fusion engine with nothing feeding it.
Profiles do **not** cascade, exactly as the comment at the top of
`docker-compose.yml` warns. The working invocation stacks all four:

```bash
docker compose --profile m3-and-above --profile m4-and-above \
               --profile m5-and-above --profile m6-and-above up -d --build
```

Week 24 should correct the plan's wording, since following it as written
produces a silently idle stack rather than an error.

## 5. Finding — empty values swallow trailing comments in .env

Found while verifying the wiring, and it had real consequences.

Docker Compose does not strip a trailing comment when the value is **empty**:

```
SENSOR_INJECTION_SEED=      # Optional seed     ->  value becomes "# Optional seed"
```

The sensor producer then called `int()` on that string and exited at startup,
taking the container with it. Two fixes applied:

1. `.env.example` moves such comments to their own line, with a note explaining
   why.
2. `injection.py` no longer treats an unparseable seed as fatal — it warns and
   runs unseeded, because the seed only matters when injection is on and a
   malformed value must never stop the producer.

**The same pattern pre-dates this week on `SPARK_STARTING_TIMESTAMP_MS`**, which
is declared the same way in `.env.example`. `spark_consumer.py` treats any
non-empty value as a replay timestamp and passes it to Kafka, so a `.env` copied
from the template would supply a comment string as a replay start. The variable
only applies when a query starts without a checkpoint, which is why this has
never surfaced — all current queries have checkpoints. Fixed in `.env.example`;
anyone with an older `.env` should check their own copy.

## Status

| Part | Result |
|---|---|
| Compose wiring | Complete |
| Default-off proof | Complete — config, runtime and code level |
| One injected run through the service definition | Complete |
| m6-and-above build and run | Complete on the lead's machine |
| Cross-machine verification | Not performed |

Two findings raised: the plan's profile assumption, and the empty-value comment
bug including its pre-existing instance.
