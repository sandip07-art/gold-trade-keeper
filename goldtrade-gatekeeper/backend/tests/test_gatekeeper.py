"""
Integration test: full gate evaluation on an in-memory DB.
"""
import pytest
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import MarketState
from app.services.gatekeeper import (
    evaluate,
    DECISION_FAVORABLE,
    DECISION_UNFAVORABLE,
)


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    S = sessionmaker(bind=engine)
    s = S()
    yield s
    s.close()


def make_dxy_candles(breakout=True):
    # 8 candles so momentum lookback has enough data
    base = [
        {"open": 104.0, "high": 104.3, "low": 103.9, "close": 104.1, "time": f"t{i}"}
        for i in range(6)
    ]
    if breakout:
        base += [
            {"open": 104.1, "high": 104.5, "low": 103.8, "close": 104.3, "time": "t6"},  # prev
            {"open": 104.3, "high": 105.1, "low": 104.2, "close": 104.9, "time": "t7"},  # curr: big bullish breakout
        ]
    else:
        base += [
            {"open": 104.1, "high": 104.5, "low": 103.8, "close": 104.3, "time": "t6"},
            {"open": 104.3, "high": 104.4, "low": 104.0, "close": 104.2, "time": "t7"},  # range < avg → no momentum
        ]
    return base


def london_state(db, vol_ok=True, news=None):
    state = MarketState(
        id=1,
        xauusd_price=2348.0,
        dxy_price=104.4,
        dxy_candles=make_dxy_candles(breakout=True),
        atr_current=3.5 if vol_ok else 1.8,
        atr_avg=2.0,
        news_events=news or [],
        server_time=datetime(2024, 6, 10, 8, 30, tzinfo=timezone.utc).replace(tzinfo=None),
    )
    db.add(state)
    db.commit()
    return state


class TestGatekeeperIntegration:
    def test_first_eval_vol_unconfirmed_blocks(self, db):
        """First evaluation has no history → volatility unconfirmed → UNFAVORABLE."""
        state = london_state(db, vol_ok=True)
        result = evaluate(db, state)
        # First tick: no prior vol history → stability check fails
        assert result["decision"] == DECISION_UNFAVORABLE
        assert any("UNCONFIRMED" in r or "VOLATILITY" in r for r in result["reasons"])

    def test_two_evals_confirm_state(self, db):
        """Two consecutive evaluations with same vol state → confirmed → FAVORABLE."""
        state = london_state(db, vol_ok=True)
        evaluate(db, state)          # tick 1: seeds history
        state2 = db.query(MarketState).filter_by(id=1).first()
        result2 = evaluate(db, state2)  # tick 2: vol now confirmed
        assert result2["decision"] == DECISION_FAVORABLE

    def test_low_vol_gives_unfavorable(self, db):
        state = london_state(db, vol_ok=False)
        result = evaluate(db, state)
        assert result["decision"] == DECISION_UNFAVORABLE
        assert any("VOLATILITY" in r for r in result["reasons"])

    def test_outside_session_blocked(self, db):
        state = MarketState(
            id=1,
            xauusd_price=2348.0, dxy_price=104.4,
            dxy_candles=make_dxy_candles(True),
            atr_current=3.5, atr_avg=2.0,
            news_events=[],
            server_time=datetime(2024, 6, 10, 22, 0).replace(tzinfo=None),
        )
        db.add(state); db.commit()
        result = evaluate(db, state)
        assert result["decision"] == DECISION_UNFAVORABLE
        assert any("SESSION" in r for r in result["reasons"])

    def test_news_window_blocked(self, db):
        from datetime import timedelta
        now = datetime(2024, 6, 10, 8, 30, tzinfo=timezone.utc)
        news = [{"time": (now + timedelta(minutes=10)).isoformat(), "name": "NFP", "impact": "HIGH"}]
        state = london_state(db, vol_ok=True, news=news)
        result = evaluate(db, state)
        assert result["decision"] == DECISION_UNFAVORABLE
        assert any("NEWS" in r for r in result["reasons"])

    def test_momentum_filter_suppresses_weak_dxy(self, db):
        """A DXY candle that breaks prev high but has tiny range stays NEUTRAL."""
        state = MarketState(
            id=1,
            xauusd_price=2348.0, dxy_price=104.4,
            dxy_candles=make_dxy_candles(breakout=False),
            atr_current=3.5, atr_avg=2.0,
            news_events=[],
            server_time=datetime(2024, 6, 10, 8, 30).replace(tzinfo=None),
        )
        db.add(state); db.commit()
        result = evaluate(db, state)
        assert result["metrics"]["dxy_state"] == "NEUTRAL"

    def test_metrics_contain_stability_fields(self, db):
        state = london_state(db, vol_ok=True)
        result = evaluate(db, state)
        m = result["metrics"]
        assert "vol_confirmed"  in m
        assert "dxy_confirmed"  in m
        assert "dxy_momentum"   in m
        assert "stability_candles" in m

    def test_advisory_present(self, db):
        state = london_state(db, vol_ok=True)
        result = evaluate(db, state)
        adv = result["advisory"]
        assert "summary" in adv and "confidence" in adv and "playbook" in adv

    def test_log_entry_persisted(self, db):
        from app.models import DecisionLog
        state = london_state(db, vol_ok=True)
        evaluate(db, state)
        assert db.query(DecisionLog).count() >= 1

    def test_strict_mode_harder_threshold(self, db):
        """ATR=3.1 vs avg=2.0: 3.1 > 1.5×2=3.0 → passes normal.
           3.1 < 1.8×2=3.6 → fails strict. Both need 2 ticks to confirm, so
           seed history first then test on second tick."""
        state = MarketState(
            id=1,
            xauusd_price=2348.0, dxy_price=104.4,
            dxy_candles=make_dxy_candles(True),
            atr_current=3.1, atr_avg=2.0,
            news_events=[],
            server_time=datetime(2024, 6, 10, 8, 30).replace(tzinfo=None),
        )
        db.add(state); db.commit()
        evaluate(db, state)  # seed tick 1

        state2 = db.query(MarketState).filter_by(id=1).first()
        res_normal = evaluate(db, state2, strict_mode=False)

        state3 = db.query(MarketState).filter_by(id=1).first()
        res_strict = evaluate(db, state3, strict_mode=True)

        assert res_normal["decision"] == DECISION_FAVORABLE
        assert res_strict["decision"] == DECISION_UNFAVORABLE
