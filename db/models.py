from sqlalchemy import Column, String, Float, DateTime
from sqlalchemy.orm import declarative_base
from datetime import datetime

Base = declarative_base()

class TradeIntent(Base):
    __tablename__ = 'trade_intents'
    id = Column(String, primary_key=True)
    symbol = Column(String, index=True)
    side = Column(String)
    amount = Column(Float)
    status = Column(String)  # PENDING/SUBMITTED/FILLED/TIMEOUT/FAILED
    created_at = Column(DateTime, default=datetime.utcnow)

class PositionRecord(Base):
    __tablename__ = 'positions'
    symbol = Column(String, primary_key=True)
    amount = Column(Float, default=0.0)
    entry_price = Column(Float, default=0.0)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class TradeLog(Base):
    __tablename__ = 'trade_logs'
    id = Column(String, primary_key=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    symbol = Column(String)
    side = Column(String)
    amount = Column(Float)
    price = Column(Float)
    status = Column(String)

class ReconciliationAudit(Base):
    __tablename__ = 'reconciliation_audit'
    id = Column(String, primary_key=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    symbol = Column(String)
    field = Column(String)
    exchange_value = Column(Float)
    local_value_before = Column(Float)
    action_taken = Column(String)
