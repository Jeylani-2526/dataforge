"""
DataForge — fusion_status heartbeat writer (M6W22T5).

Writes one row per source (alice / sensor) into fusion_status after
each micro-batch. Uses the shared DB connection from fused_writer
(design note T2 / T5 coordination) — no second connection opened.

Called by fusion_engine.py after write_fused_events() returns.
"""

import logging
from datetime import datetime, timezone

log = logging.getLogger(__name__)

HEARTBEAT_TABLE = "fusion_status"

# status thresholds
_QUALITY_OK = 80
_QUALITY_DEGRADED = 50


def _derive_status(quality_score: int) -> str:
    if quality_score >= _QUALITY_OK:
        return "ok"
    if quality_score >= _QUALITY_DEGRADED:
        return "degraded"
    return "critical"


def _compute_quality(data_loss_pct: float, latency_ms: float) -> int:
    """
    Simple quality heuristic — same units as fused_events columns:
      data_loss_pct : 0.0–100.0 (share of batch rejected by enforce())
      latency_ms    : write time minus event timestamp_ms

    Score starts at 100, deductions:
      - data_loss_pct points for data loss
      - 1 point per 100 ms of latency above 500 ms
    """
    score = 100.0
    score -= data_loss_pct
    if latency_ms > 500:
        score -= (latency_ms - 500) / 100.0
    return max(0, int(score))


def write_heartbeat(
    source_type: str,
    data_loss_pct: float,
    latency_ms: float,
    contribution_weight: float,
):
    """
    Insert one heartbeat row for source_type into fusion_status.

    Parameters
    ----------
    source_type         : "alice" or "sensor"
    data_loss_pct       : from fused_writer result.data_loss_pct
    latency_ms          : avg latency of the micro-batch (ms)
    contribution_weight : share of valid records this source contributed
                          (alice always 1.0 for a 1:1 join; sensor likewise)
    """
    from fused_writer import get_connection

    quality_score = _compute_quality(data_loss_pct, latency_ms)
    status = _derive_status(quality_score)
    now = datetime.now(timezone.utc)

    db = get_connection()
    conn = db.get()
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                INSERT INTO {HEARTBEAT_TABLE}
                    (time, source_type, quality_score,
                     contribution_weight, data_loss, latency, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    now,
                    source_type,
                    quality_score,
                    contribution_weight,
                    data_loss_pct,
                    latency_ms,
                    status,
                ),
            )
        conn.commit()
        log.info(
            "[heartbeat] %s — quality=%d status=%s data_loss=%.4f%% latency=%.1fms",
            source_type,
            quality_score,
            status,
            data_loss_pct,
            latency_ms,
        )
    except Exception as exc:
        log.error("[heartbeat] failed to write %s heartbeat: %s", source_type, exc)
        try:
            conn.rollback()
        except Exception:
            db.discard()
        raise
