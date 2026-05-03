# FORCE REDEPLOY v2

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


def safe_list(val):
    return val if isinstance(val, list) else []


def safe_float(val):
    try:
        return float(val)
    except:
        return 0.0


def evaluate(db: Session, state: MarketState, strict_mode: bool = False) -> dict[str, Any]:
    try:
        # ── SAFE TIME ─────────────────
        dt = state.server_time or datetime.now(timezone.utc)
        if isinstance(dt, str):
            try:
                dt = datetime.fromisoformat(dt)
            except:
                dt = datetime.now(timezone.utc)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)

        blocks = []

        # ── SESSION ─────────────────
        session_name, session_ok = get_session(dt)
        if not session_ok:
            blocks.append("OUTSIDE SESSION")

        # ── NEWS ─────────────────
        news_blocked, news_names = is_in_news_window(
            safe_list(state.news_events),
            dt,
            window_minutes=settings.NEWS_WINDOW_MINUTES,
        )
        if news_blocked:
            blocks.append(f"NEWS WINDOW — {', '.join(news_names)}")

        # ── SAFE CANDLES ─────────────────
        xau_candles = safe_list(state.xauusd_candles)
        dxy_candles = safe_list(state.dxy_candles)

        # ── DXY BIAS ─────────────────
        raw_bias, bias_detail = compute_dxy_bias(dxy_candles)

        prior_biases = get_recent_bias_history(db, limit=1)
        stable_bias, bias_confirmed = require_persistence(
            raw_bias, prior_biases, required_count=2
        )

        # 🔥 FALLBACK MOMENTUM BIAS
        if raw_bias and raw_bias != "NEUTRAL":
            bias = raw_bias
        else:
            if len(dxy_candles) >= 2:
                prev = dxy_candles[-2]["close"]
                curr = dxy_candles[-1]["close"]
        
                if curr > prev:
                    bias = "USD STRONG → GOLD SELL"
                elif curr < prev:
                    bias = "USD WEAK → GOLD BUY"
                else:
                    bias = "NEUTRAL"
            else:
                bias = "NEUTRAL"

        # ── VOLATILITY ─────────────────
        atr_current = safe_float(state.atr_current)
        atr_avg     = safe_float(state.atr_avg)

        raw_vol_state, raw_vol_ok = check_volatility_expansion(
            atr_current, atr_avg, settings.ATR_EXPANSION_MULTIPLIER
        )

        _, vol_confirmed = require_persistence(
            raw_vol_state, get_recent_vol_history(db, limit=1), required_count=2
        )

        low_vol_flag = not raw_vol_ok
            
        # REMOVE volatility confirmed blocking
        
        # ── RISK ─────────────────
        risk_ok, risk_blocks, risk_info = check_risk_limits(
            db,
            max_trades=settings.MAX_TRADES_PER_DAY,
            max_daily_loss_pct=settings.MAX_DAILY_LOSS_PCT,
        )
        blocks.extend(risk_blocks)

        # ── DECISION ─────────────────
        if blocks:
            decision = DECISION_UNFAVORABLE
            reasons = blocks
        else:
            decision = DECISION_FAVORABLE
            reasons = [
                f"Session: {session_name}",
                f"Volatility: {raw_vol_state}",
                f"DXY Bias: {bias}",
            ]
        
            if low_vol_flag:
                reasons.append("LOW VOLATILITY (CAUTION)")
        # ── FINAL BIAS (SAFE) ─────────────────
        bias_str = str(bias)

        if "SELL" in bias_str:
            final_bias = "SELL"
        elif "BUY" in bias_str:
            final_bias = "BUY"
        else:
            final_bias = "NEUTRAL"

        # ── ENTRY ─────────────────
        entry_zone = get_entry_zone(
            safe_float(state.xauusd_price),
            xau_candles
        )
        # ── ADAPTIVE DECISION ENGINE ──        

        if atr_avg == 0:
            vol_level = "LOW"
        else:
            ratio = atr_current / atr_avg
            if ratio > 2:
                vol_level = "HIGH"
            elif ratio > 1.2:
                vol_level = "MEDIUM"
            else:
                vol_level = "LOW"

        aligned = (
            (final_bias == "SELL" and entry_zone == "PREMIUM") or
            (final_bias == "BUY" and entry_zone == "DISCOUNT")
        )

        if aligned:
            if vol_level == "HIGH":
                trade_decision = "TRADE"
            elif vol_level == "MEDIUM":
                trade_decision = "TRADE (REDUCED RISK)"
            else:
                trade_decision = "WAIT"
        else:
            trade_decision = "NO TRADE"

        # 🔥 FORCE CONSISTENCY WITH ENVIRONMENT
        if decision == DECISION_UNFAVORABLE:
            trade_decision = "NO TRADE"
        


        # ── LOGGING ─────────────────
        try:
            log_entry = DecisionLog(
                decision=decision,
                bias=bias,
                reasons=reasons,
                metrics={},
                advisory={},
                strict_mode=strict_mode,
            )
            db.add(log_entry)
            db.commit()
            db.refresh(log_entry)
            log_id = log_entry.id
            timestamp = log_entry.timestamp.isoformat()
        except:
            log_id = None
            timestamp = datetime.now(timezone.utc).isoformat()

        return {
            "decision": decision,
            "trade_decision": trade_decision,
            "bias": final_bias,
            "entry_zone": entry_zone,
            "reasons": reasons,
            "log_id": log_id,
            "timestamp": timestamp,
        }

    except Exception as e:
        # 🔥 NEVER CRASH
        return {
            "decision": "ERROR SAFE MODE",
            "trade_decision": "NO TRADE",
            "bias": "NEUTRAL",
            "entry_zone": "UNKNOWN",
            "reasons": [str(e)],
            "log_id": None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
