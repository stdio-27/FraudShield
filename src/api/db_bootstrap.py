"""
Schema bootstrap shared by the API lifespan and src/database/init_db.py.

Every optional/fallible step (TimescaleDB extension, hypertable) runs in its own
transaction.  Previously a failing ``create_hypertable`` aborted the single
shared transaction and the commit at exit silently rolled back ``create_all``.
"""

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from .database import Base
from . import models  # noqa: F401  (registers tables on Base.metadata)

logger = logging.getLogger(__name__)

_has_timescale = False

# Idempotent upgrades for databases created before these columns/indexes existed
# (create_all never alters an existing table).
_UPGRADE_STATEMENTS = [
    "ALTER TABLE transactions ADD COLUMN IF NOT EXISTS external_id VARCHAR(64)",
    "ALTER TABLE fraud_alerts ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT now()",
    "CREATE INDEX IF NOT EXISTS ix_transactions_time ON transactions (transaction_time DESC)",
    "CREATE INDEX IF NOT EXISTS ix_transactions_external_id ON transactions (external_id)",
    "CREATE INDEX IF NOT EXISTS ix_transactions_is_flagged ON transactions (is_flagged)",
    "CREATE INDEX IF NOT EXISTS ix_fraud_alerts_status ON fraud_alerts (status)",
    "CREATE INDEX IF NOT EXISTS ix_fraud_alerts_tx_id ON fraud_alerts (tx_id)",
    "CREATE INDEX IF NOT EXISTS ix_fraud_alerts_created_at ON fraud_alerts (created_at)",
]


def has_timescale() -> bool:
    """True when the TimescaleDB extension is active (enables ``time_bucket``)."""
    return _has_timescale


async def init_schema(engine: AsyncEngine) -> None:
    global _has_timescale

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        for stmt in _UPGRADE_STATEMENTS:
            await conn.execute(text(stmt))

    # Optional: TimescaleDB.  Each step has its own transaction.
    try:
        async with engine.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS timescaledb"))
    except Exception as exc:
        logger.info("TimescaleDB extension not available (%s); using plain PostgreSQL.", exc)

    async with engine.connect() as conn:
        row = await conn.execute(text("SELECT 1 FROM pg_extension WHERE extname = 'timescaledb'"))
        _has_timescale = row.first() is not None

    if _has_timescale:
        try:
            async with engine.begin() as conn:
                await conn.execute(text(
                    "SELECT create_hypertable('transactions', 'transaction_time', "
                    "if_not_exists => TRUE, migrate_data => TRUE)"
                ))
            logger.info("TimescaleDB hypertable ready for 'transactions'.")
        except Exception as exc:
            logger.warning("create_hypertable failed (%s); table stays a regular table.", exc)
    else:
        logger.info("Running without TimescaleDB: analytics use date_bin() bucketing.")
