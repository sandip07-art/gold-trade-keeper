import pytest
from app.services.dxy_bias import compute_dxy_bias, BIAS_STRONG, BIAS_WEAK, BIAS_NEUTRAL


def candle(o, h, l, c, tag="t"):
    return {"open": o, "high": h, "low": l, "close": c, "time": tag}


def big_candle(o, h, l, c):
    """Candle with a range clearly larger than the filler candles (range=0.5→2.0)."""
    return candle(o, h, l, c)


# Filler candles with small range (~0.1) so big breakout stands out
FILLER = [candle(104.0, 104.1, 103.9, 104.0, f"f{i}") for i in range(6)]


def make_candles(prev, curr):
    """Build a list with filler + prev + curr so momentum lookback sees small avg range."""
    return FILLER + [prev, curr]


class TestDxyBias:
    def test_usd_strong_with_momentum(self):
        candles = make_candles(
            candle(104.0, 104.5, 103.8, 104.3),         # prev high=104.5
            big_candle(104.3, 106.0, 104.2, 105.8),     # curr: big bullish, close>104.5
        )
        bias, detail = compute_dxy_bias(candles)
        assert bias == BIAS_STRONG
        assert detail["momentum_ok"] is True

    def test_usd_strong_fails_without_momentum(self):
        """Breakout close but tiny range — no momentum → NEUTRAL."""
        candles = make_candles(
            candle(104.0, 104.5, 103.8, 104.3),
            candle(104.3, 104.55, 104.35, 104.52),      # close > prev high, but tiny range
        )
        bias, detail = compute_dxy_bias(candles)
        assert bias == BIAS_NEUTRAL
        assert detail["momentum_ok"] is False

    def test_usd_strong_requires_bullish_body(self):
        """Range is big but body is bearish → NEUTRAL."""
        candles = make_candles(
            candle(104.0, 104.5, 103.8, 104.3),
            big_candle(106.0, 106.5, 103.5, 104.6),    # close > prev_high but open > close
        )
        bias, _ = compute_dxy_bias(candles)
        assert bias == BIAS_NEUTRAL

    def test_usd_weak_with_momentum(self):
        candles = make_candles(
            candle(104.0, 104.5, 103.8, 104.2),         # prev low=103.8
            big_candle(104.2, 104.3, 102.5, 102.9),     # curr: big bearish, close<103.8
        )
        bias, detail = compute_dxy_bias(candles)
        assert bias == BIAS_WEAK
        assert detail["momentum_ok"] is True

    def test_usd_weak_fails_without_momentum(self):
        candles = make_candles(
            candle(104.0, 104.5, 103.8, 104.2),
            candle(104.2, 104.21, 103.75, 103.77),     # close < prev low, tiny range
        )
        bias, detail = compute_dxy_bias(candles)
        assert bias == BIAS_NEUTRAL
        assert detail["momentum_ok"] is False

    def test_neutral_range_bound(self):
        candles = make_candles(
            candle(104.0, 104.5, 103.8, 104.2),
            big_candle(104.2, 104.4, 104.0, 104.3),    # within prev range
        )
        bias, _ = compute_dxy_bias(candles)
        assert bias == BIAS_NEUTRAL

    def test_empty_list(self):
        bias, detail = compute_dxy_bias([])
        assert bias == BIAS_NEUTRAL
        assert detail["momentum_ok"] is False

    def test_insufficient_candles(self):
        bias, _ = compute_dxy_bias([candle(104.0, 104.5, 103.8, 104.2)])
        assert bias == BIAS_NEUTRAL

    def test_detail_fields_present(self):
        candles = make_candles(
            candle(104.0, 104.5, 103.8, 104.3),
            big_candle(104.3, 106.0, 104.2, 105.8),
        )
        _, detail = compute_dxy_bias(candles)
        for key in ("prev_high", "prev_low", "curr_range", "avg_range", "momentum_ok"):
            assert key in detail
