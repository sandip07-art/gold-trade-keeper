from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import MarketState
from ..services.gatekeeper import evaluate
from ..services.historical import get_historical_stats, get_all_stats_summary

router = APIRouter(tags=["decision"])


@router.get("/decision", summary="Evaluate current market state and return gate decision")
def get_decision(
    strict_mode: bool = Query(False, description="Apply stricter ATR multiplier (×1.2)"),
    db: Session = Depends(get_db),
):
    state: MarketState | None = db.query(MarketState).filter(MarketState.id == 1).first()

    if not state:
        return {
            "error": (
                "No market data found. POST /ingest or call /ingest/simulate first, "
                "or run `python seed.py` to populate demo data."
            )
        }

    # Core decision logic (includes your NEW bias + trade_decision)
    result = evaluate(db, state, strict_mode=strict_mode)

    # Attach historical context
    result["historical"] = get_historical_stats(
        db,
        dxy_state=result["metrics"]["dxy_state"],
        vol_state=result["metrics"]["vol_state"],
        session=result["metrics"]["session"],
    )

    return result


@router.get("/decision/state", summary="Return raw MarketState without running gates")
def get_state(db: Session = Depends(get_db)):
    state: MarketState | None = db.query(MarketState).filter(MarketState.id == 1).first()

    if not state:
        return {"error": "No market data ingested yet."}

    return {
        "xauusd_price": state.xauusd_price,
        "dxy_price": state.dxy_price,
        "atr_current": state.atr_current,
        "atr_avg": state.atr_avg,
        "news_events": state.news_events,
        "server_time": state.server_time.isoformat() if state.server_time else None,
        "updated_at": state.updated_at.isoformat() if state.updated_at else None,
    }


@router.get("/stats", summary="Historical performance stats across all context combinations")
def get_stats(db: Session = Depends(get_db)):
    return get_all_stats_summary(db)
