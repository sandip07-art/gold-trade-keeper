"""
Market Data Adapters
────────────────────
Abstract interface + simulated adapter.  Swap SimulatedAdapter for a real
provider (e.g. MetaApi, Alpha Vantage, Twelve Data) without touching any
service or router code.

Real adapter checklist:
  1. Subclass MarketDataAdapter
  2. Implement all abstract methods
  3. Set MARKET_ADAPTER=real in env and wire in main.py
"""
from __future__ import annotations

import random
from abc import ABC, abstractmethod
from datetime import datetime, timezone, timedelta
from typing import Any


class MarketDataAdapter(ABC):
    """Contract that all data providers must implement."""

    @abstractmethod
    def get_xauusd_candles(self, timeframe: str = "5m", count: int = 50) -> list[dict[str, Any]]:
        ...

    @abstractmethod
    def get_dxy_candles(self, timeframe: str = "1h", count: int = 10) -> list[dict[str, Any]]:
        ...

    @abstractmethod
    def get_atr(self, period: int = 14, avg_periods: int = 20) -> tuple[float, float]:
        """Return (atr_current, atr_avg)."""
        ...

    @abstractmethod
    def get_news_events(self, hours_ahead: int = 24) -> list[dict[str, Any]]:
        ...

    @abstractmethod
    def get_server_time(self) -> datetime:
        ...


# ──────────────────────────────────────────────────────────────────────────────
# Simulated adapter — used when no live feed is configured
# ──────────────────────────────────────────────────────────────────────────────

class SimulatedAdapter(MarketDataAdapter):
    """Generates plausible synthetic data for development/testing."""

    def _make_candles(
        self, base: float, count: int, volatility: float
    ) -> list[dict[str, Any]]:
        candles: list[dict[str, Any]] = []
        price = base
        for i in range(count):
            o = price
            h = o + abs(random.gauss(0, volatility))
            l = o - abs(random.gauss(0, volatility))
            c = o + random.gauss(0, volatility * 0.6)
            h = max(h, o, c)
            l = min(l, o, c)
            candles.append(
                {
                    "time": (datetime.utcnow() - timedelta(minutes=(count - i) * 5)).isoformat(),
                    "open":   round(o, 4),
                    "high":   round(h, 4),
                    "low":    round(l, 4),
                    "close":  round(c, 4),
                    "volume": random.randint(500, 8000),
                }
            )
            price = c
        return candles

    def get_xauusd_candles(self, timeframe: str = "5m", count: int = 50) -> list[dict[str, Any]]:
        return self._make_candles(base=2345.0, count=count, volatility=1.8)

    def get_dxy_candles(self, timeframe: str = "1h", count: int = 10) -> list[dict[str, Any]]:
        candles = self._make_candles(base=104.4, count=count, volatility=0.15)
        # Simulate a DXY breakout on the last candle for demo interest
        if len(candles) >= 2:
            prev_high = candles[-2]["high"]
            candles[-1]["close"] = round(prev_high + 0.12, 4)
            candles[-1]["open"]  = round(prev_high - 0.05, 4)
            candles[-1]["high"]  = round(prev_high + 0.18, 4)
        return candles

    def get_atr(self, period: int = 14, avg_periods: int = 20) -> tuple[float, float]:
        atr_avg = round(random.uniform(1.6, 2.4), 2)
        atr_cur = round(atr_avg * random.uniform(1.4, 2.0), 2)  # usually expanding
        return atr_cur, atr_avg

    def get_news_events(self, hours_ahead: int = 24) -> list[dict[str, Any]]:
        now = datetime.now(timezone.utc)
        return [
            {
                "time":   (now + timedelta(hours=3)).isoformat(),
                "name":   "FOMC Minutes",
                "impact": "HIGH",
            },
            {
                "time":   (now - timedelta(hours=4)).isoformat(),
                "name":   "CPI m/m",
                "impact": "HIGH",
            },
            {
                "time":   (now + timedelta(hours=6)).isoformat(),
                "name":   "PPI m/m",
                "impact": "MEDIUM",
            },
        ]

    def get_server_time(self) -> datetime:
        return datetime.now(timezone.utc)


# ──────────────────────────────────────────────────────────────────────────────
# Factory
# ──────────────────────────────────────────────────────────────────────────────

def get_adapter(provider: str = "simulated") -> MarketDataAdapter:
    """
    Future providers:
      "metaapi"      → MetaApiAdapter(token=..., account_id=...)
      "alphavatange" → AlphaVantageAdapter(api_key=...)
      "twelvedata"   → TwelveDataAdapter(api_key=...)
    """
    if provider == "simulated":
        return SimulatedAdapter()
    raise ValueError(f"Unknown market data provider: {provider!r}")
