"""
Historical Context
──────────────────
Queries TradeRecord for win-rate and avg R:R under a given market context.
Only returned if sample size ≥ min_sample (default 20).

Confidence tiers (sample-size based):
  LOW    : 20–49  trades  — indicative, treat with caution
  MEDIUM : 50–100 trades  — reasonably reliable
  HIGH   : > 100  trades  — statistically robust

Context key: (dxy_state, volatility_state, session)
"""
from sqlalchemy.orm import Session
from typing import Any


def _sample_confidence(n: int) -> str:
    if n > 100:
        return "HIGH"
    if n >= 50:
        return "MEDIUM"
    return "LOW"


def get_historical_stats(
    db: Session,
    dxy_state: str,
    vol_state: str,
    session: str,
    min_sample: int = 20,
) -> dict[str, Any] | None:
    from ..models import TradeRecord

    records = (
        db.query(TradeRecord)
        .filter(
            TradeRecord.dxy_state == dxy_state,
            TradeRecord.volatility_state == vol_state,
            TradeRecord.session == session,
        )
        .all()
    )

    n = len(records)
    if n < min_sample:
        return None

    wins = [r for r in records if r.result == "WIN"]
    win_rate = len(wins) / n * 100

    rr_values  = [r.rr      for r in records if r.rr      is not None]
    pnl_values = [r.pnl_pct for r in records if r.pnl_pct is not None]
    avg_rr  = sum(rr_values)  / len(rr_values)  if rr_values  else 0.0
    avg_pnl = sum(pnl_values) / len(pnl_values) if pnl_values else 0.0

    confidence = _sample_confidence(n)

    return {
        "win_rate":        round(win_rate, 1),
        "avg_rr":          round(avg_rr, 2),
        "avg_pnl_pct":     round(avg_pnl, 2),
        "sample_size":     n,
        "data_confidence": confidence,          # LOW | MEDIUM | HIGH
        "confidence_note": _confidence_note(confidence, n),
        "context": {
            "dxy_state":  dxy_state,
            "vol_state":  vol_state,
            "session":    session,
        },
    }


def _confidence_note(confidence: str, n: int) -> str:
    if confidence == "HIGH":
        return f"Statistically robust ({n} trades) — interpret with high confidence"
    if confidence == "MEDIUM":
        return f"Reasonably reliable ({n} trades) — treat as a useful guide"
    return f"Indicative only ({n} trades) — limited sample, use with caution"


def get_all_stats_summary(db: Session) -> list[dict[str, Any]]:
    """Aggregate stats for all context combinations (for dashboard overview)."""
    from ..models import TradeRecord
    from sqlalchemy import func

    rows = (
        db.query(
            TradeRecord.dxy_state,
            TradeRecord.volatility_state,
            TradeRecord.session,
            func.count(TradeRecord.id).label("total"),
        )
        .group_by(TradeRecord.dxy_state, TradeRecord.volatility_state, TradeRecord.session)
        .all()
    )

    summaries = []
    for row in rows:
        stats = get_historical_stats(db, row.dxy_state, row.volatility_state, row.session)
        if stats:
            summaries.append(stats)

    # Sort by descending confidence then win_rate
    order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    summaries.sort(key=lambda s: (order.get(s["data_confidence"], 9), -s["win_rate"]))
    return summaries
