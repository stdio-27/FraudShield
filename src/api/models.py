import uuid
import enum
from sqlalchemy import Column, Float, Boolean, String, SmallInteger, Enum
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP, JSONB
from .database import Base


class RoleEnum(str, enum.Enum):
    analyst = "analyst"
    admin = "admin"
    readonly = "readonly"


class AlertStatusEnum(str, enum.Enum):
    open = "open"
    investigating = "investigating"
    confirmed_fraud = "confirmed_fraud"
    false_positive = "false_positive"


class Analyst(Base):
    __tablename__ = "analysts"

    analyst_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(Enum(RoleEnum), default=RoleEnum.analyst, nullable=False)


class Transaction(Base):
    """
    TimescaleDB requires the partition key (transaction_time) to be part of
    the primary key for hypertable partitioning.
    """
    __tablename__ = "transactions"

    tx_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    transaction_time = Column(TIMESTAMP(timezone=True), primary_key=True, nullable=False)
    amount = Column(Float, nullable=False)

    v1 = Column(Float); v2 = Column(Float); v3 = Column(Float); v4 = Column(Float)
    v5 = Column(Float); v6 = Column(Float); v7 = Column(Float); v8 = Column(Float)
    v9 = Column(Float); v10 = Column(Float); v11 = Column(Float); v12 = Column(Float)
    v13 = Column(Float); v14 = Column(Float); v15 = Column(Float); v16 = Column(Float)
    v17 = Column(Float); v18 = Column(Float); v19 = Column(Float); v20 = Column(Float)
    v21 = Column(Float); v22 = Column(Float); v23 = Column(Float); v24 = Column(Float)
    v25 = Column(Float); v26 = Column(Float); v27 = Column(Float); v28 = Column(Float)

    hour_of_day = Column(SmallInteger)
    amount_zscore = Column(Float)
    fraud_score = Column(Float)
    is_flagged = Column(Boolean, default=False)


class FraudAlert(Base):
    __tablename__ = "fraud_alerts"

    alert_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tx_id = Column(UUID(as_uuid=True), nullable=False)
    fraud_score = Column(Float)
    shap_reasons = Column(JSONB)
    status = Column(Enum(AlertStatusEnum), default=AlertStatusEnum.open)

    # We omit a strict DB-level foreign key constraint here to bypass SQLAlchemy's
    # complexity with composite foreign keys mapped to TimescaleDB hypertables,
    # but logically tx_id maps to transactions.tx_id.
