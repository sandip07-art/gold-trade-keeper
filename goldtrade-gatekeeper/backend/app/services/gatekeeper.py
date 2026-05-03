from app.services.decision_engine import (
    get_entry_zone,
)

from .fvg import detect_fvg
from .ob import detect_ob
from .confirmation import detect_confirmation

from datetime import datetime, timezone
from sqlalchemy.orm import Session
from typing import Any

from .session_filter   import get_session
from .news_blocker     import is_in_news_window
from .dxy_bias         import compute_dxy_bias
from .volatility       import check_volatility_expansion
from .risk_enforcer    import check_risk_limits
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
        # ── TIME ─────────────────
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

        # ── DATA ─────────────────
        xau_candles = safe_list(state.xauusd_candles)
        dxy_candles = safe_list(state.dxy_candles)

        # ── BIAS ─────────────────
        raw_bias, _ = compute_dxy_bias(dxy_candles)

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
            elif len(dxy_candles) == 1:
                c = dxy_candles[-1]
                if c["close"] > c["open"]:
                    bias = "USD STRONG → GOLD SELL"
                elif c["close"] < c["open"]:
                    bias = "USD WEAK → GOLD BUY"
                else:
                    bias = "NEUTRAL"
            else:
                bias = "NEUTRAL"

        # ── FINAL BIAS ─────────────────
        if "SELL" in bias:
            final_bias = "SELL"
        elif "BUY" in bias:
            final_bias = "BUY"
        else:
            final_bias = "NEUTRAL"

        # ── VOLATILITY ─────────────────
        atr_current = safe_float(state.atr_current)
        atr_avg = safe_float(state.atr_avg)

        raw_vol_state, raw_vol_ok = check_volatility_expansion(
            atr_current, atr_avg, settings.ATR_EXPANSION_MULTIPLIER
        )

        low_vol_flag = not raw_vol_ok

        # ── RISK ─────────────────
        _, risk_blocks, _ = check_risk_limits(
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

        # ── ENTRY ZONE ─────────────────
        entry_zone = get_entry_zone(
            safe_float(state.xauusd_price),
            xau_candles
        )

        # ── FVG ─────────────────
        fvg = detect_fvg(xau_candles)
        print("DEBUG FVG:", fvg)
        
        # ── OB ─────────────────
        ob = detect_ob(xau_candles)

        ob_near_fvg = False
        if fvg and ob:
            f_low, f_high = fvg["zone"]
            o_low, o_high = ob["zone"]
            if not (o_high < f_low or o_low > f_high):
                ob_near_fvg = True

        # ── CONFIRMATION ─────────────────
        confirmation_valid, confirmation_type = detect_confirmation(xau_candles, final_bias)

        # ── ENTRY TYPE ─────────────────
    
        if fvg:
            entry_type = "FVG"
            entry_instruction = (
                f"Wait for price to return to {fvg['type']} zone {fvg['zone']} "
                f"and confirm with engulfing or rejection candle"
            )
        else:
            entry_type = "CONFIRMATION"
            entry_instruction = "Wait for candle confirmation"

        # ── CONFIDENCE ─────────────────
        if fvg and ob_near_fvg:
            confidence = "HIGH"
        elif fvg:
            confidence = "MEDIUM"
        else:
            confidence = "LOW"

        # ── ADAPTIVE ENGINE ─────────────────
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
    
        # 🔥 Allow FVG override (controlled flexibility)
        fvg_aligned = (
            fvg and (
                ("BEARISH" in fvg["type"] and final_bias == "SELL") or
                ("BULLISH" in fvg["type"] and final_bias == "BUY")
            )
        )
        
        if not aligned and fvg_aligned:
            if vol_level != "LOW":   # avoid weak conditions
                aligned = True

        if aligned:
            if not confirmation_valid:
                trade_decision = "WAIT (NO CONFIRMATION)"
            else:
                if vol_level == "HIGH":
                    trade_decision = "TRADE"
                elif vol_level == "MEDIUM":
                    trade_decision = "TRADE (REDUCED RISK)"
                else:
                    trade_decision = "WAIT"
        else:
            trade_decision = "NO TRADE"

        # ── SAFE OVERRIDE ─────────────────
        if decision == DECISION_UNFAVORABLE and trade_decision == "TRADE":
            trade_decision = "WAIT"

        # ── LOG ─────────────────
        try:
            log_entry = DecisionLog(
                decision=decision,
                bias=final_bias,
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
            "entry_type": entry_type,
            "entry_instruction": entry_instruction,
            "confluence": {
                "fvg": fvg is not None,
                "ob_nearby": ob_near_fvg
            },
            "confidence": confidence,
            "confirmation": {
                "valid": confirmation_valid,
                "type": confirmation_type
            },
            "reasons": reasons,
            "log_id": log_id,
            "timestamp": timestamp,
        }

    except Exception as e:
        return {
            "decision": "ERROR SAFE MODE",
            "trade_decision": "NO TRADE",
            "bias": "NEUTRAL",
            "entry_zone": "UNKNOWN",
            "entry_type": "UNKNOWN",
            "entry_instruction": "SYSTEM ERROR",
            "confluence": {
                "fvg": False,
                "ob_nearby": False
            },
            "confidence": "LOW",
            "reasons": [str(e)],
            "log_id": None,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
