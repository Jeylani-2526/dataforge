# DataForge — Docker/Infrastructure Configuration-Consistency Verification

**Task:** M5W19T4
**Owner:** Abdullah (reassigned from Ömer this week — see Week 19 plan's Planning note)
**Milestone:** M5 · Week 19
**Scope:** Kafka (KRaft), Spark, and sensor-generators configuration consistency across
`docker-compose.yml`, `.env.example`, and each service's actual runtime behavior —
following the M4W16T5 format.
**Status:** No functional bugs found in the three in-scope services' core configuration.
One dead config value confirmed (`EVENTS_PER_SECOND`), one config gap fixed earlier this
week (`SENSOR_PUBLISH_INTERVAL_MS`), and one undocumented-but-real Compose profile
behavior found, live-tested, and now documented.

---

## 1. Kafka (KRaft) — static review

| Item | Value | Consistent? |
|---|---|---|
| `KAFKA_LISTENERS` | `PLAINTEXT://kafka:29092,CONTROLLER://kafka:29093,PLAINTEXT_HOST://0.0.0.0:9092` | Source of truth |
| `KAFKA_ADVERTISED_LISTENERS` | `PLAINTEXT://kafka:29092,PLAINTEXT_HOST://localhost:9092` | Matches — container-internal traffic advertises `kafka:29092`, host traffic advertises `localhost:9092` |
| `spark-processor` / `sensor-generators` / `alice-ingestion` `KAFKA_BOOTSTRAP_SERVERS` | `kafka:29092` (all three) | Matches the internal listener |
| `kafka-ui` `KAFKA_CLUSTERS_0_BOOTSTRAPSERVERS` | `kafka:29092` | Matches (kafka-ui runs inside the Docker network too) |

No remaining mismatch — this is the KRaft migration (previously fixed in `0b2c44a`,
`887ddaa`, `a2c9798`) holding correctly. Confirmed by static review here; already
confirmed live and healthy throughout M5W19T1/T2's runs.

---

## 2. Spark — static review

Every environment variable `spark_consumer.py` actually reads is set consistently:

| Variable | `docker-compose.yml` | `.env.example` | Read by code? |
|---|---|---|---|
| `KAFKA_BOOTSTRAP_SERVERS` | `kafka:29092` | n/a (container-internal) | ✅ |
| `KAFKA_TOPIC_ALICE` / `_RADAR` / `_LIDAR` / `_TELEMETRY` | hardcoded, matches | ✅ present | ✅ |
| `DB_HOST` / `DB_PORT` | `timescaledb` / `5432` | n/a (container-internal — same pattern M4W16T5 already confirmed for `DB_PORT`) | ✅ |
| `DB_NAME` / `DB_USER` / `DB_PASSWORD` | `${POSTGRES_*}` | ✅ present | ✅ |
| `WATERMARK_DELAY_SECONDS` | `${WATERMARK_DELAY_SECONDS:-5}` | ✅ present | ✅ |
| `ALICE_SCHEMA_PATH` / `SENSOR_SCHEMA_PATH` | not set anywhere | not set | Defaults to `/app/schemas/alice_event_schema_v1.avsc` / `/app/schemas/sensor_schema_v1.avsc` — verified these filenames exist exactly as named in `schemas/`, and match the `./schemas:/app/schemas` volume mount |

`pyspark==3.5.9` (`services/streaming/spark/requirements.txt`) matches the
`SPARK_KAFKA_PACKAGE`/`SPARK_AVRO_PACKAGE` version strings (`3.5.9`) hardcoded in
`spark_consumer.py` — checked because a Spark/Scala-vs-PySpark version mismatch is a
common, silent source of Kafka connector failures. No mismatch.

---

## 3. sensor-generators — static review, one thing worth knowing

Every variable in `docker-compose.yml`'s `sensor-generators` block matches what
`sensor_producer.py` reads, with one exception (below). New finding this task:
`infrastructure/docker/sensor-generators.Dockerfile` **also** bakes its own `ENV`
defaults directly into the image:

```dockerfile
ENV KAFKA_BOOTSTRAP_SERVERS=kafka:29092
ENV KAFKA_TOPIC_RADAR=sensor-radar
ENV KAFKA_TOPIC_LIDAR=sensor-lidar
ENV KAFKA_TOPIC_TELEMETRY=sensor-telemetry
ENV SENSOR_PUBLISH_INTERVAL_MS=200
ENV SENSOR_SCHEMA_PATH=/app/schemas/sensor_schema_v1.avsc
```

So there are three layers with defaults for these values: the Dockerfile's `ENV`,
`docker-compose.yml`'s `environment:` (which overrides the Dockerfile at container
start), and the Python code's own `os.environ.get(..., "200")` fallback. All three
currently agree — not a bug — but noted so a future change to one of these doesn't
silently diverge from the other two.

**Confirmed dead config:** `EVENTS_PER_SECOND` is declared in `docker-compose.yml` and
`.env.example`, but absent from this Dockerfile too and never read anywhere in
`sensor_producer.py`. Surfaced during M5W19T2's benchmark planning; recorded formally
here as this task's own finding. Not fixed this week — flagged as a follow-up
(either wire it up as a genuine records/sec rate limiter, or remove it so it stops
implying a control that doesn't exist).

**Fixed earlier this week:** `SENSOR_PUBLISH_INTERVAL_MS` was missing from
`docker-compose.yml`'s `environment:` block entirely — the Dockerfile `ENV` and the
code's own default both happened to agree at `200`, so nothing was visibly broken, but
there was no way to override it through Compose. Added ahead of M5W19T2 so the
benchmark's throttle-removal could actually reach the container. Confirmed still
present and correct.

**Minor, non-blocking:** `spark.Dockerfile` uses `python:3.11-slim`;
`sensor-generators.Dockerfile` uses `python:3.12-slim`. Not a bug — each container is
isolated — flagged only in case the version difference isn't intentional.

---

## 4. Compose profile behavior — tested live, not assumed

Every module service carries exactly one `profiles:` tag matching its own milestone
(`sensor-generators`: `m3-and-above`; `adaptation-layer`: `m4-and-above`;
`alice-ingestion` / `spark-processor`: `m5-and-above`). Profile tags aren't
hierarchical in Compose — activating `m5-and-above` does not imply `m3-and-above` is
also active. This exact gap caused M5W19T1's first bring-up attempt to follow the Week
19 plan's own suggested command (`--profile m5-and-above` alone) and silently omit the
sensor generators — caught and corrected before it caused a false "only ALICE is
flowing" reading.

**Tested directly, live, rather than assumed:**

```
$ docker compose down
[all 5 running containers removed cleanly]

$ docker compose up -d sensor-generators
 ✔ Container dataforge-kafka             Healthy    19.5s
 ✔ Container dataforge-sensor-generators Started    19.6s

$ docker compose ps
NAME                          STATUS
dataforge-kafka               Up 40 seconds (healthy)
dataforge-sensor-generators   Up 22 seconds
```

**Finding:** naming a service explicitly on the command line (`docker compose up -d
sensor-generators`) starts it regardless of its `profiles:` tag — **no `--profile` flag
required at all.** `kafka` started automatically as `sensor-generators`'s declared
dependency (`depends_on: condition: service_healthy`) — correct, and unrelated to the
profile question itself. `timescaledb`, `kafka-ui`, `adminer` correctly stayed down,
since nothing named them and nothing running depended on them.

**Consequence:** the `--profile m3-and-above --profile m5-and-above` flags used in
every runbook this week (M5W19T1, M5W19T2) were not actually load-bearing — they
worked because services were always named explicitly alongside them. **The real risk is
specifically a bare `docker compose up` with no service names**, relying on
`--profile` flags alone — exactly the form the Week 19 plan's own original command
took. That form genuinely does miss unlisted-profile services.

**Recommendation:** document both correct patterns explicitly for the team, rather than
leave this as tribal knowledge:
- Naming services explicitly (as this week's runbooks did) → profiles don't need to be
  passed at all.
- Using bare `docker compose up` with no service names → every applicable
  `--profile` flag must be passed, cumulatively, for every milestone tag up to and
  including the one you want (e.g., `--profile m3-and-above --profile m4-and-above
  --profile m5-and-above` for the current full M5 stack).

---

## 5. Conclusion

- **Kafka and Spark configuration: fully consistent**, static review and (via M5W19T1/T2)
  live-verified — no changes needed.
- **sensor-generators: one dead config value found** (`EVENTS_PER_SECOND`, follow-up
  flagged, not fixed this week), **one gap already fixed** this week
  (`SENSOR_PUBLISH_INTERVAL_MS`), and a three-layer-default pattern documented so it
  doesn't silently drift in the future.
- **Compose profile behavior tested live, not assumed** — explicit service naming
  bypasses profile gating; the actual risk is scoped precisely to bare `docker compose
  up` without service names, and a correct-usage reference is now written down instead
  of left implicit.
