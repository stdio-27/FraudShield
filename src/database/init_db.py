"""
init_db.py — Standalone database initialization and seeding script.

Run from the project root with PYTHONPATH=. :
    python src/database/init_db.py

This script:
  1. Creates all SQLAlchemy ORM tables in the target PostgreSQL/Supabase database.
  2. Attempts to convert 'transactions' into a TimescaleDB hypertable.
  3. Seeds a default admin analyst account for first-time login.
"""

import os
import sys
import asyncio
import logging

# Ensure project root is on the path so that `src.api.*` imports resolve
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy import text
from sqlalchemy.future import select

from src.api.database import engine, Base, AsyncSessionLocal
from src.api.models import Analyst, RoleEnum
from src.api.analytics import seed_dataset_from_csv_if_needed
from src.api.auth import hash_password

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Default seed analyst — change password in production via env var
SEED_EMAIL = os.getenv("SEED_ADMIN_EMAIL", "admin@fraudshield.com")
SEED_PASSWORD = os.getenv("SEED_ADMIN_PASSWORD", "FraudShield2025!")


async def init_tables():
    """Create all ORM tables and configure TimescaleDB hypertable."""
    logging.info("Creating database tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        logging.info("All tables created successfully.")

        # TimescaleDB hypertable (gracefully skipped if extension is missing)
        try:
            await conn.execute(text(
                "SELECT create_hypertable('transactions', 'transaction_time', if_not_exists => TRUE);"
            ))
            logging.info("TimescaleDB hypertable configured for 'transactions'.")
        except Exception as e:
            logging.warning(f"Hypertable setup skipped (extension may not be available): {e}")

        try:
            await conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_transactions_time ON transactions (transaction_time DESC);"
            ))
            logging.info("Time-series index created.")
        except Exception as e:
            logging.warning(f"Index creation note: {e}")


async def seed_admin():
    """Seed a default admin analyst if one does not already exist."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Analyst).where(Analyst.email == SEED_EMAIL))
        existing = result.scalars().first()

        if existing:
            logging.info(f"Admin analyst '{SEED_EMAIL}' already exists — skipping seed.")
            return

        admin = Analyst(
            email=SEED_EMAIL,
            password_hash=hash_password(SEED_PASSWORD),
            role=RoleEnum.admin,
        )
        session.add(admin)
        await session.commit()
        logging.info(f"Seeded admin analyst: {SEED_EMAIL}")


async def main():
    logging.info("=" * 60)
    logging.info("FraudShield — Database Initialization")
    logging.info("=" * 60)

    await init_tables()
    async with AsyncSessionLocal() as session:
        await seed_dataset_from_csv_if_needed(session)
    await seed_admin()

    logging.info("=" * 60)
    logging.info("Database initialization complete. analysts table seeded.")
    logging.info("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
