import pytest
from datetime import date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import TradeRecord
from app.services.historical import get_historical_stats, _sample_confidence


CTX = dict(dxy_state="USD STRONG → GOLD SELL", vol_state="EXPANSION", session="LONDON")


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    S = sessionmaker(bind=engine)
    s = S()
    yield s
    s.close()


def add_trades(db, n: int, result="WIN", rr=2.0, pnl=1.0):
    for _ in range(n):
        db.add(TradeRecord(
            date=date.today().isoformat(),
            result=result, rr=rr, pnl_pct=pnl,
            **CTX,
        ))
    db.commit()


class TestSampleConfidence:
    def test_low_below_50(self):       assert _sample_confidence(20)  == "LOW"
    def test_low_at_49(self):          assert _sample_confidence(49)  == "LOW"
    def test_medium_at_50(self):       assert _sample_confidence(50)  == "MEDIUM"
    def test_medium_at_100(self):      assert _sample_confidence(100) == "MEDIUM"
    def test_high_above_100(self):     assert _sample_confidence(101) == "HIGH"
    def test_high_at_large(self):      assert _sample_confidence(999) == "HIGH"


class TestHistoricalStats:
    def test_returns_none_below_min_sample(self, db):
        add_trades(db, 10)
        result = get_historical_stats(db, **CTX)
        assert result is None

    def test_low_confidence_at_20(self, db):
        add_trades(db, 20)
        result = get_historical_stats(db, **CTX)
        assert result is not None
        assert result["data_confidence"] == "LOW"

    def test_medium_confidence_at_50(self, db):
        add_trades(db, 50)
        result = get_historical_stats(db, **CTX)
        assert result["data_confidence"] == "MEDIUM"

    def test_high_confidence_at_101(self, db):
        add_trades(db, 101)
        result = get_historical_stats(db, **CTX)
        assert result["data_confidence"] == "HIGH"

    def test_confidence_note_present(self, db):
        add_trades(db, 25)
        result = get_historical_stats(db, **CTX)
        assert "confidence_note" in result
        assert isinstance(result["confidence_note"], str)
        assert len(result["confidence_note"]) > 10

    def test_win_rate_calculation(self, db):
        add_trades(db, 15, result="WIN")
        add_trades(db, 5,  result="LOSS", rr=0.5, pnl=-0.8)
        result = get_historical_stats(db, **CTX)
        assert result["win_rate"] == pytest.approx(75.0)

    def test_avg_rr_calculation(self, db):
        add_trades(db, 20, result="WIN", rr=2.5)
        result = get_historical_stats(db, **CTX)
        assert result["avg_rr"] == pytest.approx(2.5)

    def test_context_embedded(self, db):
        add_trades(db, 20)
        result = get_historical_stats(db, **CTX)
        assert result["context"]["dxy_state"]  == CTX["dxy_state"]
        assert result["context"]["vol_state"]  == CTX["vol_state"]
        assert result["context"]["session"]    == CTX["session"]
