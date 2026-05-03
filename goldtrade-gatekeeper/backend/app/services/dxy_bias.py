"""
DXY Bias Engine
───────────────
Uses 1-hour DXY candles to determine directional bias.

Rules (all three conditions must hold for a breakout):
  1. Price: current close breaks prev high (bullish) or prev low (bearish)
  2. Body:  current candle body is in the direction of the break
  3. Momentum: breakout candle range > average range of lookback candles
               (ensures the break has actual expansion, not a drift)

Requires ≥ 3 candles (2 lookback + 1 current).
Returns "NEUTRAL" on insufficient data or failed momentum check.
"""
from typing import Any


BIAS_NEUTRAL = "NEUTRAL"
BIAS_STRONG  = "USD STRONG → GOLD SELL"
BIAS_WEAK    = "USD WEAK → GOLD BUY"

# How many prior candles to average for the momentum range check
MOMENTUM_LOOKBACK = 5


def _avg_range(candles: list[dict[str, Any]]) -> float:
    """Mean high-low range of the given candles."""
    ranges = [float(c["high"]) - float(c["low"]) for c in candles]
    return sum(ranges) / len(ranges) if ranges else 0.0


def compute_dxy_bias(
    dxy_candles: list[dict[str, Any]],
    momentum_lookback: int = MOMENTUM_LOOKBACK,
) -> tuple[str, dict[str, Any]]:
    """
    Returns (bias_string, detail_dict).
    detail_dict keys: prev_high, prev_low, curr_range, avg_range, momentum_ok
    """
    empty_detail: dict[str, Any] = {
        "prev_high": None, "prev_low": None,
        "curr_range": None, "avg_range": None, "momentum_ok": False,
    }

    if not dxy_candles or len(dxy_candles) < 3:
        return BIAS_NEUTRAL, empty_detail

    prev = dxy_candles[-2]
    curr = dxy_candles[-1]

    prev_high  = float(prev["high"])
    prev_low   = float(prev["low"])
    curr_close = float(curr["close"])
    curr_open  = float(curr["open"])
    curr_high  = float(curr["high"])
    curr_low   = float(curr["low"])
    curr_range = curr_high - curr_low

    # Use up to MOMENTUM_LOOKBACK candles before the breakout candle for avg range
    lookback_candles = dxy_candles[-(momentum_lookback + 2):-1]
    avg_range = _avg_range(lookback_candles) if lookback_candles else 0.0
    momentum_ok = avg_range > 0 and curr_range > avg_range

    detail: dict[str, Any] = {
        "prev_high":   round(prev_high, 5),
        "prev_low":    round(prev_low, 5),
        "curr_range":  round(curr_range, 5),
        "avg_range":   round(avg_range, 5),
        "momentum_ok": momentum_ok,
    }

    if not momentum_ok:
        return BIAS_NEUTRAL, detail

    if curr_close > prev_high and curr_close > curr_open:
        return BIAS_STRONG, detail

    if curr_close < prev_low and curr_close < curr_open:
        return BIAS_WEAK, detail

    return BIAS_NEUTRAL, detail


def bias_to_label(bias: str) -> str:
    """Human-readable one-liner for UI."""
    if bias == BIAS_STRONG:
        return "DXY Breakout High ↑ — Gold headwind"
    if bias == BIAS_WEAK:
        return "DXY Breakout Low ↓ — Gold tailwind"
    return "DXY range-bound — no directional conviction"
