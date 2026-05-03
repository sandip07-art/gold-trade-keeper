from sqlalchemy import Column, Integer, String, Float, DateTime, JSON, Boolean
from datetime import datetime
from .database import Base


class MarketState(Base):
    """Singleton row holding the latest ingested market data."""
    __tablename__ = "market_state"

    id = Column(Integer, primary_key=True, default=1)
    xauusd_price = Column(Float, nullable=True)
    xauusd_candles = Column(JSON, nullable=True)   # list of OHLCV dicts
    dxy_price = Column(Float, nullable=True)
    dxy_candles = Column(JSON, nullable=True)       # 1h candles for bias engine
    atr_current = Column(Float, nullable=True)
    atr_avg = Column(Float, nullable=True)
    news_events = Column(JSON, nullable=True)       # [{time, name, impact}]
    server_time = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DecisionLog(Base):
    """Immutable audit log of every gate evaluation."""
    __tablename__ = "decision_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    decision = Column(String(32))          # TRADE ALLOWED | NO TRADE | BLOCKED
    bias = Column(String(64))
    reasons = Column(JSON)                 # list[str]
    metrics = Column(JSON)                 # {atr, atr_avg, session, vol_state, …}
    advisory = Column(JSON)               # {summary, confidence, playbook}
    strict_mode = Column(Boolean, default=False)


class TradeRecord(Base):
    """Optional: user-recorded trade outcomes for historical context."""
    __tablename__ = "trade_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    date = Column(String(10), index=True)          # YYYY-MM-DD
    result = Column(String(8))                     # WIN | LOSS | BE
    rr = Column(Float, nullable=True)              # risk-reward achieved
    dxy_state = Column(String(64))
    volatility_state = Column(String(16))
    session = Column(String(16))
    pnl_pct = Column(Float, nullable=True)         # % of account
