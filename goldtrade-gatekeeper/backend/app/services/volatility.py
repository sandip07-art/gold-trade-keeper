"""
Volatility Expansion
────────────────────
ATR(14) on 5-minute candles.

  • If atr_current > multiplier × atr_avg_20  → EXPANSION  (trade allowed)
  • Otherwise                                  → LOW VOL    (blocked)

Candle dict schema: {open, high, low, close, time, volume?}
"""
from typing import Any


def compute_atr(candles: list[dict[str, Any]], period: int = 14) -> float:
    """Wilder's ATR(period)."""
    if len(candles) < period + 1:
        return 0.0

    trs: list[float] = []
    for i in range(1, len(candles)):
        h = float(candles[i]["high"])
        l = float(candles[i]["low"])
        pc = float(candles[i - 1]["close"])
        tr = max(h - l, abs(h - pc), abs(l - pc))
        trs.append(tr)

    # Seed: simple average of first `period` TRs
    atr = sum(trs[:period]) / period
    # Smooth: Wilder's method
    for tr in trs[period:]:
        atr = (atr * (period - 1) + tr) / period

    return round(atr, 5)


def compute_atr_average(candles: list[dict[str, Any]], atr_period: int = 14, avg_periods: int = 20) -> float:
    """Rolling mean of the last avg_periods ATR values."""
    needed = atr_period + avg_periods + 1
    if len(candles) < needed:
        return 0.0

    atrs: list[float] = []
    for i in range(avg_periods):
        window = candles[: len(candles) - i]
        atrs.append(compute_atr(window, atr_period))

    return round(sum(atrs) / len(atrs), 5)


def check_volatility_expansion(
    atr_current: float,
    atr_avg: float,
    multiplier: float = 1.5,
) -> tuple[str, bool]:
    """Return (state_label, is_expansion)."""
    if atr_avg <= 0:
        return "LOW VOL", False
    if atr_current > multiplier * atr_avg:
        return "EXPANSION", True
    return "LOW VOL", False
