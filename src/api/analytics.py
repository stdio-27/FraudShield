"""
analytics.py — Advanced TimescaleDB time-series aggregation queries.

Uses raw SQL for TimescaleDB-specific functions (time_bucket) that have
no SQLAlchemy ORM equivalent, wrapped in async execution via the engine.
"""

import logging
import os
import uuid
from datetime import datetime, timezone, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import func, text
from sqlalchemy.future import select
import pandas as pd

from .models import AlertStatusEnum, FraudAlert, Transaction
from .services import model_manager

logging.basicConfig(level=logging.INFO)


def resolve_dataset_path(explicit_path: str | None = None) -> str | None:
    """Locate a local fraud dataset CSV for ingestion into the database."""
    if explicit_path:
        return explicit_path

    env_path = os.getenv("DATASET_PATH")
    if env_path and os.path.exists(env_path):
        return env_path

    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    default_path = os.path.join(base_dir, "data", "creditcard.csv")
    if os.path.exists(default_path):
        return default_path

    return None


def build_transaction_payload_from_row(row, manager=None) -> dict:
    """Convert a dataset row into the payload needed for transaction scoring and persistence."""
    manager = manager or model_manager
    amount = float(row["Amount"])
    time_seconds = float(row["Time"])

    req_data = {"amount": amount, "time_seconds": time_seconds}
    for feature_idx in range(1, 29):
        req_data[f"v{feature_idx}"] = float(row[f"V{feature_idx}"])

    df_eng = manager.engineer_features(req_data).iloc[0]
    fraud_score, is_flagged, _, shap_reasons = manager.predict(req_data)

    return {
        "amount": amount,
        "time_seconds": time_seconds,
        "req_data": req_data,
        "hour_of_day": int(df_eng["hour_of_day"]),
        "amount_zscore": float(df_eng["amount_zscore"]),
        "fraud_score": fraud_score,
        "is_flagged": is_flagged,
        "shap_reasons": shap_reasons,
    }


async def seed_dataset_from_csv_if_needed(db: AsyncSession) -> bool:
    """Import transactions from a local CSV dataset when the database is empty."""
    tx_count_result = await db.execute(select(func.count(Transaction.tx_id)))
    tx_count = tx_count_result.scalar() or 0
    if tx_count > 0:
        return False

    dataset_path = resolve_dataset_path()
    if not dataset_path:
        logging.info("No dataset found at DATASET_PATH or data/creditcard.csv; skipping CSV import.")
        return False

    if model_manager.model is None:
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        models_dir = os.path.join(base_dir, "models")
        model_manager.load_artifacts(models_dir)

    df = pd.read_csv(dataset_path)
    required_columns = {"Time", "Amount", "Class"}
    required_columns.update({f"V{idx}" for idx in range(1, 29)})
    missing_columns = sorted(required_columns - set(df.columns))
    if missing_columns:
        logging.warning(f"Dataset at {dataset_path} is missing required columns: {missing_columns}")
        return False

    import_limit = os.getenv("DATASET_IMPORT_LIMIT", "2000")
    try:
        import_limit_value = int(import_limit)
    except ValueError:
        import_limit_value = 2000

    if import_limit_value > 0:
        df = df.head(import_limit_value)

    anchor_date = datetime(2025, 1, 1, tzinfo=timezone.utc)
    inserted_count = 0

    for _, row in df.iterrows():
        payload = build_transaction_payload_from_row(row, manager=model_manager)
        tx_time = anchor_date + timedelta(seconds=payload["time_seconds"])

        tx = Transaction(
            tx_id=uuid.uuid4(),
            transaction_time=tx_time,
            amount=payload["amount"],
            fraud_score=payload["fraud_score"],
            is_flagged=payload["is_flagged"],
            hour_of_day=payload["hour_of_day"],
            amount_zscore=payload["amount_zscore"],
        )

        for feature_idx in range(1, 29):
            setattr(tx, f"v{feature_idx}", payload["req_data"][f"v{feature_idx}"])

        db.add(tx)
        inserted_count += 1

        if payload["is_flagged"]:
            alert = FraudAlert(
                tx_id=tx.tx_id,
                fraud_score=tx.fraud_score,
                shap_reasons=payload["shap_reasons"] or [],
                status=AlertStatusEnum.open,
            )
            db.add(alert)

        if inserted_count % 250 == 0:
            await db.commit()
            await db.flush()

    if inserted_count:
        await db.commit()
        logging.info(f"Imported {inserted_count} transactions from dataset {dataset_path}.")

    return inserted_count > 0


async def seed_demo_data_if_needed(db: AsyncSession) -> bool:
    """Populate a real dataset when available, otherwise fall back to a small demo set."""
    tx_count_result = await db.execute(select(func.count(Transaction.tx_id)))
    tx_count = tx_count_result.scalar() or 0

    dataset_imported = await seed_dataset_from_csv_if_needed(db)
    if dataset_imported:
        return True

    if tx_count > 0:
        return False

    base_time = datetime.now(timezone.utc)
    sample_transactions = []

    for index in range(12):
        tx_time = base_time - timedelta(minutes=5 * (11 - index))
        is_flagged = index in {2, 5, 8}
        fraud_score = 0.91 if is_flagged else 0.18 + (index * 0.03)

        tx = Transaction(
            tx_id=uuid.uuid4(),
            transaction_time=tx_time,
            amount=120.0 + index * 35.0,
            fraud_score=fraud_score,
            is_flagged=is_flagged,
            hour_of_day=(tx_time.hour + index) % 24,
            amount_zscore=0.4 + (index * 0.08),
        )

        for feature_idx in range(1, 29):
            setattr(tx, f"v{feature_idx}", ((feature_idx % 7) - 3) * 0.2 + (index * 0.02))

        sample_transactions.append(tx)

    for tx in sample_transactions:
        db.add(tx)

    flagged_txs = [tx for tx in sample_transactions if tx.is_flagged]
    if flagged_txs:
        for idx, tx in enumerate(flagged_txs[:3]):
            alert = FraudAlert(
                tx_id=tx.tx_id,
                fraud_score=tx.fraud_score,
                shap_reasons=[{"feature": "V14", "attribution_score": 0.42 + idx * 0.03, "direction": "INCREASE RISK"}],
                status=AlertStatusEnum.open if idx == 0 else AlertStatusEnum.investigating,
            )
            db.add(alert)

    await db.commit()
    return True


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
    await seed_demo_data_if_needed(db)

    #cutoff = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
    latest_tx=await db.execute(
        select(func.max(Transaction.transaction_time))
    )
    latest_time=latest_tx.scalar()
    if latest_time is None :
        return []
    cutoff=latest_time-timedelta(minutes=window_minutes)
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
    await seed_demo_data_if_needed(db)

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
    await seed_demo_data_if_needed(db)

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
