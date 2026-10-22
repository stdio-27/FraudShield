"""
analytics.py — read-only aggregation queries for the dashboard.

Time bucketing uses TimescaleDB's ``time_bucket`` when the extension is active
and PostgreSQL's built-in ``date_bin`` (PG 14+) otherwise.  Nothing in here
writes or seeds data; use ``python -m src.database.init_db`` for that.
"""

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import func

from . import config
from .db_bootstrap import has_timescale
from .models import Transaction

logger = logging.getLogger(__name__)

_BUCKET_TIMESCALE = "time_bucket('5 minutes', transaction_time)"
_BUCKET_PLAIN = "date_bin('5 minutes', transaction_time, TIMESTAMPTZ '2000-01-01 00:00:00+00')"


async def _window_end(db: AsyncSession):
    """End of the rolling window: 'now' by default, or the newest transaction when ANALYTICS_ANCHOR=latest."""
    if config.ANALYTICS_ANCHOR == "latest":
        return (await db.execute(select(func.max(Transaction.transaction_time)))).scalar()
    return datetime.now(timezone.utc)


async def get_rolling_fraud_metrics(db: AsyncSession, window_minutes: int = 60) -> list[dict]:
    """
    Fraud metrics over the last *window_minutes*, grouped into 5-minute buckets
    (newest first).  Each bucket holds: bucket (ISO start), tx_count,
    total_volume, avg_fraud_score and flagged_count.
    """
    end = await _window_end(db)
    if end is None:
        return []
    cutoff = end - timedelta(minutes=window_minutes)

    bucket_expr = _BUCKET_TIMESCALE if has_timescale() else _BUCKET_PLAIN
    # bucket_expr is one of two constants above, never user input.
    query = text(f"""
        SELECT
            {bucket_expr}                               AS bucket,
            COUNT(*)                                    AS tx_count,
            COALESCE(SUM(amount), 0)                    AS total_volume,
            COALESCE(AVG(fraud_score), 0)               AS avg_fraud_score,
            COUNT(*) FILTER (WHERE is_flagged = TRUE)   AS flagged_count
        FROM transactions
        WHERE transaction_time >= :cutoff AND transaction_time <= :end
        GROUP BY bucket
        ORDER BY bucket DESC;
    """)
    rows = (await db.execute(query, {"cutoff": cutoff, "end": end})).fetchall()

    return [
        {
            "bucket": row.bucket.isoformat() if row.bucket else None,
            "tx_count": row.tx_count,
            "total_volume": float(row.total_volume),
            "avg_fraud_score": round(float(row.avg_fraud_score), 6),
            "flagged_count": row.flagged_count,
        }
        for row in rows
    ]


async def get_fraud_summary(db: AsyncSession) -> dict:
    """High-level fraud summary across the entire transactions table."""
    query = text("""
        SELECT
            COUNT(*)                                    AS total_transactions,
            COALESCE(SUM(amount), 0)                    AS total_volume,
            COALESCE(AVG(fraud_score), 0)               AS avg_fraud_score,
            COALESCE(MAX(fraud_score), 0)               AS max_fraud_score,
            COUNT(*) FILTER (WHERE is_flagged = TRUE)   AS flagged_count,
            COALESCE(
                ROUND(
                    (COUNT(*) FILTER (WHERE is_flagged = TRUE))::numeric
                    / NULLIF(COUNT(*), 0) * 100, 4
                ), 0
            )                                           AS fraud_rate_pct
        FROM transactions;
    """)
    row = (await db.execute(query)).fetchone()

    return {
        "total_transactions": row.total_transactions,
        "total_volume": float(row.total_volume),
        "avg_fraud_score": round(float(row.avg_fraud_score), 6),
        "max_fraud_score": round(float(row.max_fraud_score), 6),
        "flagged_count": row.flagged_count,
        "fraud_rate_pct": float(row.fraud_rate_pct),
    }


async def get_alert_backlog(db: AsyncSession) -> list[dict]:
    """
    Open / investigating alert volume and average severity, grouped by status.
    (The schema has no per-analyst assignment yet, so this is backlog telemetry.)
    """
    query = text("""
        SELECT
            status,
            COUNT(*)                          AS alert_count,
            COALESCE(AVG(fraud_score), 0)     AS avg_severity
        FROM fraud_alerts
        WHERE status IN ('open', 'investigating')
        GROUP BY status
        ORDER BY alert_count DESC;
    """)
    rows = (await db.execute(query)).fetchall()
    return [
        {
            "status": row.status,
            "alert_count": row.alert_count,
            "avg_severity": round(float(row.avg_severity), 6),
        }
        for row in rows
    ]
