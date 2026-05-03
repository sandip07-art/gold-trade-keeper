import pytest
from app.services.volatility import compute_atr, check_volatility_expansion


def candle(h, l, c):
    return {"open": (h + l) / 2, "high": h, "low": l, "close": c, "time": "x"}


class TestComputeAtr:
    def test_requires_enough_candles(self):
        assert compute_atr([candle(10, 9, 9.5)], period=14) == 0.0

    def test_returns_positive(self):
        candles = [candle(100 + i * 0.5, 99 + i * 0.5, 99.5 + i * 0.5) for i in range(20)]
        atr = compute_atr(candles, period=14)
        assert atr > 0

    def test_higher_vol_gives_higher_atr(self):
        low_vol  = [candle(100 + i * 0.2, 100 + i * 0.2 - 0.1, 100 + i * 0.2 - 0.05) for i in range(20)]
        high_vol = [candle(100 + i * 0.2, 100 + i * 0.2 - 2.0, 100 + i * 0.2 - 1.0)  for i in range(20)]
        assert compute_atr(high_vol) > compute_atr(low_vol)


class TestVolatilityExpansion:
    def test_expansion_when_above_threshold(self):
        state, ok = check_volatility_expansion(atr_current=3.5, atr_avg=2.0, multiplier=1.5)
        assert ok is True
        assert state == "EXPANSION"

    def test_blocked_when_below_threshold(self):
        state, ok = check_volatility_expansion(atr_current=2.5, atr_avg=2.0, multiplier=1.5)
        assert ok is False
        assert state == "LOW VOL"

    def test_exact_boundary_is_not_expansion(self):
        # exactly 1.5× → NOT expansion (must be GREATER than)
        state, ok = check_volatility_expansion(atr_current=3.0, atr_avg=2.0, multiplier=1.5)
        assert ok is False

    def test_zero_avg_returns_low_vol(self):
        state, ok = check_volatility_expansion(atr_current=1.5, atr_avg=0.0)
        assert ok is False
        assert state == "LOW VOL"

    def test_strict_mode_higher_multiplier(self):
        # At 1.5× the current just passes normal, but fails strict (1.5×1.2=1.8×)
        state_normal, ok_normal = check_volatility_expansion(3.1, 2.0, multiplier=1.5)
        state_strict, ok_strict = check_volatility_expansion(3.1, 2.0, multiplier=1.8)
        assert ok_normal is True
        assert ok_strict is False
