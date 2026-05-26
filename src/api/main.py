import os
import time
import logging
from fastapi import FastAPI, HTTPException
from contextlib import asynccontextmanager
from .schemas import TransactionRequest, TransactionResponse
from .services import model_manager

logging.basicConfig(level=logging.INFO)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle event to load ML models purely once at startup into memory."""
    try:
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        models_dir = os.path.join(base_dir, "models")
        model_manager.load_artifacts(models_dir)
    except Exception as e:
        logging.error(f"Failed to load ML artifacts: {e}")
        # Allows API to start and fail gracefully on request if models are missing
    yield
    logging.info("Shutting down API...")

app = FastAPI(
    title="FraudShield Serving API",
    description="Real-time <300ms Credit Card Fraud Detection API",
    version="0.3.0",
    lifespan=lifespan
)

@app.post("/transactions/score", response_model=TransactionResponse)
async def score_transaction(request: TransactionRequest):
    """Scores an incoming transaction for fraud probability."""
    start_time = time.perf_counter()
    
    try:
        # Use model_dump if using Pydantic V2, dict for V1
        req_dict = request.dict() if hasattr(request, "dict") else request.model_dump()
        fraud_score, is_flagged, decision, shap_reasons = model_manager.predict(req_dict)
    except Exception as e:
        logging.error(f"Inference error: {e}")
        raise HTTPException(status_code=500, detail="Internal inference error.")
        
    end_time = time.perf_counter()
    latency_ms = int((end_time - start_time) * 1000)
    
    return TransactionResponse(
        transaction_id=request.transaction_id,
        fraud_score=fraud_score,
        is_flagged=is_flagged,
        decision=decision,
        shap_reasons=shap_reasons,
        latency_ms=latency_ms
    )

@app.get("/health", tags=["Health"])
async def health_check():
    """Health check to verify API and Model Manager readiness."""
    artifacts_loaded = model_manager.model is not None
    return {
        "status": "healthy",
        "artifacts_loaded": artifacts_loaded
    }
