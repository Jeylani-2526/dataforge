# M5W20T11 Build Verification

## Original Issue

The command:

`docker compose --profile m5-and-above up -d`

previously failed on my local Windows development environment due to a Docker Compose build-context/path-related error involving `services\infrastructure`.

The same repository state was reported to work on another developer's machine, suggesting that the issue could be related to my local Docker environment rather than a repository-wide defect.

## Investigation

To rule out stale Docker build cache as a possible cause, I rebuilt all buildable services belonging to the `m5-and-above` profile without using the existing Docker build cache:

`docker compose --profile m5-and-above build --no-cache`

Docker successfully located and processed the Dockerfiles for both `alice-ingestion` and `spark-processor`.

The complete no-cache build finished successfully:

- `dataforge-alice-ingestion` — Built
- `dataforge-spark-processor` — Built
- Overall build result — 2/2 images built successfully

The previously observed build-context/path error did not occur during the clean rebuild.

## Root Cause / Finding

The successful clean rebuild indicates that the Dockerfiles and build contexts required by the `m5-and-above` profile are valid and accessible from the current local checkout.

Since the same repository state worked on another developer's machine and the issue disappeared after rebuilding the profile without Docker's existing build cache, the previous failure is consistent with stale or inconsistent local Docker build state rather than a reproducible repository defect.

No repository-level path correction was required to reproduce a successful build.

## Resolution

The affected services were rebuilt from scratch with:

`docker compose --profile m5-and-above build --no-cache`

After the clean build completed successfully, the complete profile was started with:

`docker compose --profile m5-and-above up -d`

Docker Compose reported:

`[+] up 7/7`

The network was created successfully and all expected containers started. Kafka and TimescaleDB passed their configured health checks.

## Final Stack Verification

The running stack was verified with:

`docker compose --profile m5-and-above ps`

The following services were confirmed running:

- `dataforge-adminer` — Up
- `dataforge-kafka` — Up (healthy)
- `dataforge-kafka-ui` — Up
- `dataforge-spark` — Up
- `dataforge-timescaledb` — Up (healthy)
- `dataforge-alice-ingestion` — Started successfully as part of the profile startup

The `m5-and-above` Docker Compose stack is therefore confirmed operational on my local machine. All services started successfully, and services with configured Docker health checks reported healthy status.

## Additional Note

Docker Compose reports that the top-level `version` attribute in `docker-compose.yml` is obsolete and ignored. This warning does not prevent the stack from building or starting, but the obsolete attribute can be removed separately to avoid future confusion.