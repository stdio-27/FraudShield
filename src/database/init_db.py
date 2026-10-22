"""
init_db.py — database initialisation and seeding.

Run from the project root:
    python -m src.database.init_db                 # schema + admin + dataset import
    python -m src.database.init_db --skip-dataset  # schema + admin only
    python -m src.database.init_db --replace-dataset --limit 0   # re-import the whole CSV

Environment (usually in .env):
    SEED_ADMIN_EMAIL, SEED_ADMIN_PASSWORD   required to create the first admin
                                            (no defaults: there is no built-in login)
    DATASET_IMPORT_LIMIT                    rows to import (default 2000, 0 = all)
"""

import argparse
import asyncio
import logging
import os
import sys

# Allow `python src/database/init_db.py` as well as `python -m src.database.init_db`.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy.future import select

from src.api import config  # noqa: F401  (loads .env)
from src.api.auth import get_analyst_by_email, hash_password
from src.api.database import AsyncSessionLocal, engine
from src.api.db_bootstrap import init_schema
from src.api.models import Analyst, RoleEnum
from src.database.seed import seed_dataset_if_empty

logger = logging.getLogger("fraudshield.init_db")

MIN_PASSWORD_LENGTH = 12


async def seed_admin() -> None:
    email = (os.getenv("SEED_ADMIN_EMAIL") or "").strip().lower()
    password = os.getenv("SEED_ADMIN_PASSWORD") or ""

    if not email or not password:
        logger.warning(
            "SEED_ADMIN_EMAIL / SEED_ADMIN_PASSWORD not set; no admin account created. "
            "Set both (and re-run) to create the first admin."
        )
        return
    if len(password) < MIN_PASSWORD_LENGTH:
        raise SystemExit(f"SEED_ADMIN_PASSWORD must be at least {MIN_PASSWORD_LENGTH} characters.")

    async with AsyncSessionLocal() as session:
        if await get_analyst_by_email(session, email):
            logger.info("Admin analyst '%s' already exists; skipping.", email)
            return
        session.add(Analyst(email=email, password_hash=hash_password(password), role=RoleEnum.admin))
        await session.commit()
        logger.info("Seeded admin analyst: %s", email)


async def main(skip_dataset: bool, limit, replace: bool) -> None:
    logger.info("Initialising database schema...")
    await init_schema(engine)
    await seed_admin()
    if not skip_dataset:
        await seed_dataset_if_empty(limit=limit, replace=replace)
    await engine.dispose()
    logger.info("Database initialisation complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Initialise and seed the FraudShield database.")
    parser.add_argument("--skip-dataset", action="store_true", help="do not import creditcard.csv")
    parser.add_argument(
        "--limit", type=int, default=None,
        help="rows of creditcard.csv to import; 0 = the whole file (default: DATASET_IMPORT_LIMIT, then 2000)",
    )
    parser.add_argument(
        "--replace-dataset", action="store_true",
        help="delete previously imported dataset rows (and their alerts) first, then re-import; "
             "transactions scored through the API are kept",
    )
    args = parser.parse_args()
    asyncio.run(main(args.skip_dataset, args.limit, args.replace_dataset))
