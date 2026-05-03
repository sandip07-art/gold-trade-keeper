from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import MarketState
from ..adapters.market_data import get_adapter

router = APIRouter(tags=["ingest"])


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class CandleIn(BaseModel):
    time: str
    open: float
    high: float
    low: float
    close: float
    volume: Optional[float] = None


class NewsEventIn(BaseModel):
    time: str
    name: str
    impact: str   # HIGH | MEDIUM | LOW


class IngestPayload(BaseModel):
    xauusd_price:   Optional[float]          = None
    xauusd_candles: Optional[list[CandleIn]] = None
    dxy_price:      Optional[float]          = None
    dxy_candles:    Optional[list[CandleIn]] = None
    atr_current:    Optional[float]          = None
    atr_avg:        Optional[float]          = None
    news_events:    Optional[list[NewsEventIn]] = None
    server_time:    Optional[str]            = None   # ISO-8601 UTC


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/ingest", summary="Ingest raw market data")
def ingest(payload: IngestPayload, db: Session = Depends(get_db)):
    """
    Upsert the singleton MarketState row with incoming data.
    Partial updates are supported — only non-None fields are written.
    """
    state: MarketState = db.query(MarketState).filter(MarketState.id == 1).first()
    if not state:
        state = MarketState(id=1)
        db.add(state)

    if payload.xauusd_price   is not None: state.xauusd_price   = payload.xauusd_price
    if payload.xauusd_candles is not None: state.xauusd_candles = [c.model_dump() for c in payload.xauusd_candles]
    if payload.dxy_price      is not None: state.dxy_price      = payload.dxy_price
    if payload.dxy_candles    is not None: state.dxy_candles    = [c.model_dump() for c in payload.dxy_candles]
    if payload.atr_current    is not None: state.atr_current    = payload.atr_current
    if payload.atr_avg        is not None: state.atr_avg        = payload.atr_avg
    if payload.news_events    is not None: state.news_events    = [e.model_dump() for e in payload.news_events]
    if payload.server_time    is not None:
        state.server_time = datetime.fromisoformat(payload.server_time)

    state.updated_at = datetime.utcnow()
    db.commit()
    return {"status": "ok", "updated_at": state.updated_at.isoformat()}


@router.post("/ingest/simulate", summary="Pull from SimulatedAdapter and ingest")
def ingest_simulated(db: Session = Depends(get_db)):
    """Useful for dev — generates a fresh synthetic snapshot."""
    adapter = get_adapter("simulated")

    xauusd_candles = adapter.get_xauusd_candles()
    dxy_candles    = adapter.get_dxy_candles()
    atr_cur, atr_avg = adapter.get_atr()
    news           = adapter.get_news_events()
    server_time    = adapter.get_server_time()

    state: MarketState = db.query(MarketState).filter(MarketState.id == 1).first()
    if not state:
        state = MarketState(id=1)
        db.add(state)

    state.xauusd_price   = xauusd_candles[-1]["close"]
    state.xauusd_candles = xauusd_candles
    state.dxy_price      = dxy_candles[-1]["close"]
    state.dxy_candles    = dxy_candles
    state.atr_current    = atr_cur
    state.atr_avg        = atr_avg
    state.news_events    = news
    state.server_time    = server_time.replace(tzinfo=None)
    state.updated_at     = datetime.utcnow()

    db.commit()
    return {
        "status":       "ok",
        "xauusd_price": state.xauusd_price,
        "dxy_price":    state.dxy_price,
        "atr_current":  state.atr_current,
        "atr_avg":      state.atr_avg,
        "server_time":  state.server_time.isoformat(),
    }
