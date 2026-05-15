# Module 1 — ALICE-like Event Data Ingestion

**Owner:** Abdalla  
**Milestone:** M3 (implementation), M4 (integration with adaptation layer)  
**Status:** 🔲 Not started

## Purpose

Ingest scientific event data from the CERN Open Data Portal (ALICE Run 3 dataset subset) and publish raw event records to Kafka.

## Data Fields

| Field | Type | Description |
|-------|------|-------------|
| event_id | string | Unique event identifier |
| timestamp | int64 (ms) | Event timestamp (software) |
| position_x | float | Particle position X (cm) |
| position_y | float | Particle position Y (cm) |
| position_z | float | Particle position Z (cm) |
| momentum | float | Track momentum (GeV/c) |
| energy | float | Cluster energy (GeV) |
| source | string | Always "alice" |

## Kafka Output Topic

`alice-events`

## Setup

```bash
# Install dependencies (M3)
pip install -r requirements.txt

# Run locally
python src/alice_ingestion.py --data-path ../../data/samples/
```

## Notes

- ALICE Run 3 sample data must be downloaded separately from the CERN Open Data Portal (M3 task)
- See `data/samples/` for expected file structure
