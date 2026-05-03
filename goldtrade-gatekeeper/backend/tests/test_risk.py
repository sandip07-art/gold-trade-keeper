import pytest
from datetime import datetime, date
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import DecisionLog, TradeRecord
from app.services.risk_enforcer import check_risk_limits


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def add_allowed_decision(db, n: int = 1):
    for _ in range(n):
        db.add(DecisionLog(
            decision="TRADE ALLOWED",
            bias="NEUTRAL",
            reasons=[],
            metrics={},
            advisory={},
            strict_mode=False,
        ))
    db.commit()


def add_loss(db, pnl_pct: float):
    db.add(TradeRecord(
        date=date.today().isoformat(),
        result="LOSS",
        rr=0.5,
        dxy_state="NEUTRAL",
        volatility_state="EXPANSION",
        session="LONDON",
        pnl_pct=pnl_pct,
    ))
    db.commit()


class TestRiskEnforcer:
    def test_passes_with_no_history(self, db):
        ok, blocks, info = check_risk_limits(db)
        assert ok is True
        assert blocks == []
        assert info["trades_today"] == 0

    def test_blocks_at_max_trades(self, db):
        add_allowed_decision(db, n=3)
        ok, blocks, info = check_risk_limits(db, max_trades=3)
        assert ok is False
        assert any("MAX TRADES" in b for b in blocks)
        assert info["trades_today"] == 3

    def test_allows_below_max_trades(self, db):
        add_allowed_decision(db, n=2)
        ok, blocks, _ = check_risk_limits(db, max_trades=3)
        assert ok is True

    def test_blocks_on_daily_loss(self, db):
        add_loss(db, pnl_pct=-1.5)
        add_loss(db, pnl_pct=-0.6)
        ok, blocks, info = check_risk_limits(db, max_daily_loss_pct=2.0)
        assert ok is False
        assert any("MAX DAILY LOSS" in b for b in blocks)
        assert info["daily_loss_pct"] == pytest.approx(2.1)

    def test_allows_under_daily_loss_limit(self, db):
        add_loss(db, pnl_pct=-0.8)
        ok, blocks, _ = check_risk_limits(db, max_daily_loss_pct=2.0)
        assert ok is True

    def test_both_limits_exceeded(self, db):
        add_allowed_decision(db, n=3)
        add_loss(db, pnl_pct=-2.5)
        ok, blocks, _ = check_risk_limits(db, max_trades=3, max_daily_loss_pct=2.0)
        assert ok is False
        assert len(blocks) == 2
