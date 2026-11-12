-- M7W27: range checks on fused_events scored columns (M7W27T5 finding).
-- For databases created before the checks were added to init-db.sql.
-- Safe to run more than once. NULL passes a CHECK, so unscored rows are unaffected.

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_fused_anomaly_label') THEN
        ALTER TABLE fused_events
            ADD CONSTRAINT chk_fused_anomaly_label CHECK (anomaly_label IN (0, 1));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_fused_risk_score') THEN
        ALTER TABLE fused_events
            ADD CONSTRAINT chk_fused_risk_score CHECK (risk_score BETWEEN 0.0 AND 1.0);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'chk_fused_confidence') THEN
        ALTER TABLE fused_events
            ADD CONSTRAINT chk_fused_confidence CHECK (confidence BETWEEN 0.0 AND 1.0);
    END IF;
END $$;

SELECT conname, pg_get_constraintdef(oid) AS definition
FROM pg_constraint
WHERE conname LIKE 'chk_fused_%'
ORDER BY conname;
