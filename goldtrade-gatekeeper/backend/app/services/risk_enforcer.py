"""
Risk Enforcer
─────────────
Hard limits per trading day (UTC):
  • max_trades_per_day = 3       → BLOCK if exceeded
  • risk_per_trade     = 1 %
  • max_daily_loss     = 2 %     → BLOCK if exceeded

Reads from DB to be stateful across process restarts.
"""
from datetime import datetime, date
from sqlalchemy.orm import Session


def check_risk_limits(
    db: Session,
    max_trades: int = 3,
    max_daily_loss_pct: float = 2.0,
) -> tuple[bool, list[str], dict]:
    """
    Returns:
        ok          – True if no limits breached
        blocks      – list of human-readable block reasons
        risk_info   – {trades_today, daily_loss_pct}
    """
    from ..models import DecisionLog, TradeRecord

    today_str = date.today().isoformat()
    today_start = datetime.fromisoformat(today_str + "T00:00:00")

    # Count ALLOWED decisions today (proxy for executed trades)
    trades_today: int = (
        db.query(DecisionLog)
        .filter(
            DecisionLog.timestamp >= today_start,
            DecisionLog.decision == "TRADE ALLOWED",
        )
        .count()
    )

    # Sum realised losses from TradeRecord table
    today_records = (
        db.query(TradeRecord)
        .filter(TradeRecord.date == today_str)
        .all()
    )
    daily_loss_pct: float = sum(
        abs(r.pnl_pct) for r in today_records if r.pnl_pct is not None and r.pnl_pct < 0
    )

    blocks: list[str] = []
    if trades_today >= max_trades:
        blocks.append(f"MAX TRADES REACHED ({trades_today}/{max_trades} today)")
    if daily_loss_pct >= max_daily_loss_pct:
        blocks.append(
            f"MAX DAILY LOSS REACHED ({daily_loss_pct:.2f}% / {max_daily_loss_pct}% limit)"
        )

    return (
        len(blocks) == 0,
        blocks,
        {"trades_today": trades_today, "daily_loss_pct": round(daily_loss_pct, 2)},
    )
