import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Optional

from . import config  # noqa: F401  (must be first: loads .env)
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response, status
from fastapi.concurrency import run_in_threadpool
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from . import alerts as alert_engine
from . import cache
from .alerts import evaluate_and_dispatch_alert
from .analytics import get_alert_backlog, get_fraud_summary, get_rolling_fraud_metrics
from .auth import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    authorize_scoring,
    create_access_token,
    get_analyst_by_email,
    get_current_active_analyst,
    hash_password_async,
    require_roles,
    verify_password_async,
)
from .database import engine, get_db
from .db_bootstrap import init_schema
from .models import Analyst, AlertStatusEnum, FraudAlert, RoleEnum, Transaction
from .schemas import (
    AlertListResponse,
    AlertResponse,
    AlertStatusUpdate,
    AnalystCreate,
    AnalystResponse,
    Token,
    TransactionRequest,
    TransactionResponse,
)
from .services import model_manager

logger = logging.getLogger("fraudshield.api")

# Dynamic CORS origins — never use "*" in production.  Trailing slashes are
# stripped because browsers send origins without them.
_ALLOWED_ORIGINS = [
    origin.strip().rstrip("/")
    for origin in os.getenv("FRONTEND_PRODUCTION_URL", "http://localhost:5173").split(",")
    if origin.strip()
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. ML artifacts.  A failure leaves the model "not ready": /health reports
    #    503 and scoring returns 503, but the rest of the API stays usable.
    try:
        model_manager.load_artifacts(config.MODELS_DIR)
    except Exception as exc:
        logger.error("Failed to load ML artifacts: %s", exc, exc_info=True)

    # 2. Database schema (+ optional TimescaleDB)
    await init_schema(engine)

    # 3. Redis (optional; the API degrades gracefully without it)
    await cache.init(os.getenv("REDIS_URL", "redis://localhost:6379"))

    yield

    await alert_engine.close_client()
    await cache.close()
    await engine.dispose()


app = FastAPI(
    title="FraudShield API",
    description="Real-time Fraud Detection with Persistent DB, Cache, Analytics & Alerting",
    version="1.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key"],
)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    """422 without echoing the offending input (NaN/Infinity are not JSON-serialisable and crashed the default handler)."""
    errors = [{"loc": list(e.get("loc", ())), "msg": e.get("msg"), "type": e.get("type")} for e in exc.errors()]
    return JSONResponse(status_code=422, content={"detail": errors})


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


# ---------------------------------------------------------------------------
# AUTH ROUTES
# ---------------------------------------------------------------------------

@app.post("/auth/register", response_model=AnalystResponse, status_code=status.HTTP_201_CREATED, tags=["Auth"])
async def register(
    analyst_data: AnalystCreate,
    db: AsyncSession = Depends(get_db),
    _admin: Analyst = Depends(require_roles(RoleEnum.admin)),
):
    """Create an analyst account.  Admin-only: there is no self-service sign-up."""
    email = analyst_data.email.strip().lower()
    if await get_analyst_by_email(db, email):
        raise HTTPException(status_code=400, detail="Email already registered")

    new_analyst = Analyst(
        email=email,
        password_hash=await hash_password_async(analyst_data.password),
        role=RoleEnum(analyst_data.role.value),
    )
    db.add(new_analyst)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=400, detail="Email already registered")
    await db.refresh(new_analyst)

    logger.info("Analyst %s created by admin %s with role %s", new_analyst.email, _admin.email, new_analyst.role.value)
    return AnalystResponse(
        analyst_id=str(new_analyst.analyst_id),
        email=new_analyst.email,
        role=new_analyst.role.value,
    )


@app.post("/auth/login", response_model=Token, tags=["Auth"])
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
):
    username = form_data.username.strip().lower()
    ip = _client_ip(request)
    user_key = f"login:{ip}:{username}"

    allowed = await cache.rate_limit(user_key, config.LOGIN_MAX_ATTEMPTS, config.LOGIN_WINDOW_SECONDS)
    allowed = await cache.rate_limit(f"login-ip:{ip}", config.LOGIN_MAX_ATTEMPTS * 10, config.LOGIN_WINDOW_SECONDS) and allowed
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Try again later.",
            headers={"Retry-After": str(config.LOGIN_WINDOW_SECONDS)},
        )

    analyst = await get_analyst_by_email(db, username)
    # Always run a bcrypt verification (against a dummy hash if the account is
    # unknown) so response time does not reveal whether the email exists.
    password_ok = await verify_password_async(form_data.password, analyst.password_hash if analyst else None)

    if not analyst or not password_ok:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    await cache.rate_limit_reset(user_key)
    access_token = create_access_token(
        data={"sub": analyst.email, "role": analyst.role.value},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    return {"access_token": access_token, "token_type": "bearer"}


# ---------------------------------------------------------------------------
# TRANSACTION SCORING
# ---------------------------------------------------------------------------

def _resolve_tx_id(raw_id: str) -> uuid.UUID:
    """UUIDs are used as-is; any other id maps deterministically, so retries are idempotent."""
    try:
        return uuid.UUID(raw_id)
    except ValueError:
        return uuid.uuid5(uuid.NAMESPACE_URL, f"fraudshield:transaction:{raw_id}")


async def _stored_response(
    db: AsyncSession, tx: Transaction, external_id: str, started: float
) -> TransactionResponse:
    alert = (
        await db.execute(select(FraudAlert).where(FraudAlert.tx_id == tx.tx_id).limit(1))
    ).scalars().first()
    flagged = bool(tx.is_flagged)
    return TransactionResponse(
        transaction_id=external_id,
        fraud_score=tx.fraud_score or 0.0,
        is_flagged=flagged,
        decision="REVIEW" if flagged else "APPROVE",
        shap_reasons=alert.shap_reasons if alert else None,
        latency_ms=int((time.perf_counter() - started) * 1000),
    )


async def _find_transaction(db: AsyncSession, tx_id: uuid.UUID) -> Optional[Transaction]:
    return (
        await db.execute(select(Transaction).where(Transaction.tx_id == tx_id).limit(1))
    ).scalars().first()


@app.post("/transactions/score", response_model=TransactionResponse, tags=["Scoring"])
async def score_transaction(
    request: TransactionRequest,
    db: AsyncSession = Depends(get_db),
    principal: str = Depends(authorize_scoring),
):
    """
    Score one transaction.  Requires `X-API-Key` (SCORING_API_KEY) or an analyst JWT.
    Idempotent on `transaction_id`: re-sending the same id returns the stored result.
    """
    started = time.perf_counter()

    if not model_manager.is_ready:
        raise HTTPException(status_code=503, detail="Scoring model is not available")

    if not await cache.rate_limit(f"score:{principal}", config.SCORE_RATE_LIMIT_PER_MIN, 60):
        raise HTTPException(status_code=429, detail="Rate limit exceeded", headers={"Retry-After": "60"})

    tx_id = _resolve_tx_id(request.transaction_id)

    existing = await _find_transaction(db, tx_id)
    if existing is not None:
        return await _stored_response(db, existing, request.transaction_id, started)

    req_dict = request.model_dump(exclude={"transaction_id", "transaction_time"})
    try:
        result = await run_in_threadpool(model_manager.score, req_dict)
    except Exception:
        logger.exception("Model inference failed for transaction %s", request.transaction_id)
        raise HTTPException(status_code=500, detail="Model inference failed")

    transaction_time = request.transaction_time or datetime.now(timezone.utc)
    v_values = {f"v{i}": req_dict[f"v{i}"] for i in range(1, 29)}

    try:
        db.add(Transaction(
            tx_id=tx_id,
            transaction_time=transaction_time,
            external_id=request.transaction_id,
            amount=request.amount,
            hour_of_day=result.hour_of_day,
            amount_zscore=result.amount_zscore,
            fraud_score=result.fraud_score,
            is_flagged=result.is_flagged,
            **v_values,
        ))
        if result.is_flagged:
            db.add(FraudAlert(
                tx_id=tx_id,
                fraud_score=result.fraud_score,
                shap_reasons=result.shap_reasons,
                status=AlertStatusEnum.open,
            ))
        await db.commit()
    except IntegrityError:
        # A concurrent request with the same transaction_id won the race.
        await db.rollback()
        existing = await _find_transaction(db, tx_id)
        if existing is not None:
            return await _stored_response(db, existing, request.transaction_id, started)
        logger.exception("Integrity error persisting transaction %s", request.transaction_id)
        raise HTTPException(status_code=500, detail="Could not store transaction")
    except Exception:
        await db.rollback()
        logger.exception("Database error persisting transaction %s", request.transaction_id)
        raise HTTPException(status_code=500, detail="Could not store transaction")

    # Persisted: nothing below may turn the request into an error.
    evaluate_and_dispatch_alert(
        tx_id=tx_id,
        amount=request.amount,
        fraud_score=result.fraud_score,
        is_flagged=result.is_flagged,
        shap_reasons=result.shap_reasons,
    )

    return TransactionResponse(
        transaction_id=request.transaction_id,
        fraud_score=result.fraud_score,
        is_flagged=result.is_flagged,
        decision=result.decision,
        shap_reasons=result.shap_reasons,
        latency_ms=int((time.perf_counter() - started) * 1000),
    )


# ---------------------------------------------------------------------------
# ALERTS  (JWT-protected)
# ---------------------------------------------------------------------------

def _alert_to_response(alert: FraudAlert, amount=None, transaction_time=None, external_id=None) -> AlertResponse:
    return AlertResponse(
        alert_id=alert.alert_id,
        tx_id=alert.tx_id,
        fraud_score=alert.fraud_score,
        status=alert.status.value if alert.status else AlertStatusEnum.open.value,
        shap_reasons=alert.shap_reasons or None,
        created_at=alert.created_at,
        amount=amount,
        transaction_time=transaction_time,
        external_id=external_id,
    )


# FraudAlert plus the columns of its transaction, joined on tx_id (outer: tolerate a missing row)
def _alert_with_transaction():
    return select(
        FraudAlert, Transaction.amount, Transaction.transaction_time, Transaction.external_id
    ).outerjoin(Transaction, Transaction.tx_id == FraudAlert.tx_id)


@app.get("/alerts", response_model=AlertListResponse, tags=["Alerts"])
async def list_alerts(
    status_filter: Optional[str] = Query(None, alias="status", description="Comma-separated statuses"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    _user: Analyst = Depends(get_current_active_analyst),
):
    query = _alert_with_transaction()
    count_query = select(func.count(FraudAlert.alert_id))

    if status_filter:
        try:
            wanted = [AlertStatusEnum(s.strip()) for s in status_filter.split(",") if s.strip()]
        except ValueError:
            raise HTTPException(status_code=422, detail="Invalid status filter")
        query = query.where(FraudAlert.status.in_(wanted))
        count_query = count_query.where(FraudAlert.status.in_(wanted))

    total = (await db.execute(count_query)).scalar() or 0
    rows = (
        await db.execute(
            query.order_by(FraudAlert.created_at.desc(), FraudAlert.fraud_score.desc())
            .limit(limit)
            .offset(offset)
        )
    ).all()

    return AlertListResponse(
        items=[_alert_to_response(a, amount, tx_time, ext_id) for a, amount, tx_time, ext_id in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@app.patch("/alerts/{alert_id}", response_model=AlertResponse, tags=["Alerts"])
async def update_alert_status(
    alert_id: uuid.UUID,
    body: AlertStatusUpdate,
    db: AsyncSession = Depends(get_db),
    user: Analyst = Depends(require_roles(RoleEnum.analyst, RoleEnum.admin)),
):
    row = (
        await db.execute(_alert_with_transaction().where(FraudAlert.alert_id == alert_id))
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Alert not found")
    alert, amount, tx_time, ext_id = row

    previous = alert.status.value if alert.status else None
    alert.status = AlertStatusEnum(body.status.value)
    await db.commit()
    await db.refresh(alert)

    logger.info("Alert %s: %s -> %s by %s", alert_id, previous, body.status.value, user.email)
    await cache.delete("analytics:alert_telemetry", "dashboard_stats")
    return _alert_to_response(alert, amount, tx_time, ext_id)


# ---------------------------------------------------------------------------
# ANALYTICS ROUTES  (JWT-PROTECTED, REDIS-CACHED)
# ---------------------------------------------------------------------------

@app.get("/analytics/summary", tags=["Analytics"])
async def analytics_summary(
    db: AsyncSession = Depends(get_db),
    _user: Analyst = Depends(get_current_active_analyst),
):
    """High-level fraud summary across all transactions. Cached for 30 seconds."""

    async def build():
        summary = await get_fraud_summary(db)
        summary["timestamp"] = datetime.now(timezone.utc).isoformat()
        return summary

    return await cache.cached("analytics:summary", 30, build)


@app.get("/analytics/time-series", tags=["Analytics"])
async def analytics_time_series(
    window_minutes: int = Query(60, ge=1, le=1440),
    db: AsyncSession = Depends(get_db),
    _user: Analyst = Depends(get_current_active_analyst),
):
    """Fraud metrics in 5-minute buckets over the last *window_minutes*. Cached for 30 seconds."""

    async def build():
        return {
            "window_minutes": window_minutes,
            "buckets": await get_rolling_fraud_metrics(db, window_minutes=window_minutes),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    return await cache.cached(f"analytics:timeseries:{window_minutes}", 30, build)


@app.get("/analytics/alert-telemetry", tags=["Analytics"])
async def analytics_alert_telemetry(
    db: AsyncSession = Depends(get_db),
    _user: Analyst = Depends(get_current_active_analyst),
):
    """Open / investigating alert backlog. Cached for 30 seconds."""

    async def build():
        return {
            "telemetry": await get_alert_backlog(db),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    return await cache.cached("analytics:alert_telemetry", 30, build)


# ---------------------------------------------------------------------------
# DASHBOARD (JWT-PROTECTED, REDIS-CACHED)
# ---------------------------------------------------------------------------

@app.get("/dashboard/stats", tags=["Dashboard"])
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
    _user: Analyst = Depends(get_current_active_analyst),
):
    """Counts of transactions, flagged transactions and open alerts. Cached for 60 seconds."""

    async def build():
        total_tx = (await db.execute(select(func.count(Transaction.tx_id)))).scalar() or 0
        flagged_tx = (
            await db.execute(select(func.count(Transaction.tx_id)).where(Transaction.is_flagged.is_(True)))
        ).scalar() or 0
        open_alerts = (
            await db.execute(
                select(func.count(FraudAlert.alert_id)).where(FraudAlert.status == AlertStatusEnum.open)
            )
        ).scalar() or 0
        return {
            "total_transactions": total_tx,
            "flagged_transactions": flagged_tx,
            "open_alerts": open_alerts,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    return await cache.cached("dashboard_stats", 60, build)


# ---------------------------------------------------------------------------
# HEALTH
# ---------------------------------------------------------------------------

@app.get("/health", tags=["Health"])
async def health_check(response: Response):
    """Readiness probe: 503 unless the model artifacts are loaded and the database answers."""
    artifacts_loaded = model_manager.is_ready

    database_ok = True
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        database_ok = False

    healthy = artifacts_loaded and database_ok
    if not healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    body = {
        "status": "healthy" if healthy else "unavailable",
        "artifacts_loaded": artifacts_loaded,
        "database": database_ok,
        "redis": cache.is_available(),
    }
    if not config.IS_PRODUCTION and model_manager.load_error:
        body["model_error"] = model_manager.load_error
    return body
