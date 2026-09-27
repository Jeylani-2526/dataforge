### Docker Compose Verification

The core Dataforge infrastructure services were verified successfully.

Running:

`docker compose ps`

confirmed that the following services were running:

* `dataforge-kafka` — **Up / Healthy**
* `dataforge-timescaledb` — **Up / Healthy**
* `dataforge-kafka-ui` — **Up**
* `dataforge-adminer` — **Up**

The Kafka KRaft metadata quorum was also verified using:

`docker exec dataforge-kafka kafka-metadata-quorum --bootstrap-server localhost:9092 describe --status`

The command returned a valid cluster state with `LeaderId: 1`, `CurrentVoters: [1]`, and `MaxFollowerLag: 0`, confirming that the Kafka quorum was operational.

### Alice Ingestion Verification

Starting the Alice ingestion service directly with:

`docker compose up -d alice-ingestion`

completed successfully. Docker reported:

* `dataforge-kafka` — **Healthy**
* `dataforge-timescaledb` — **Healthy**
* `dataforge-alice-ingestion` — **Started**

This confirms that the `alice-ingestion` service itself can be built/started with its required dependencies.

### M5-and-Above Profile Issue

Running the complete profile with:

`docker compose --profile m5-and-above up -d`

currently fails during the build phase with:

`resolve : GetFileAttributesEx C:\Users\asus\dataforge\services\infrastructure: The system cannot find the file specified.`

The failure occurs while Docker attempts to build the profile images (`dataforge-alice-ingestion` and `dataforge-spark-processor`). Since `alice-ingestion` starts successfully when invoked directly, the issue appears to be specific to the `m5-and-above` profile/build configuration or one of its referenced build paths, rather than a general failure of the Alice ingestion service.

The Docker Compose warning concerning the obsolete `version` attribute is non-blocking and does not prevent the verified services from starting.
