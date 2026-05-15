# Architecture

This folder contains the DataForge architecture documentation.

## Files

| File | Description |
|------|-------------|
| `DataForge_Architecture.png` | Main architecture diagram (all 10 modules + prototype bar) |
| `ARCHITECTURE.md` | Narrative description of each layer and design decisions |

## Pipeline Summary

```
[1] ALICE-like Event Data (CERN Open Data Portal)
[2] Sensor Data — Radar / LIDAR / Telemetry (synthetic generators)
        │
        ▼
[3] Data Adaptation Layer — Avro serialization, Parquet storage
        │
        ▼
[4] Streaming Layer — Apache Kafka (topic-partitioned)
        │
        ▼
[5] Cleaning & Synchronization — PySpark Structured Streaming
        │  Software timestamps, watermark windows, duplicate removal
        ▼
[6] Data Fusion — Window-based join on unified timeline
        │
        ▼
[7] AI/ML Anomaly Detection — scikit-learn / PyTorch, AUC ≥ 0.85
        │
        ▼
[8] Explainable AI (XAI) — SHAP feature attribution
        │
        ▼
[9] Dashboard + API — ReactJS + FastAPI + TimescaleDB
        │
        ▼
[10] Testing & Validation — Latency, throughput, FPR, AUC reports
```

## Design Principles

**ALICE O² Reference Model:** DataForge adapts the CERN ALICE Online–Offline (O²) architecture, which processes millions of particle collisions per second. The same principles — continuous event streams, parallel processing, fault tolerance — apply to defense and industrial sensor data.

**Software-only time synchronization:** The prototype uses software timestamps with ±1 ms precision via watermark windows. Hardware PTP synchronization is out of scope for the prototype (industrial version only).

**Docker Compose deployment:** The full pipeline runs on team laptops via Docker Compose. This means throughput targets (≥10K events/sec) are scaled down from the industrial 200K events/sec goal.

**Module ownership map:**

| Module | Owner |
|--------|-------|
| 1, 7, 8 + Architecture | Abdalla |
| 9 (Dashboard + API) + TimescaleDB | Beyza |
| 2, 4, 5, 6, 10 + Docker | Omer |
