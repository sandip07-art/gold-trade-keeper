import pytest
from app.services.state_stability import require_persistence


class TestRequirePersistence:
    def test_confirms_with_enough_history(self):
        val, ok = require_persistence("EXPANSION", ["EXPANSION"], required_count=2)
        assert ok is True
        assert val == "EXPANSION"

    def test_rejects_with_no_history(self):
        val, ok = require_persistence("EXPANSION", [], required_count=2)
        assert ok is False

    def test_rejects_mismatched_history(self):
        val, ok = require_persistence("EXPANSION", ["LOW VOL"], required_count=2)
        assert ok is False

    def test_three_candle_requirement_passes(self):
        val, ok = require_persistence("EXPANSION", ["EXPANSION", "EXPANSION"], required_count=3)
        assert ok is True

    def test_three_candle_requirement_fails_partial(self):
        val, ok = require_persistence("EXPANSION", ["LOW VOL", "EXPANSION"], required_count=3)
        assert ok is False

    def test_required_count_1_always_confirms(self):
        val, ok = require_persistence("X", [], required_count=1)
        assert ok is True

    def test_neutral_bias_confirms_instantly(self):
        """NEUTRAL should confirm even with no history (required_count=1 edge case test)."""
        val, ok = require_persistence("NEUTRAL", [], required_count=1)
        assert ok is True

    def test_uses_only_tail_of_history(self):
        """Long history — only the tail matching required_count-1 matters."""
        history = ["LOW VOL"] * 10 + ["EXPANSION"]
        val, ok = require_persistence("EXPANSION", history, required_count=2)
        assert ok is True

    def test_partial_tail_mismatch(self):
        history = ["EXPANSION"] * 5 + ["LOW VOL"]
        val, ok = require_persistence("EXPANSION", history, required_count=2)
        assert ok is False   # last prior was LOW VOL

    def test_works_with_string_bias_values(self):
        val, ok = require_persistence(
            "USD STRONG → GOLD SELL",
            ["USD STRONG → GOLD SELL"],
            required_count=2,
        )
        assert ok is True
        assert val == "USD STRONG → GOLD SELL"
