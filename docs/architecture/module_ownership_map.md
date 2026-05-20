# DataForge — Module Ownership Map


---

## Purpose

This table maps all 10 DataForge system modules to their responsible team member. It defines ownership clearly to prevent ambiguity across milestones and feeds directly into the Scope Reconciliation Document for Emrah Uysal.

---

## Module Ownership Table

| # | Module Name | Type | Owner | Main Technology | Implementation Milestone |
|---|---|---|---|---|---|
| 1 | ALICE Data Source | Source | **Beyza** | Python · CERN Open Data Portal · uproot | M3 — Data Generation & Preprocessing |
| 2 | Sensor Data Source (synthetic) | Source | **Omer** | Python data generators (radar / LIDAR / telemetry) | M3 — Data Generation & Preprocessing |
| 3 | Data Adaptation Layer | Pipeline | **Abdullah + Omer** | PySpark · Avro schemas · Parquet (pyarrow) | M4 — Data Adaptation Layer |
| 4 | Streaming Layer | Pipeline | **Omer** | Apache Kafka · Docker Compose · Confluent image | M5 — Streaming Pipeline |
| 5 | Cleaning & Synchronization | Pipeline | **Beyza + Omer** | PySpark Structured Streaming · watermark windows | M5 — Streaming Pipeline |
| 6 | Data Fusion Layer | Pipeline | **Abdullah + Omer** | PySpark stream-stream join · TimescaleDB Parquet sink | M6 — Data Fusion & Synchronization |
| 7 | AI/ML Anomaly Detection | Intelligence | **Abdullah** | scikit-learn (Isolation Forest) · PyTorch (TBD) · SHAP | M7 — AI/ML Anomaly Detection |
| 8 | Explainable AI (XAI) | Intelligence | **Abdullah** | SHAP library · cause-effect chain templates | M8 — Explainable AI Layer |
| 9 | Dashboard + API | Delivery | **Beyza** | ReactJS · FastAPI · TimescaleDB · PostgreSQL | M9 — Dashboard, API & Integration |
| 10 | Testing & Validation | Validation | **Beyza + Abdullah** | pytest · custom load generators · performance report | M10 — Testing & Final Delivery |
| — | Documentation & Reporting | Cross-cutting | **Abdullah** | Markdown · Docx · GitHub · weekly Emrah updates | All milestones |

---

## Ownership Notes

- **Modules 3 & 6** are co-owned by Abdullah and Omer because they require both PySpark expertise (Omer) and schema/architecture decisions (Abdullah).
- **Module 10** is co-owned because performance testing requires Omer's infrastructure knowledge and Abdullah's understanding of the model metrics (AUC, FPR).
- **Documentation** is a cross-cutting concern owned entirely by Abdullah — this covers architecture docs, weekly updates, milestone reports, final technical report, and the GitHub README.
- **Beyza** owns the full UI/API/database stack (Module 9) and assist Abdullah and Omer.

---

## Team Quick Reference

| Team Member | Modules Owned | Primary Role |
|---|---|---|
| **Abdullah** | 3 (co), 6 (co), 7, 8, 10 (co), Docs | Project Lead · Architecture · AI/ML · XAI · Documentation |
| **Beyza** |1, 9, 5 (co), 10 (co) | Full-Stack Developer · Dashboard · FastAPI · TimescaleDB |
| **Omer** | 2, 3 (co), 4, 6 (co)| Data Engineer · Kafka · PySpark · Docker · Testing |

---


