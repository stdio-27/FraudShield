"""
analytics.py — Advanced TimescaleDB time-series aggregation queries.

Uses raw SQL for TimescaleDB-specific functions (time_bucket) that have
no SQLAlchemy ORM equivalent, wrapped in async execution via the engine.
"""

import logging
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

logging.basicConfig(level=logging.INFO)


async def get_rolling_fraud_metrics(
    db: AsyncSession,
    window_minutes: int = 60,
) -> list[dict]:
    """
    Calculates rolling fraud metrics over the last *window_minutes* minutes,
    grouped into 5-minute time buckets using TimescaleDB's native
    ``time_bucket`` function.

    Returns a list of dicts, each containing:
        - bucket          : ISO-formatted start of the 5-min window
        - tx_count        : total transactions in that bucket
        - total_volume    : sum of transaction amounts
        - avg_fraud_score : mean fraud_score across the bucket
        - flagged_count   : number of flagged (is_flagged = true) transactions
    """
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)

    query = text("""
        SELECT
            time_bucket('5 minutes', transaction_time) AS bucket,
            COUNT(*)                                   AS tx_count,
            COALESCE(SUM(amount), 0)                   AS total_volume,
            COALESCE(AVG(fraud_score), 0)               AS avg_fraud_score,
            COUNT(*) FILTER (WHERE is_flagged = TRUE)   AS flagged_count
        FROM transactions
        WHERE transaction_time >= :cutoff
        GROUP BY bucket
        ORDER BY bucket DESC;
    """)

    result = await db.execute(query, {"cutoff": cutoff})
    rows = result.fetchall()

    metrics = []
    for row in rows:
        metrics.append({
            "bucket": row.bucket.isoformat() if row.bucket else None,
            "tx_count": row.tx_count,
            "total_volume": float(row.total_volume),
            "avg_fraud_score": round(float(row.avg_fraud_score), 6),
            "flagged_count": row.flagged_count,
        })
    return metrics


async def get_fraud_summary(db: AsyncSession) -> dict:
    """
    Computes a high-level fraud summary across the entire dataset.
    Useful for the /analytics/summary endpoint.
    """
    query = text("""
        SELECT
            COUNT(*)                                    AS total_transactions,
            COALESCE(SUM(amount), 0)                    AS total_volume,
            COALESCE(AVG(fraud_score), 0)                AS avg_fraud_score,
            COALESCE(MAX(fraud_score), 0)                AS max_fraud_score,
            COUNT(*) FILTER (WHERE is_flagged = TRUE)    AS flagged_count,
            COALESCE(
                ROUND(
                    (COUNT(*) FILTER (WHERE is_flagged = TRUE))::numeric
                    / NULLIF(COUNT(*), 0) * 100, 4
                ), 0
            )                                            AS fraud_rate_pct
        FROM transactions;
    """)

    result = await db.execute(query)
    row = result.fetchone()

    if row is None:
        return {
            "total_transactions": 0,
            "total_volume": 0.0,
            "avg_fraud_score": 0.0,
            "max_fraud_score": 0.0,
            "flagged_count": 0,
            "fraud_rate_pct": 0.0,
        }

    return {
        "total_transactions": row.total_transactions,
        "total_volume": float(row.total_volume),
        "avg_fraud_score": round(float(row.avg_fraud_score), 6),
        "max_fraud_score": round(float(row.max_fraud_score), 6),
        "flagged_count": row.flagged_count,
        "fraud_rate_pct": float(row.fraud_rate_pct),
    }


async def get_top_at_risk_analysts(db: AsyncSession, limit: int = 10) -> list[dict]:
    """
    Analyses the fraud_alerts table to find analysts (by alert volume)
    who have the highest number of open or investigating incidents.

    Note: Since our current schema does not assign an analyst to each alert,
    this query groups by alert status to produce audit telemetry on the
    overall alert backlog.  It can be extended once an 'assigned_analyst_id'
    column is added to fraud_alerts.
    """
    query = text("""
        SELECT
            status,
            COUNT(*)                          AS alert_count,
            COALESCE(AVG(fraud_score), 0)     AS avg_severity
        FROM fraud_alerts
        WHERE status IN ('open', 'investigating')
        GROUP BY status
        ORDER BY alert_count DESC
        LIMIT :lim;
    """)

    result = await db.execute(query, {"lim": limit})
    rows = result.fetchall()

    telemetry = []
    for row in rows:
        telemetry.append({
            "status": row.status,
            "alert_count": row.alert_count,
            "avg_severity": round(float(row.avg_severity), 6),
        })
    return telemetry
