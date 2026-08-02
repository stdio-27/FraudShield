from pydantic import BaseModel, EmailStr, Field
from typing import List, Optional
from datetime import datetime
from enum import Enum

class ShapReason(BaseModel):
    feature: str
    attribution_score: float
    direction: str

class TransactionRequest(BaseModel):
    transaction_id: str
    amount: float = Field(..., gt=0)
    time_seconds: float
    v1: float; v2: float; v3: float; v4: float; v5: float
    v6: float; v7: float; v8: float; v9: float; v10: float
    v11: float; v12: float; v13: float; v14: float; v15: float
    v16: float; v17: float; v18: float; v19: float; v20: float
    v21: float; v22: float; v23: float; v24: float; v25: float
    v26: float; v27: float; v28: float

class TransactionResponse(BaseModel):
    transaction_id: str
    fraud_score: float
    is_flagged: bool
    decision: str
    shap_reasons: Optional[List[ShapReason]] = None
    latency_ms: int

class UserRole(str,Enum):
    analyst="analyst"
    admin="admin"
    readonly="readonly"

class AnalystCreate(BaseModel):
    email: EmailStr
    password: str
    role: UserRole=UserRole.analyst

class AnalystResponse(BaseModel):
    analyst_id: str
    email: EmailStr
    role: str

class Token(BaseModel):
    access_token: str
    token_type: str
