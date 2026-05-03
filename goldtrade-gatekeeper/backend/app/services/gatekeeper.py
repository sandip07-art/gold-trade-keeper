from app.services.decision_engine import (
    get_dxy_bias,
    get_structure_bias,
    get_final_bias,
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
DECISION_NO_TRADE    = "NO TRADE"

DECISION_ALLOWED = DECISION_FAVORABLE
DECISION_BLOCKED = DECISION_UNFAVORABLE

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

    session_name, session_ok = get_session(dt)
    if not session_ok:
        blocks.append("OUTSIDE SESSION")

    news_blocked, news_names = is_in_news_window(
        state.news_events or [],
        dt,
        window_minutes=settings.NEWS_WINDOW_MINUTES,
    )
    if news_blocked:
        events_str = ", ".join(news_names)
        blocks.append(f"NEWS WINDOW — {events_str}")

    raw_bias, bias_detail = compute_dxy_bias(state.dxy_candles or [])

    prior_biases = get_recent_bias_history(db, limit=STABILITY_CANDLES - 1)
    stable_bias, bias_confirmed = require_persistence(
        raw_bias, prior_biases, required_count=STABILITY_CANDLES
    )

    bias = stable_bias if bias_confirmed else "NEUTRAL"
    bias_pending = raw_bias != "NEUTRAL" and not bias_confirmed

    atr_current: float = state.atr_current or 0.0
    atr_avg:     float = state.atr_avg or 0.0
    multiplier = settings.ATR_EXPANSION_MULTIPLIER * (1.2 if strict_mode else 1.0)

    raw_vol_state, raw_vol_ok = check_volatility_expansion(atr_current, atr_avg, multiplier)

    prior_vols = get_recent_vol_history(db, limit=STABILITY_CANDLES - 1)
    _, vol_confirmed = require_persistence(
        raw_vol_state, prior_vols, required_count=STABILITY_CANDLES
    )

    vol_state = raw_vol_state
    vol_ok = raw_vol_ok and vol_confirmed

    if not raw_vol_ok:
        blocks.append("LOW VOLATILITY — ATR below expansion threshold")
    elif not vol_confirmed:
        blocks.append(
            f"VOLATILITY UNCONFIRMED — {raw_vol_state} seen but requires "
            f"{STABILITY_CANDLES} consecutive candles (stability check)"
        )

    risk_ok, risk_blocks, risk_info = check_risk_limits(
        db,
        max_trades=settings.MAX_TRADES_PER_DAY,
        max_daily_loss_pct=settings.MAX_DAILY_LOSS_PCT,
    )
    blocks.extend(risk_blocks)

    if blocks:
        decision = DECISION_UNFAVORABLE
        reasons  = blocks
    else:
        decision = DECISION_FAVORABLE
        reasons  = [
            f"Session: {session_name}",
            f"Volatility: {vol_state} (confirmed {STABILITY_CANDLES} candles)",
            f"DXY Bias: {bias}" + (" (confirmed)" if bias_confirmed else ""),
            f"Risk: {risk_info['trades_today']}/{settings.MAX_TRADES_PER_DAY} trades today",
        ]

    metrics = {
        "atr":              round(atr_current, 4),
        "atr_avg":          round(atr_avg, 4),
        "atr_ratio":        round(atr_current / atr_avg, 3) if atr_avg else 0,
        "dxy_state":        bias,
        "dxy_raw":          raw_bias,
        "dxy_confirmed":    bias_confirmed,
        "dxy_pending":      bias_pending,
        "dxy_momentum":     bias_detail,
        "session":          session_name,
        "vol_state":        vol_state,
        "vol_confirmed":    vol_confirmed,
        "trades_today":     risk_info["trades_today"],
        "daily_loss_pct":   risk_info["daily_loss_pct"],
        "xauusd_price":     state.xauusd_price,
        "dxy_price":        state.dxy_price,
        "strict_mode":      strict_mode,
        "stability_candles": STABILITY_CANDLES,
    }

    advisory = generate_advisory(
        session=session_name,
        vol_state=vol_state,
        bias=bias,
        news_blocked=news_blocked,
        strict_mode=strict_mode,
    )

    # =========================
    # NEW DECISION ENGINE LAYER
    # =========================

    xau_candles = state.xauusd_candles or []
    dxy_candles = state.dxy_candles or []

    dxy_bias = get_dxy_bias(dxy_candles)
    structure_bias = get_structure_bias(xau_candles)
    final_bias = get_final_bias(dxy_bias, structure_bias)

    entry_zone = get_entry_zone(
        state.xauusd_price or 0,
        xau_candles
    )

    env_ok = (
        vol_confirmed and session_name in ["NEW_YORK", "LONDON"]
    )

    trade_decision = get_trade_decision(env_ok, final_bias, entry_zone)

    # =========================

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
        "decision":  decision,

        # NEW OUTPUTS
        "trade_decision": trade_decision,
        "bias": final_bias,
        "entry_zone": entry_zone,

        "reasons":   reasons,
        "metrics":   metrics,
        "advisory":  advisory,
        "log_id":    log_entry.id,
        "timestamp": log_entry.timestamp.isoformat(),
    }
