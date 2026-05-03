from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import MarketState
from ..services.gatekeeper import evaluate

router = APIRouter(tags=["decision"])


@router.get("/decision")
def get_decision(
    strict_mode: bool = Query(False),
    db: Session = Depends(get_db),
):
    try:
        state = db.query(MarketState).filter(MarketState.id == 1).first()

        if not state:
            return {
                "decision": "NO DATA",
                "trade_decision": "NO TRADE",
                "bias": "NEUTRAL",
                "entry_zone": "UNKNOWN",
                "reasons": ["No market data found"]
            }

        result = evaluate(db, state, strict_mode=strict_mode)
        return result

    except Exception as e:
        return {
            "decision": "ERROR SAFE MODE",
            "trade_decision": "NO TRADE",
            "bias": "NEUTRAL",
            "entry_zone": "UNKNOWN",
            "reasons": [str(e)]
        }
