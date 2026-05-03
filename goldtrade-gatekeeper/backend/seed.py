#!/usr/bin/env python3
"""
seed.py — Populate GoldTrade Gatekeeper with demo data.

Usage:
  cd backend
  python seed.py [--session london|newyork|outside] [--vol expansion|low]
"""
import sys, os, argparse, random
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal, engine
from app.models import Base, MarketState, TradeRecord, DecisionLog


def make_candles(base: float, count: int, vol: float) -> list[dict]:
    candles, price = [], base
    for i in range(count):
        o = price
        h = o + abs(random.gauss(0, vol))
        l = o - abs(random.gauss(0, vol))
        c = o + random.gauss(0, vol * 0.6)
        h, l = max(h, o, c), min(l, o, c)
        candles.append({
            "time":   (datetime.utcnow() - timedelta(minutes=(count - i) * 5)).isoformat(),
            "open":   round(o, 4), "high": round(h, 4),
            "low":    round(l, 4), "close": round(c, 4),
            "volume": random.randint(800, 6000),
        })
        price = c
    return candles


def seed(session_preset: str = "london", vol_preset: str = "expansion"):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()

    # ── MarketState ───────────────────────────────────────────────────────────
    hour_map = {"london": 8, "newyork": 13, "outside": 22}
    utc_hour = hour_map.get(session_preset, 8)
    now_utc = datetime.now(timezone.utc).replace(hour=utc_hour, minute=15, second=0, microsecond=0)

    xauusd_candles = make_candles(2348.0, 40, 1.9)
    dxy_candles    = make_candles(104.4, 8, 0.14)

    # Force a DXY breakout for an interesting default state
    if len(dxy_candles) >= 2:
        ph = dxy_candles[-2]["high"]
        dxy_candles[-1].update({"open": ph - 0.04, "close": ph + 0.13, "high": ph + 0.19})

    # ATR values
    atr_avg = 2.1
    if vol_preset == "expansion":
        atr_current = round(atr_avg * 1.8, 2)   # clearly above threshold
    else:
        atr_current = round(atr_avg * 1.1, 2)   # below threshold

    news_events = [
        {
            "time":   (now_utc + timedelta(hours=3, minutes=30)).isoformat(),
            "name":   "FOMC Minutes",
            "impact": "HIGH",
        },
        {
            "time":   (now_utc - timedelta(hours=5)).isoformat(),
            "name":   "CPI m/m",
            "impact": "HIGH",
        },
        {
            "time":   (now_utc + timedelta(hours=1, minutes=15)).isoformat(),
            "name":   "Initial Jobless Claims",
            "impact": "MEDIUM",
        },
    ]

    state = db.query(MarketState).filter(MarketState.id == 1).first()
    if not state:
        state = MarketState(id=1)
        db.add(state)

    state.xauusd_price   = xauusd_candles[-1]["close"]
    state.xauusd_candles = xauusd_candles
    state.dxy_price      = dxy_candles[-1]["close"]
    state.dxy_candles    = dxy_candles
    state.atr_current    = atr_current
    state.atr_avg        = atr_avg
    state.news_events    = news_events
    state.server_time    = now_utc.replace(tzinfo=None)
    state.updated_at     = datetime.utcnow()

    # ── TradeRecords (historical context data) ────────────────────────────────
    sessions    = ["LONDON", "NEW_YORK"]
    dxy_states  = ["USD STRONG → GOLD SELL", "USD WEAK → GOLD BUY", "NEUTRAL"]
    vol_states  = ["EXPANSION", "LOW VOL"]
    # Weighted toward WIN for expansion sessions to show historical context value
    result_pool = ["WIN"] * 6 + ["LOSS"] * 3 + ["BE"] * 1

    for _ in range(80):
        sess = random.choice(sessions)
        dxy  = random.choice(dxy_states)
        vol  = random.choice(vol_states)
        # Slightly better outcomes in expansion + strong bias
        if vol == "EXPANSION" and dxy != "NEUTRAL":
            pool = ["WIN"] * 7 + ["LOSS"] * 2 + ["BE"] * 1
        else:
            pool = result_pool
        res  = random.choice(pool)
        pnl  = round(random.uniform(0.8, 2.5), 2) if res == "WIN" else round(random.uniform(-1.2, -0.3), 2)
        rr   = round(random.uniform(1.2, 3.5), 2)  if res == "WIN" else round(random.uniform(0.2, 0.9), 2)

        db.add(TradeRecord(
            date              = (datetime.utcnow() - timedelta(days=random.randint(1, 90))).date().isoformat(),
            result            = res,
            rr                = rr,
            dxy_state         = dxy,
            volatility_state  = vol,
            session           = sess,
            pnl_pct           = pnl if res == "WIN" else pnl,
        ))

    db.commit()
    db.close()

    print("✅  Seed complete.")
    print(f"   Session preset  : {session_preset.upper()} ({utc_hour:02d}:15 UTC)")
    print(f"   Volatility      : {vol_preset.upper()} — ATR {atr_current} vs avg {atr_avg}")
    print(f"   XAUUSD          : {state.xauusd_price:.2f}")
    print(f"   DXY             : {state.dxy_price:.4f}")
    print(f"   News events     : {len(news_events)}")
    print(f"   Trade records   : 80 synthetic historical trades")
    print()
    print("   Next: GET /decision")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed GoldTrade Gatekeeper with demo data")
    parser.add_argument("--session", choices=["london", "newyork", "outside"], default="london")
    parser.add_argument("--vol",     choices=["expansion", "low"],             default="expansion")
    args = parser.parse_args()
    seed(session_preset=args.session, vol_preset=args.vol)
