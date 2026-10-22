import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from fastapi.security import APIKeyHeader, OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from . import config
from .database import get_db
from .models import Analyst, RoleEnum

logger = logging.getLogger(__name__)

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = config.ACCESS_TOKEN_EXPIRE_MINUTES
MIN_SECRET_LENGTH = 32
_KNOWN_INSECURE_SECRETS = {
    "fraudshield-super-secret-key-dev-12345",
    "CHANGE_ME_TO_A_STRONG_RANDOM_SECRET",
    "your-secret-key",
}


def _load_secret_key() -> str:
    secret = os.getenv("SECRET_KEY", "").strip()
    if secret and secret not in _KNOWN_INSECURE_SECRETS and len(secret) >= MIN_SECRET_LENGTH:
        return secret

    reason = (
        "SECRET_KEY is not set"
        if not secret
        else "SECRET_KEY is a known placeholder or shorter than 32 characters"
    )
    if config.IS_PRODUCTION:
        raise RuntimeError(
            f"{reason}. Refusing to start in production. Generate one with: "
            'python -c "import secrets; print(secrets.token_urlsafe(64))"'
        )
    logger.warning(
        "%s. Using a random per-process secret (development only): all tokens become "
        "invalid on restart. Set SECRET_KEY in .env to avoid this.",
        reason,
    )
    return secrets.token_urlsafe(64)


SECRET_KEY = _load_secret_key()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

_BCRYPT_MAX_BYTES = 72


def hash_password(password: str) -> str:
    raw = password.encode("utf-8")
    if len(raw) > _BCRYPT_MAX_BYTES:
        raise ValueError("Password must be at most 72 bytes when UTF-8 encoded.")
    return bcrypt.hashpw(raw, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    raw = plain_password.encode("utf-8")
    if len(raw) > _BCRYPT_MAX_BYTES:
        return False
    try:
        return bcrypt.checkpw(raw, hashed_password.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# Verified against when the account does not exist so login timing does not
# reveal which emails are registered.
_DUMMY_HASH = hash_password(secrets.token_urlsafe(16))


async def hash_password_async(password: str) -> str:
    return await run_in_threadpool(hash_password, password)


async def verify_password_async(plain_password: str, hashed_password: Optional[str]) -> bool:
    return await run_in_threadpool(verify_password, plain_password, hashed_password or _DUMMY_HASH)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    now = datetime.now(timezone.utc)
    to_encode = data.copy()
    to_encode.update(
        {"iat": now, "exp": now + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))}
    )
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def _credentials_exception() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_analyst_by_email(db: AsyncSession, email: str) -> Optional[Analyst]:
    result = await db.execute(select(Analyst).where(func.lower(Analyst.email) == email.strip().lower()))
    return result.scalars().first()


async def _analyst_from_token(token: str, db: AsyncSession) -> Analyst:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
    except JWTError:
        raise _credentials_exception()
    if not email:
        raise _credentials_exception()

    analyst = await get_analyst_by_email(db, email)
    if analyst is None:
        raise _credentials_exception()
    return analyst


async def get_current_active_analyst(
    token: str = Depends(oauth2_scheme), db: AsyncSession = Depends(get_db)
) -> Analyst:
    return await _analyst_from_token(token, db)


def require_roles(*roles: RoleEnum):
    """Dependency factory: the authenticated analyst's DB role must be in ``roles``."""

    async def checker(analyst: Analyst = Depends(get_current_active_analyst)) -> Analyst:
        if analyst.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return analyst

    return checker


async def authorize_scoring(
    api_key: Optional[str] = Depends(api_key_header),
    token: Optional[str] = Depends(oauth2_scheme_optional),
    db: AsyncSession = Depends(get_db),
) -> str:
    """
    Guards POST /transactions/score.  Accepts either the machine API key
    (``X-API-Key`` == SCORING_API_KEY) or a JWT of an analyst/admin.
    Returns a stable principal id used for rate limiting.
    """
    if api_key and config.SCORING_API_KEY:
        if secrets.compare_digest(api_key.encode("utf-8"), config.SCORING_API_KEY.encode("utf-8")):
            return "apikey"

    if token:
        analyst = await _analyst_from_token(token, db)
        if analyst.role not in (RoleEnum.analyst, RoleEnum.admin):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return f"user:{analyst.analyst_id}"

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Bearer"},
    )
