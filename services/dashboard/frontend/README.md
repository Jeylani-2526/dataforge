# Module 9a — ReactJS Dashboard

**Owner:** Beyza  
**Milestone:** M9 (implementation)  
**Status:** 🔲 Not started

## Purpose

Live operator dashboard with 7 pages displaying real-time data from the full DataForge pipeline.

## Dashboard Pages

| # | Page | Description |
|---|------|-------------|
| 1 | Home | System status overview, pipeline health |
| 2 | Live Stream | Real-time event feed from Kafka |
| 3 | Fusion Monitor | Fused event timeline, sync quality |
| 4 | AI Alerts | Anomaly detection results and risk scores |
| 5 | XAI Panel | SHAP explanations for each anomaly |
| 6 | Performance | Latency, throughput, data loss metrics |
| 7 | Reports | Downloadable summary reports |

Page-by-page data field specs are a M2 deliverable (`docs/api/dashboard-data-fields.md`).

## Setup

```bash
npm install
npm start         # Development server at http://localhost:3000
npm run build     # Production build
npm test          # Run tests
```
