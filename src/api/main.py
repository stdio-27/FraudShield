import sys
import os
import time
import uuid
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import json
from datetime import datetime, timezone, timedelta
import logging
import redis.asyncio as redis
import src.database.init_db
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import text, func

from .schemas import TransactionRequest, TransactionResponse, AnalystCreate, AnalystResponse, Token
from .services import model_manager
from .database import engine, Base, get_db
from .models import Transaction, FraudAlert, Analyst, RoleEnum
from .auth import hash_password, verify_password, create_access_token, get_current_active_analyst
from .analytics import get_rolling_fraud_metrics, get_fraud_summary, get_top_at_risk_analysts
from .alerts import evaluate_and_dispatch_alert

logging.basicConfig(level=logging.INFO)

# Project anchor date: Kaggle dataset time_seconds are elapsed seconds from
# the first transaction.  We anchor them to a fixed base date so that
# datetime.fromtimestamp produces meaningful wall-clock timestamps.
_ANCHOR_DATE = datetime(2025, 1, 1, tzinfo=timezone.utc)

# Dynamic CORS origins — never use "*" in production.
_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "FRONTEND_PRODUCTION_URL", "http://localhost:5173"
    ).split(",")
    if origin.strip()
]

redis_client = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Load ML Models
    try:
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        models_dir = os.path.join(base_dir, "models")
        model_manager.load_artifacts(models_dir)
    except Exception as e:
        logging.error(f"Failed to load ML artifacts: {e}")

    # 2. Database Initialization & TimescaleDB setup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Create hypertable
        try:
            await conn.execute(text(
                "SELECT create_hypertable('transactions', 'transaction_time', if_not_exists => TRUE);"
            ))
            await conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_transactions_time ON transactions (transaction_time DESC);"
            ))
        except Exception as e:
            logging.warning(
                f"TimescaleDB hypertable setup note (may already exist or extension not loaded): {e}"
            )

    # 3. Redis Initialization
    global redis_client
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    redis_client = redis.from_url(redis_url, decode_responses=True)

    yield

    # Shutdown
    await redis_client.aclose()


app = FastAPI(
    title="FraudShield API",
    description="Real-time Fraud Detection with Persistent DB, Cache, Analytics & Alerting",
    version="1.0.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS — dynamic origins from environment; no wildcards in production
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# AUTH ROUTES
# ---------------------------------------------------------------------------

@app.post("/auth/register", response_model=AnalystResponse)
async def register(analyst_data: AnalystCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Analyst).where(Analyst.email == analyst_data.email))
    if result.scalars().first():
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed_pw = hash_password(analyst_data.password)

    # Safely coerce the incoming role string to the RoleEnum; default to analyst
    try:
        role_enum = RoleEnum(analyst_data.role)
    except ValueError:
        role_enum = RoleEnum.analyst

    new_analyst = Analyst(
        email=analyst_data.email,
        password_hash=hashed_pw,
        role=role_enum,
    )

    db.add(new_analyst)
    await db.commit()
    await db.refresh(new_analyst)

    return AnalystResponse(
        analyst_id=str(new_analyst.analyst_id),
        email=new_analyst.email,
        role=new_analyst.role.value,
    )


@app.post("/auth/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Analyst).where(Analyst.email == form_data.username))
    analyst = result.scalars().first()

    if not analyst or not verify_password(form_data.password, analyst.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=60)
    access_token = create_access_token(
        data={"sub": analyst.email, "role": analyst.role.value},
        expires_delta=access_token_expires,
    )
    return {"access_token": access_token, "token_type": "bearer"}


# ---------------------------------------------------------------------------
# TRANSACTION SCORING  (now with real-time alert dispatch)
# ---------------------------------------------------------------------------

@app.post("/transactions/score", response_model=TransactionResponse)
async def score_transaction(request: TransactionRequest, db: AsyncSession = Depends(get_db)):
    start_time = time.perf_counter()

    req_dict = request.model_dump() if hasattr(request, "model_dump") else request.dict()
    try:
        fraud_score, is_flagged, decision, shap_reasons = model_manager.predict(req_dict)

        # --- Safe UUID parsing (handles plain-text transaction IDs) ---
        try:
            tx_id = uuid.UUID(request.transaction_id)
        except ValueError:
            tx_id = uuid.uuid4()
            logging.warning(
                f"Non-UUID transaction_id '{request.transaction_id}' received. "
                f"Generated fallback UUID: {tx_id}"
            )

        # --- Timestamp mapping ---
        computed_timestamp = _ANCHOR_DATE + timedelta(seconds=request.time_seconds)

        # --- Extract engineered features for DB storage ---
        df_eng = model_manager._engineer_features(req_dict).iloc[0]

        # --- Build Transaction ORM object ---
        new_tx = Transaction(
            tx_id=tx_id,
            transaction_time=computed_timestamp,
            amount=request.amount,
            v1=request.v1, v2=request.v2, v3=request.v3, v4=request.v4,
            v5=request.v5, v6=request.v6, v7=request.v7, v8=request.v8,
            v9=request.v9, v10=request.v10, v11=request.v11, v12=request.v12,
            v13=request.v13, v14=request.v14, v15=request.v15, v16=request.v16,
            v17=request.v17, v18=request.v18, v19=request.v19, v20=request.v20,
            v21=request.v21, v22=request.v22, v23=request.v23, v24=request.v24,
            v25=request.v25, v26=request.v26, v27=request.v27, v28=request.v28,
            hour_of_day=int(df_eng["hour_of_day"]),
            amount_zscore=float(df_eng["amount_zscore"]),
            fraud_score=fraud_score,
            is_flagged=is_flagged,
        )
        db.add(new_tx)

        # --- Auto-create fraud alert if flagged ---
        if is_flagged:
            new_alert = FraudAlert(
                tx_id=tx_id,
                fraud_score=fraud_score,
                shap_reasons=shap_reasons,
            )
            db.add(new_alert)

        await db.commit()

        # --- Real-time alert dispatch (fire-and-forget, non-blocking) ---
        evaluate_and_dispatch_alert(
            tx_id=tx_id,
            amount=request.amount,
            fraud_score=fraud_score,
            is_flagged=is_flagged,
            shap_reasons=shap_reasons,
        )

    except Exception as e:
        logging.error(f"Inference/DB error: {e}", exc_info=True)
        await db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

    end_time = time.perf_counter()
    latency_ms = int((end_time - start_time) * 1000)

    return TransactionResponse(
        transaction_id=request.transaction_id,
        fraud_score=fraud_score,
        is_flagged=is_flagged,
        decision=decision,
        shap_reasons=shap_reasons,
        latency_ms=latency_ms,
    )


# ---------------------------------------------------------------------------
# ANALYTICS ROUTES  (JWT-PROTECTED, REDIS-CACHED)
# ---------------------------------------------------------------------------

@app.get("/analytics/summary", tags=["Analytics"])
async def analytics_summary(
    db: AsyncSession = Depends(get_db),
    current_user: Analyst = Depends(get_current_active_analyst),
):
    """
    Returns a high-level fraud summary across all transactions.
    Cached in Redis for 30 seconds.
    """
    cache_key = "analytics:summary"
    cached = await redis_client.get(cache_key)
    if cached:
        return json.loads(cached)

    summary = await get_fraud_summary(db)
    summary["timestamp"] = datetime.now(timezone.utc).isoformat()

    await redis_client.set(cache_key, json.dumps(summary), ex=30)
    return summary


@app.get("/analytics/time-series", tags=["Analytics"])
async def analytics_time_series(
    window_minutes: int = 60,
    db: AsyncSession = Depends(get_db),
    current_user: Analyst = Depends(get_current_active_analyst),
):
    """
    Returns rolling fraud metrics grouped into 5-minute time buckets
    over the last *window_minutes* (default 60).
    Cached in Redis for 30 seconds, keyed by window size.
    """
    cache_key = f"analytics:timeseries:{window_minutes}"
    cached = await redis_client.get(cache_key)
    if cached:
        return json.loads(cached)

    buckets = await get_rolling_fraud_metrics(db, window_minutes=window_minutes)
    result = {
        "window_minutes": window_minutes,
        "buckets": buckets,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    await redis_client.set(cache_key, json.dumps(result), ex=30)
    return result


@app.get("/analytics/alert-telemetry", tags=["Analytics"])
async def analytics_alert_telemetry(
    db: AsyncSession = Depends(get_db),
    current_user: Analyst = Depends(get_current_active_analyst),
):
    """
    Returns audit telemetry on open/investigating alert volume.
    Cached in Redis for 30 seconds.
    """
    cache_key = "analytics:alert_telemetry"
    cached = await redis_client.get(cache_key)
    if cached:
        return json.loads(cached)

    telemetry = await get_top_at_risk_analysts(db)
    result = {
        "telemetry": telemetry,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    await redis_client.set(cache_key, json.dumps(result), ex=30)
    return result


# ---------------------------------------------------------------------------
# DASHBOARD (JWT-PROTECTED, REDIS-CACHED)
# ---------------------------------------------------------------------------

@app.get("/dashboard/stats", tags=["Dashboard"])
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
    current_user: Analyst = Depends(get_current_active_analyst),
):
    """Protected endpoint to retrieve fraud stats, cached in Redis."""
    cache_key = "dashboard_stats"
    cached_stats = await redis_client.get(cache_key)

    if cached_stats:
        return json.loads(cached_stats)

    # Total transactions
    total_tx_result = await db.execute(select(func.count(Transaction.tx_id)))
    total_tx = total_tx_result.scalar() or 0

    # Flagged transactions
    flagged_tx_result = await db.execute(
        select(func.count(Transaction.tx_id)).where(Transaction.is_flagged == True)  # noqa: E712
    )
    flagged_tx = flagged_tx_result.scalar() or 0

    # Open Alerts
    open_alerts_result = await db.execute(
        select(func.count(FraudAlert.alert_id)).where(FraudAlert.status == "open")
    )
    open_alerts = open_alerts_result.scalar() or 0

    stats = {
        "total_transactions": total_tx,
        "flagged_transactions": flagged_tx,
        "open_alerts": open_alerts,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # Cache for 60 seconds
    await redis_client.set(cache_key, json.dumps(stats), ex=60)

    return stats


# ---------------------------------------------------------------------------
# HEALTH
# ---------------------------------------------------------------------------

@app.get("/health", tags=["Health"])
async def health_check():
    """Health check to verify API and Model Manager readiness."""
    artifacts_loaded = model_manager.model is not None
    return {"status": "healthy", "artifacts_loaded": artifacts_loaded}
