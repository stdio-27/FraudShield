"""
Dataset import.  Never called from request handlers: run it deliberately via
``python -m src.database.init_db``.

The CSV is processed in chunks (scored in one vectorised pass per chunk, SHAP
only for flagged rows, bulk inserted and committed per chunk), so the whole
284,807-row Kaggle dataset can be loaded without holding it all in memory.

The dataset timeline is shifted so its LAST imported row lands at the moment of
import, which keeps the "last N minutes" dashboard windows populated.  A
Postgres advisory lock stops two processes importing concurrently.

Imported rows are tagged ``external_id = 'dataset-<n>'`` so a re-import can
replace them (``replace=True``) without touching transactions scored via the API.
"""

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import pandas as pd
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import delete, func, insert, select, text

from src.api import config
from src.api.database import AsyncSessionLocal, engine
from src.api.models import AlertStatusEnum, FraudAlert, Transaction
from src.api.services import model_manager
from src.ml.dataset import resolve_dataset_path
from src.ml.features import V_COLUMNS

logger = logging.getLogger(__name__)

_LOCK_KEY = 727_001
_SCORE_CHUNK = 10_000   # rows scored and committed together
_INSERT_CHUNK = 1_000   # rows per executemany batch
DATASET_PREFIX = "dataset-"


def default_import_limit() -> int:
    """Rows to import when no explicit limit is given (env DATASET_IMPORT_LIMIT; 0 = all)."""
    return config.env_int("DATASET_IMPORT_LIMIT", 2000)


async def seed_dataset_if_empty(limit: Optional[int] = None, replace: bool = False) -> int:
    """
    Import the CSV into the database.  Returns the number of transactions inserted.

    limit    rows to import (0 = the whole file); defaults to DATASET_IMPORT_LIMIT
    replace  first delete previously imported dataset rows (and their alerts), keeping
             anything scored through the API; without it, import only into an empty table
    """
    dataset_path = resolve_dataset_path()
    if not dataset_path:
        logger.warning("No creditcard.csv found (set DATASET_PATH or use data/creditcard.csv); nothing imported.")
        return 0

    if not model_manager.is_ready:
        try:
            model_manager.load_artifacts(config.MODELS_DIR)
        except Exception as exc:
            logger.error("Cannot import dataset: model artifacts unavailable (%s)", exc)
            return 0

    row_limit = default_import_limit() if limit is None else limit

    async with engine.connect() as lock_conn:
        got_lock = (await lock_conn.execute(text("SELECT pg_try_advisory_lock(:k)"), {"k": _LOCK_KEY})).scalar()
        if not got_lock:
            logger.info("Another process is importing the dataset; skipping.")
            return 0
        try:
            return await _import(dataset_path, row_limit, replace)
        finally:
            await lock_conn.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": _LOCK_KEY})
            await lock_conn.rollback()


async def _import(dataset_path: str, row_limit: int, replace: bool) -> int:
    nrows = row_limit if row_limit > 0 else None

    async with AsyncSessionLocal() as session:
        if replace:
            imported_ids = select(Transaction.tx_id).where(Transaction.external_id.like(f"{DATASET_PREFIX}%"))
            alerts_deleted = (await session.execute(delete(FraudAlert).where(FraudAlert.tx_id.in_(imported_ids)))).rowcount
            tx_deleted = (
                await session.execute(delete(Transaction).where(Transaction.external_id.like(f"{DATASET_PREFIX}%")))
            ).rowcount
            await session.commit()
            logger.info("Removed %s previously imported transactions and %s alerts.", tx_deleted, alerts_deleted)
        else:
            existing = (await session.execute(select(func.count(Transaction.tx_id)))).scalar() or 0
            if existing:
                logger.info(
                    "transactions table already has %s rows; skipping dataset import "
                    "(use --replace-dataset to re-import).", existing,
                )
                return 0

    header = await run_in_threadpool(pd.read_csv, dataset_path, nrows=0)
    missing = sorted({"Time", "Amount", "Class", *V_COLUMNS} - set(header.columns))
    if missing:
        logger.error("Dataset %s is missing columns: %s", dataset_path, missing)
        return 0

    # Shift the timeline so the last imported row is "now".
    times = await run_in_threadpool(pd.read_csv, dataset_path, usecols=["Time"], nrows=nrows)
    base_time = datetime.now(timezone.utc) - timedelta(seconds=float(times["Time"].max()))
    total_rows = len(times)
    logger.info("Importing %s rows from %s in chunks of %s...", total_rows, dataset_path, _SCORE_CHUNK)

    reader = pd.read_csv(dataset_path, nrows=nrows, chunksize=_SCORE_CHUNK)
    inserted = alerts_created = 0

    for chunk in reader:
        results = await run_in_threadpool(model_manager.score_frame, chunk)
        records = chunk.to_dict("records")

        tx_rows, alert_rows = [], []
        for offset, (rec, result) in enumerate(zip(records, results)):
            tx_id = uuid.uuid4()
            tx_row = {
                "tx_id": tx_id,
                "transaction_time": base_time + timedelta(seconds=float(rec["Time"])),
                "external_id": f"{DATASET_PREFIX}{inserted + offset}",
                "amount": float(rec["Amount"]),
                "hour_of_day": result.hour_of_day,
                "amount_zscore": result.amount_zscore,
                "fraud_score": result.fraud_score,
                "is_flagged": result.is_flagged,
            }
            for i in range(1, 29):
                tx_row[f"v{i}"] = float(rec[f"V{i}"])
            tx_rows.append(tx_row)

            if result.is_flagged:
                alert_rows.append({
                    "alert_id": uuid.uuid4(),
                    "tx_id": tx_id,
                    "fraud_score": result.fraud_score,
                    "shap_reasons": result.shap_reasons or [],
                    "status": AlertStatusEnum.open,
                })

        async with AsyncSessionLocal() as session:
            for start in range(0, len(tx_rows), _INSERT_CHUNK):
                await session.execute(insert(Transaction), tx_rows[start:start + _INSERT_CHUNK])
            for start in range(0, len(alert_rows), _INSERT_CHUNK):
                await session.execute(insert(FraudAlert), alert_rows[start:start + _INSERT_CHUNK])
            await session.commit()

        inserted += len(tx_rows)
        alerts_created += len(alert_rows)
        logger.info("  %s / %s rows imported (%s alerts so far)", inserted, total_rows, alerts_created)

    logger.info("Imported %s transactions (%s alerts) from %s.", inserted, alerts_created, dataset_path)
    return inserted
