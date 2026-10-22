import os

from . import config  # noqa: F401  (loads .env before DATABASE_URL is read)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is not set. Copy .env.example to .env and set it, e.g. "
        "postgresql+asyncpg://postgres:<password>@localhost:5433/fraudshield"
    )

# Ensure URL uses asyncpg driver scheme for create_async_engine
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+asyncpg://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_size=config.env_int("DB_POOL_SIZE", 10),
    max_overflow=config.env_int("DB_MAX_OVERFLOW", 10),
    pool_pre_ping=True,
    pool_recycle=1800,
)
Base = declarative_base()
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
