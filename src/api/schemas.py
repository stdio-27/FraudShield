import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, List, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

# Finite, bounded floats: NaN/Infinity would poison the model input and the DB.
Finite = Annotated[float, Field(allow_inf_nan=False, ge=-1e6, le=1e6)]


class ShapReason(BaseModel):
    feature: str
    attribution_score: float
    direction: str


class TransactionRequest(BaseModel):
    transaction_id: str = Field(..., min_length=1, max_length=64)
    amount: float = Field(..., gt=0, le=1e9, allow_inf_nan=False)
    # Seconds since the start of the observation window; feeds hour_of_day / is_weekend features.
    time_seconds: float = Field(..., ge=0, le=1e9, allow_inf_nan=False)
    # Optional real event time; defaults to the time the request is received.
    transaction_time: Optional[datetime] = None
    v1: Finite; v2: Finite; v3: Finite; v4: Finite; v5: Finite
    v6: Finite; v7: Finite; v8: Finite; v9: Finite; v10: Finite
    v11: Finite; v12: Finite; v13: Finite; v14: Finite; v15: Finite
    v16: Finite; v17: Finite; v18: Finite; v19: Finite; v20: Finite
    v21: Finite; v22: Finite; v23: Finite; v24: Finite; v25: Finite
    v26: Finite; v27: Finite; v28: Finite

    @field_validator("transaction_time")
    @classmethod
    def _utc(cls, value: Optional[datetime]) -> Optional[datetime]:
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value


class TransactionResponse(BaseModel):
    transaction_id: str
    fraud_score: float
    is_flagged: bool
    decision: str
    shap_reasons: Optional[List[ShapReason]] = None
    latency_ms: int


class UserRole(str, Enum):
    analyst = "analyst"
    admin = "admin"
    readonly = "readonly"


class AnalystCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=12, max_length=72)
    role: UserRole = UserRole.analyst

    @field_validator("password")
    @classmethod
    def _bcrypt_limit(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must be at most 72 bytes when UTF-8 encoded")
        return value


class AnalystResponse(BaseModel):
    analyst_id: str
    email: EmailStr
    role: str


class Token(BaseModel):
    access_token: str
    token_type: str


class AlertStatus(str, Enum):
    open = "open"
    investigating = "investigating"
    confirmed_fraud = "confirmed_fraud"
    false_positive = "false_positive"


class AlertStatusUpdate(BaseModel):
    status: AlertStatus


class AlertResponse(BaseModel):
    alert_id: uuid.UUID
    tx_id: uuid.UUID
    fraud_score: Optional[float] = None
    status: AlertStatus
    shap_reasons: Optional[List[ShapReason]] = None
    created_at: Optional[datetime] = None
    # Transaction context (null if the transaction row is missing)
    amount: Optional[float] = None
    transaction_time: Optional[datetime] = None
    external_id: Optional[str] = None


class AlertListResponse(BaseModel):
    items: List[AlertResponse]
    total: int
    limit: int
    offset: int
