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
                "reasons": ["No data in DB"]
            }

        try:
            result = evaluate(db, state, strict_mode=strict_mode)
            return result
        except Exception as e:
            return {
                "decision": "EVALUATE CRASH",
                "trade_decision": "NO TRADE",
                "bias": "NEUTRAL",
                "entry_zone": "UNKNOWN",
                "reasons": [f"evaluate failed: {str(e)}"]
            }

    except Exception as e:
        return {
            "decision": "ROUTE CRASH",
            "trade_decision": "NO TRADE",
            "bias": "NEUTRAL",
            "entry_zone": "UNKNOWN",
            "reasons": [str(e)]
        }
