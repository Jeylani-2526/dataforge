# Promotion Validation Note

## Records Promoted

| Source | Records | load_status |
|---|---|---|
| `raw_alice_events_staging` | 68 | promoted ✅ |
| `raw_sensor_events_staging` | 150,000 | promoted ✅ |

---

## Events Hypertable — Source Type Counts

```sql
SELECT source_type, COUNT(*) FROM events GROUP BY source_type ORDER BY source_type;
```

| source_type | count |
|---|---|
| alice | 68 |
| lidar | 150,000 |
| radar | 150,000 |
| telemetry | 150,000 |

---

## Staging load_status

```sql
SELECT load_status, COUNT(*) FROM raw_sensor_events_staging GROUP BY load_status;
```

| load_status | count |
|---|---|
| promoted | 150,000 |

```sql
SELECT load_status, COUNT(*) FROM raw_alice_events_staging GROUP BY load_status;
```

| load_status | count |
|---|---|
| promoted | 68 |

---

0 failed · 0 skipped · port 5433 · M4W16T1 fix applied
