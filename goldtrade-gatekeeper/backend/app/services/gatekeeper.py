from app.services.decision_engine import (
    get_entry_zone,
    get_trade_decision
)

from datetime import datetime, timezone
from sqlalchemy.orm import Session
from typing import Any

from .session_filter   import get_session
from .news_blocker     import is_in_news_window
from .dxy_bias         import compute_dxy_bias
from .volatility       import check_volatility_expansion
from .risk_enforcer    import check_risk_limits
from .advisory         import generate_advisory
from .state_stability  import (
    require_persistence,
    get_recent_bias_history,
    get_recent_vol_history,
)
from ..config          import settings
from ..models          import MarketState, DecisionLog

DECISION_FAVORABLE   = "CONDITIONS FAVORABLE"
DECISION_UNFAVORABLE = "CONDITIONS UNFAVORABLE"

STABILITY_CANDLES = 2


def evaluate(
    db: Session,
    state: MarketState,
    strict_mode: bool = False,
) -> dict[str, Any]:

    dt: datetime = state.server_time or datetime.now(timezone.utc)
    if isinstance(dt, str):
        dt = datetime.fromisoformat(dt)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    blocks: list[str] = []

    # ── Session ─────────────────────────
    session_name, session_ok = get_session(dt)
    if not session_ok:
        blocks.append("OUTSIDE SESSION")

    # ── News ────────────────────────────
    news_blocked, news_names = is_in_news_window(
        state.news_events or [],
        dt,
        window_minutes=settings.NEWS_WINDOW_MINUTES,
    )
    if news_blocked:
        blocks.append(f"NEWS WINDOW — {', '.join(news_names)}")

    # ── DXY Bias ────────────────────────
    raw_bias, bias_detail = compute_dxy_bias(state.dxy_candles or [])

    prior_biases = get_recent_bias_history(db, limit=STABILITY_CANDLES - 1)
    stable_bias, bias_confirmed = require_persistence(
        raw_bias, prior_biases, required_count=STABILITY_CANDLES
    )

    # ✅ Early + confirmed bias logic
    if bias_confirmed:
        bias = stable_bias
    else:
        bias = raw_bias if raw_bias != "NEUTRAL" else "NEUTRAL"

    bias_pending = raw_bias != "NEUTRAL" and not bias_confirmed

    # ── Volatility ──────────────────────
    atr_current = state.atr_current or 0.0
    atr_avg     = state.atr_avg or 0.0

    multiplier = settings.ATR_EXPANSION_MULTIPLIER * (1.2 if strict_mode else 1.0)

    raw_vol_state, raw_vol_ok = check_volatility_expansion(
        atr_current, atr_avg, multiplier
    )

    prior_vols = get_recent_vol_history(db, limit=STABILITY_CANDLES - 1)
    _, vol_confirmed = require_persistence(
        raw_vol_state, prior_vols, required_count=STABILITY_CANDLES
    )

    vol_state = raw_vol_state

    if not raw_vol_ok:
        blocks.append("LOW VOLATILITY — ATR below threshold")
    elif not vol_confirmed:
        blocks.append("VOLATILITY UNCONFIRMED")

    # ── Risk ────────────────────────────
    risk_ok, risk_blocks, risk_info = check_risk_limits(
        db,
        max_trades=settings.MAX_TRADES_PER_DAY,
        max_daily_loss_pct=settings.MAX_DAILY_LOSS_PCT,
    )
    blocks.extend(risk_blocks)

    # ── Decision ────────────────────────
    if blocks:
        decision = DECISION_UNFAVORABLE
        reasons = blocks
    else:
        decision = DECISION_FAVORABLE
        reasons = [
            f"Session: {session_name}",
            f"Volatility: {vol_state}",
            f"DXY Bias: {bias}",
            f"Risk: {risk_info['trades_today']}/{settings.MAX_TRADES_PER_DAY}"
        ]

    # ── Metrics ─────────────────────────
    metrics = {
        "atr": atr_current,
        "atr_avg": atr_avg,
        "dxy_state": bias,
        "dxy_raw": raw_bias,
        "dxy_confirmed": bias_confirmed,
        "dxy_pending": bias_pending,
        "vol_confirmed": vol_confirmed,
        "session": session_name,
        "xauusd_price": state.xauusd_price,
        "dxy_price": state.dxy_price
    }

    # ── Advisory ────────────────────────
    advisory = generate_advisory(
        session=session_name,
        vol_state=vol_state,
        bias=bias,
        news_blocked=news_blocked,
        strict_mode=strict_mode,
    )

    # ── FINAL BIAS (DXY PRIORITY) ───────
    if "SELL" in bias:
        final_bias = "SELL"
    elif "BUY" in bias:
        final_bias = "BUY"
    else:
        final_bias = "NEUTRAL"

    # ── Entry + Decision ────────────────
    entry_zone = get_entry_zone(
        state.xauusd_price or 0,
        state.xauusd_candles or []
    )

    env_ok = vol_confirmed and session_name in ["NEW_YORK", "LONDON"]

    trade_decision = get_trade_decision(env_ok, final_bias, entry_zone)

    # ── Logging ─────────────────────────
    log_entry = DecisionLog(
        decision=decision,
        bias=bias,
        reasons=reasons,
        metrics=metrics,
        advisory=advisory,
        strict_mode=strict_mode,
    )
    db.add(log_entry)
    db.commit()
    db.refresh(log_entry)

    return {
        "decision": decision,
        "trade_decision": trade_decision,
        "bias": final_bias,
        "entry_zone": entry_zone,
        "reasons": reasons,
        "metrics": metrics,
        "advisory": advisory,
        "log_id": log_entry.id,
        "timestamp": log_entry.timestamp.isoformat(),
    }
