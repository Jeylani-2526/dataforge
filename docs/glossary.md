# DataForge — Project Glossary

> **Living Document** — Updated at every milestone as new concepts are introduced.  
> **v1.0 · Milestone 1 · June 2026**  
> All definitions are written in plain language accessible to non-specialist reviewers.


## Quick Navigation

[A](#a) · [D](#d) · [E](#e) · [F](#f) · [H](#h) · [I](#i) · [K](#k) · [O](#o) · [P](#p) · [R](#r) · [S](#s) · [T](#t) · [W](#w) · [X](#x)

---

## A

### ALICE
*A Large Ion Collider Experiment*

One of the four major physics experiments at CERN's Large Hadron Collider, designed to study matter under extreme temperature and density by analysing heavy-ion collisions. ALICE produces millions of particle collision events per second, each described by position, momentum, and energy measurements. DataForge adapts the ALICE O² data processing architecture as the engineering blueprint for its own real-time pipeline.

---

### Anomaly Detection

The process of identifying events or data points that deviate significantly from expected or normal behaviour. In DataForge, anomaly detection is performed by a machine learning model (Isolation Forest) applied to fused sensor and ALICE-like records. Detected anomalies are assigned a risk score and routed as alerts to the operator dashboard.

---

### AUC
*Area Under the ROC Curve*

A performance metric for classification models measuring how well the model distinguishes between anomalous and normal events, on a scale from 0.5 (random guessing) to 1.0 (perfect separation). The DataForge prototype targets AUC ≥ 0.85, meaning the model correctly ranks a randomly chosen anomaly above a randomly chosen normal event at least 85% of the time. A higher AUC means fewer missed anomalies and fewer false alarms.

---

### Avro

A compact binary serialisation format that stores data together with an embedded schema, enabling efficient streaming and backward-compatible schema evolution. DataForge uses Avro to serialise all events flowing through Kafka topics, with schemas stored in a Schema Registry. Avro's evolution rules allow new optional fields to be added across milestones without breaking existing pipeline consumers.

---

## D

### Docker Compose

A tool for defining and running multi-container Docker applications from a single YAML configuration file. DataForge uses Docker Compose to launch the entire prototype stack — Kafka, Zookeeper, PySpark, TimescaleDB, FastAPI, and the ReactJS dashboard — with a single `docker-compose up` command. This ensures every team member can reproduce the full prototype environment on their laptop, regardless of operating system.

---

## E

### Event

The fundamental unit of data in DataForge: a single timestamped observation produced by either the ALICE-like data source or a synthetic sensor (radar, LIDAR, or telemetry). Each event carries core fields — `event_id`, `timestamp_ms`, `source_type`, `energy`, and sensor-specific readings — and flows through all 10 pipeline modules from ingestion to the dashboard. All pipeline throughput metrics are measured in events per second.

---

## F

### FPR
*False Positive Rate*

The proportion of normal events that the AI model incorrectly classifies as anomalous. A high FPR floods operators with false alerts, eroding trust in the system. The DataForge prototype targets FPR ≤ 5%, meaning no more than 5 in every 100 normal events will be incorrectly flagged.

---

### Fusion

The process of combining related events from two or more data sources — ALICE-like and sensor streams — into a single unified record using a shared timestamp and a configurable time window. A fused record contains fields from both source types, enabling the AI model to reason across data streams simultaneously. Fusion is performed by Module 6 (Data Fusion Layer) using PySpark's stream-stream join on a confirmed 2-second tumbling window.

---

## H

### Hypertable

A TimescaleDB-specific table type that automatically partitions time-series data into time-based chunks to maintain fast query performance as data volume grows. All time-stamped data in DataForge — events, anomaly alerts, SHAP explanations, and system performance metrics — is stored in hypertables. Standard SQL queries work on hypertables; TimescaleDB transparently routes each query to the relevant time chunk.

---

## I

### Isolation Forest

A machine learning algorithm for anomaly detection that works by randomly partitioning data and measuring how many splits are needed to isolate a single record. Anomalous records are isolated quickly (few splits required) and receive a high anomaly score; normal records require many splits and receive a low score. DataForge uses the scikit-learn implementation of Isolation Forest as the required baseline model for Module 7, targeting AUC ≥ 0.85.

---

## K

### Kafka Partition

A subdivision of a Kafka topic that enables parallel reading and writing. Each partition is an ordered, append-only log; messages within a partition are always read in the order they were written, but multiple partitions in the same topic allow multiple consumers to read simultaneously. DataForge uses partitioning to let PySpark's Structured Streaming workers process events from different partitions in parallel, increasing throughput.

---

### Kafka Topic

A named, durable channel in Apache Kafka through which producers write messages and consumers read them. DataForge uses four main topics: `alice_events`, `sensor_events`, `fused_events`, and `anomaly_events` — each representing a data stage in the pipeline. Topics retain messages for a configurable period, allowing any consumer to replay data from any past offset, which is essential for debugging and late-start recovery.

---

## O

### O²
*CERN ALICE Online-Offline Computing System*

CERN's data acquisition and processing framework for the ALICE experiment, designed to handle millions of particle collision events per second across a distributed cluster of processing nodes. O² separates real-time online processing (at the detector) from offline scientific analysis (batch computation), using a multi-stage pipeline architecture with strict inter-module contracts. DataForge adapts O²'s event-driven pipeline design pattern for defence and industrial sensor data processing.

---

## P

### Parquet

A columnar storage file format optimised for efficient analytical queries on large datasets. DataForge writes adapted and fused events to Parquet files at each processing stage for persistent storage and AI/ML training data preparation. Columnar format means only the specific columns needed for a query or model training are read from disk, making workloads significantly faster than row-based formats such as CSV.

---

### Prototype Performance Bar

The agreed set of quantitative performance targets for the DataForge 12-month prototype, scaled down from the Dataseed industrial proposal to reflect laptop-Docker hardware constraints. All six metrics — throughput (≥ 10K events/sec), latency p95 (≤ 500 ms), data loss (≤ 1%), time sync (± 1 ms), model AUC (≥ 0.85), and FPR (≤ 5%) — must be verified in Milestone 10. The bar is the binding success criterion for prototype sign-off, agreed with Emrah Uysal in Milestone 1.

---

### PSI / KL Drift
*Population Stability Index / Kullback-Leibler Divergence*

Statistical measures used to detect when the distribution of data flowing into a machine learning model has shifted significantly from the distribution it was trained on — a sign the model may need retraining. PSI measures relative distribution shift; KL divergence quantifies information loss between two distributions. DataForge may use these metrics in Milestones 7–8 to validate that synthetic test data is sufficiently representative of the training distribution.

---

### PTP
*Precision Time Protocol (IEEE 1588)*

A hardware-based clock synchronisation protocol capable of achieving sub-microsecond accuracy across networked devices, commonly used in defence, telecommunications, and industrial automation. The Dataseed industrial proposal targets PTP-based time synchronisation (± 200 µs) for multi-sensor data alignment. The DataForge prototype uses software timestamps instead (± 1 ms) because PTP requires dedicated NIC hardware unavailable in a laptop-Docker environment.

---

### PySpark

The Python API for Apache Spark, a distributed data processing framework designed for large-scale batch and streaming analytics. DataForge uses PySpark's Structured Streaming module to clean, synchronise, and fuse continuous event streams in near-real time inside Docker Compose. PySpark connects to Kafka as both a source (reading raw events) and a sink (writing fused events back to topics).

---

## R

### Risk Score

A numeric value between 0.0 and 1.0 produced by the AI model for every processed event, indicating how anomalous the event is relative to the learned normal distribution. A score close to 1.0 signals a high-confidence anomaly; a score close to 0.0 indicates a normal event. Risk scores are stored in the `anomaly_alerts` TimescaleDB table and displayed on the AI Alerts dashboard page to help operators prioritise which events require investigation.

---

## S

### Schema Evolution

The practice of updating a data schema — adding, removing, or renaming fields — without breaking existing systems that depend on the previous version. DataForge enforces backward-compatible evolution using Avro schemas with a Schema Registry: new optional fields can be added in later milestones without requiring every pipeline consumer to be updated simultaneously. This is essential for a 12-milestone project where data requirements are refined incrementally.

---

### SHAP
*SHapley Additive exPlanations*

A method from cooperative game theory applied to machine learning that computes the contribution of each input feature to a specific model prediction. DataForge's XAI module (Module 8) uses SHAP to explain why a particular event was flagged as anomalous — for example, `energy_gev` contributed +0.42 to the anomaly score. SHAP makes AI decisions auditable and interpretable for non-specialist operators.

---

### SHAP Value

A single numeric contribution score assigned by SHAP to one input feature for one specific model prediction. A positive SHAP value means that feature pushed the prediction toward anomaly; a negative value pushed it toward normal. For each alert, DataForge surfaces the top 3 features by absolute SHAP value, giving operators the three strongest reasons the event was flagged.

---

### STANAG
*NATO Standardization Agreement*

A NATO document that standardises processes, procedures, terms, and technical requirements across member nations to ensure interoperability of military systems and equipment. STANAG-certified radar interfaces are referenced in the Dataseed industrial proposal as a requirement for operational deployment. These are explicitly out of scope for the DataForge prototype, which uses synthetic sensor data instead of certified hardware.

---

### Structured Streaming

Apache Spark's engine for processing continuous data streams by treating the live stream as an unbounded table that grows with each new event. DataForge's Modules 4, 5, and 6 use Structured Streaming to filter, synchronise, and fuse events in near-real time, with watermarks controlling how long the system waits for late data before closing a window. Structured Streaming supports exactly-once processing semantics, ensuring no event is double-counted even after a restart.

---

## T

### Track

In ALICE particle physics, a track is the reconstructed three-dimensional path of a charged particle through the detector, inferred from a sequence of position measurements (hits) left in detector layers. Track parameters include momentum components (px, py, pz), electric charge, and the position at the collision vertex. DataForge ingests track-level data from ALICE Open Data as one of its two input event types.

---

### TRL
*Technology Readiness Level*

A nine-point scale, originally developed by NASA, used to measure the maturity of a technology from basic research (TRL 1–3) through laboratory validation (TRL 4–5) to operational deployment (TRL 6–9). The DataForge prototype targets TRL 4–5: a validated component in a laboratory environment, demonstrated on representative data using laptop-Docker hardware. The full Dataseed industrial proposal targets TRL 5–7 — demonstrated in a relevant operational environment.

---

## W

### Watermark

In stream processing, a watermark is a time threshold that defines how long the system will wait for late-arriving events before considering a time window complete and emitting results. DataForge configures PySpark Structured Streaming with a 2-second watermark: events that arrive more than 2 seconds after their recorded timestamp are dropped from the fusion window. Without a watermark, the system would wait indefinitely for late data and never produce output.

---

## X

### XAI
*Explainable Artificial Intelligence*

A field of AI focused on making model decisions interpretable and verifiable by humans, not merely accurate. DataForge's XAI module (Module 8) uses SHAP to produce structured feature attribution scores and a human-readable cause-effect explanation string for every anomaly alert. XAI is essential for operator trust in defence and industrial applications, where blind reliance on opaque AI scores is operationally unacceptable.

---

## Summary

| v1.0 Total Terms | Required Terms Covered | Additional Terms Added | Next Update |
|-----------------|----------------------|----------------------|-------------|
| 28 | 23 / 23 ✓ | 5 (Anomaly Detection, Isolation Forest, Prototype Performance Bar, PSI/KL Drift, Risk Score) | v2.0 at M2 — Schema & Model Design |

---

*DataForge Prototype · Team: Abdullah · Beyza · Omer · Supervisor: Emrah Uysal · Scientific Advisor: Prof. Dr. Ayben Karasu Uysal*
