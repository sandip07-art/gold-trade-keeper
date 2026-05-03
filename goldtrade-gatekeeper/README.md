# ⚡ GoldTrade Gatekeeper — XAUUSD Discipline Enforcer

> **Rule-based trade gate for XAUUSD. No AI prediction. Pure discipline enforcement.**

---

## What It Does

GoldTrade Gatekeeper evaluates real-time market conditions against a strict ruleset and returns one of three verdicts:

| Verdict | Meaning |
|---------|---------|
| `TRADE ALLOWED` | All gates passed — conditions are valid |
| `BLOCKED` | One or more rules violated — exact reasons given |
| `NO TRADE` | Conditions partially met — caution advised |

It also provides a non-controlling **Advisory Engine** with market interpretation and a **Historical Context** module showing win-rate/R:R for the current context.

---

## Architecture

```
goldtrade-gatekeeper/
├── backend/                  # Python + FastAPI
│   ├── app/
│   │   ├── main.py           # FastAPI app + CORS
│   │   ├── config.py         # Pydantic settings (env-driven)
│   │   ├── database.py       # SQLAlchemy engine + session
│   │   ├── models.py         # MarketState, DecisionLog, TradeRecord
│   │   ├── routers/
│   │   │   ├── ingest.py     # POST /ingest, POST /ingest/simulate
│   │   │   ├── decision.py   # GET /decision, GET /stats
│   │   │   └── logs.py       # GET /logs, GET /logs/export, POST /trades
│   │   ├── services/
│   │   │   ├── session_filter.py  # London + NY session gate
│   │   │   ├── news_blocker.py    # ±30-min HIGH-impact USD events
│   │   │   ├── dxy_bias.py        # DXY 1h breakout bias engine
│   │   │   ├── volatility.py      # ATR(14) expansion check
│   │   │   ├── risk_enforcer.py   # Max trades + max loss enforcer
│   │   │   ├── gatekeeper.py      # Orchestrator — final verdict
│   │   │   ├── advisory.py        # Non-controlling market interpretation
│   │   │   └── historical.py      # Win-rate + R:R by context
│   │   └── adapters/
│   │       └── market_data.py     # Abstract adapter + SimulatedAdapter
│   ├── tests/                # Pytest unit + integration tests
│   ├── seed.py               # Demo data seeder
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/                 # React + Vite
│   ├── src/
│   │   ├── App.jsx           # Full dashboard (single component)
│   │   ├── api/client.js     # Axios API client
│   │   └── index.css         # Dark theme design system
│   ├── Dockerfile
│   └── nginx.conf
└── docker-compose.yml
```

---

## Quick Start (Local — No Docker)

### 1. Backend

```bash
cd backend

# Create virtual environment
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

# Install deps
pip install -r requirements.txt

# Copy env config
cp .env.example .env

# Seed demo data (London session + ATR expansion)
python seed.py

# Seed for other scenarios:
python seed.py --session newyork --vol expansion
python seed.py --session outside --vol low

# Start API
uvicorn app.main:app --reload --port 8000
```

API docs: http://localhost:8000/docs

### 2. Frontend

```bash
cd frontend
cp .env.example .env         # sets VITE_API_URL=http://localhost:8000
npm install
npm run dev
```

Dashboard: http://localhost:5173

### 3. Run Tests

```bash
cd backend
pytest -v
```

---

## Quick Start (Docker)

```bash
# Build + start both services
docker-compose up --build

# Dashboard:   http://localhost:3000
# API docs:    http://localhost:8000/docs

# Seed demo data inside the container:
docker exec gtg-backend python seed.py
```

---

## API Reference

### Ingest Market Data

```bash
# POST /ingest — push real data (partial updates supported)
curl -X POST http://localhost:8000/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "xauusd_price": 2348.5,
    "atr_current": 3.8,
    "atr_avg": 2.1,
    "dxy_price": 104.45,
    "server_time": "2024-06-10T08:30:00Z",
    "news_events": [
      {"time": "2024-06-10T12:30:00Z", "name": "CPI", "impact": "HIGH"}
    ]
  }'

# POST /ingest/simulate — pull from SimulatedAdapter (dev)
curl -X POST http://localhost:8000/ingest/simulate
```

### Get Decision

```bash
# Normal mode
curl http://localhost:8000/decision

# Strict mode (ATR multiplier ×1.2 harder)
curl http://localhost:8000/decision?strict_mode=true
```

**Response:**
```json
{
  "decision": "TRADE ALLOWED",
  "bias": "USD STRONG → GOLD SELL",
  "reasons": [
    "Session: LONDON",
    "Volatility: EXPANSION",
    "DXY Bias: USD STRONG → GOLD SELL",
    "Risk: 0/3 trades today"
  ],
  "metrics": {
    "atr": 3.8,
    "atr_avg": 2.1,
    "atr_ratio": 1.81,
    "dxy_state": "USD STRONG → GOLD SELL",
    "session": "LONDON",
    "vol_state": "EXPANSION",
    "trades_today": 0,
    "daily_loss_pct": 0.0,
    "xauusd_price": 2348.5,
    "dxy_price": 104.45,
    "strict_mode": false
  },
  "advisory": {
    "summary": "DXY is showing strength with volatility expanding during the LONDON session...",
    "confidence": "HIGH",
    "playbook": [
      "Look for bearish price structure on Gold at resistance zones.",
      "Confirm with a bearish close on the 5m candle before considering an entry.",
      "Keep risk defined — expansion phases can reverse sharply."
    ]
  },
  "historical": {
    "win_rate": 64.3,
    "avg_rr": 2.14,
    "sample_size": 28,
    "context": {
      "dxy_state": "USD STRONG → GOLD SELL",
      "vol_state": "EXPANSION",
      "session": "LONDON"
    }
  }
}
```

### Logs

```bash
# Last 50 decisions (JSON)
curl http://localhost:8000/logs

# Export all as CSV
curl http://localhost:8000/logs/export -o gate_decisions.csv

# Record a trade outcome (feeds historical stats)
curl -X POST http://localhost:8000/trades \
  -H "Content-Type: application/json" \
  -d '{
    "result": "WIN",
    "rr": 2.1,
    "dxy_state": "USD STRONG → GOLD SELL",
    "volatility_state": "EXPANSION",
    "session": "LONDON",
    "pnl_pct": 1.8
  }'
```

---

## The 5 Gates

| # | Gate | Block Reason | Override |
|---|------|-------------|---------|
| 1 | **Session Filter** | `OUTSIDE SESSION` | None |
| 2 | **News Blocker** | `NEWS WINDOW — <event>` | None |
| 3 | **Volatility** | `LOW VOLATILITY — ATR below expansion threshold` | None |
| 4 | **Risk: Trade Count** | `MAX TRADES REACHED (3/3 today)` | None |
| 5 | **Risk: Daily Loss** | `MAX DAILY LOSS REACHED (2.1% / 2% limit)` | None |

All 5 must pass for `TRADE ALLOWED`. DXY bias is **informational** — it does not gate the trade.

---

## Connecting Real Data

The adapter pattern makes this straightforward. Create a new adapter:

```python
# backend/app/adapters/market_data.py
class MetaApiAdapter(MarketDataAdapter):
    def __init__(self, token: str, account_id: str):
        self.token = token
        self.account_id = account_id

    def get_xauusd_candles(self, timeframe="5m", count=50):
        # Call MetaApi REST: GET /accounts/{id}/symbols/XAUUSD/candles
        resp = requests.get(
            f"https://metaapi.cloud/users/current/accounts/{self.account_id}"
            f"/history-market/symbols/XAUUSD/time-frames/{timeframe}/candles",
            headers={"auth-token": self.token},
            params={"limit": count},
        )
        return resp.json()["candles"]

    # ... implement other methods
```

Then in `main.py` wire it:
```python
from app.adapters.market_data import get_adapter
adapter = get_adapter("metaapi")   # or "alphavatange", "twelvedata"
```

### Provider Mapping

| Data | Providers |
|------|-----------|
| XAUUSD candles | MetaApi, Twelve Data, Alpha Vantage |
| DXY candles | Twelve Data (`DXY`), Alpha Vantage |
| ATR(14) | Compute from candles (built-in) |
| Economic calendar | Investing.com scraper, ForexFactory API, Myfxbook |
| Server time | `datetime.utcnow()` or broker server time |

---

## Deploying to Render / Railway

### Render (Backend)
1. New **Web Service** → connect repo
2. Build command: `pip install -r requirements.txt`
3. Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. Add env vars from `.env.example`
5. For persistent DB: add a **Postgres** addon and set `DATABASE_URL`

### Render (Frontend)
1. New **Static Site** → connect `/frontend`
2. Build: `npm install && npm run build`
3. Publish dir: `dist`
4. Set `VITE_API_URL=https://your-backend.onrender.com`

### Railway
```bash
# Both services auto-detected from docker-compose.yml
railway up
```

---

## Strict Mode

Toggled from the UI or via `?strict_mode=true`.

- ATR expansion multiplier increases from **1.5× → 1.8×** (1.5 × 1.2)
- Advisory confidence downgrades one level (HIGH → MEDIUM)
- All other gates unchanged

---

## Historical Context

Records are added via `POST /trades` after each real trade. Once a context (session + volatility + DXY state) accumulates **≥20 samples**, the dashboard shows:

- **Win Rate** (%)
- **Avg R:R**
- **Sample Size**

This is purely observational — it does not affect gate decisions.

---

## Configuration Reference

| Env Var | Default | Description |
|---------|---------|-------------|
| `DATABASE_URL` | `sqlite:///./goldtrade.db` | SQLite or Postgres URL |
| `MAX_TRADES_PER_DAY` | `3` | Max ALLOWED decisions per UTC day |
| `MAX_DAILY_LOSS_PCT` | `2.0` | Max cumulative loss % before block |
| `RISK_PER_TRADE_PCT` | `1.0` | Risk per trade (informational) |
| `ATR_EXPANSION_MULTIPLIER` | `1.5` | ATR current must exceed avg × this |
| `ATR_AVG_PERIODS` | `20` | Rolling periods for ATR average |
| `NEWS_WINDOW_MINUTES` | `30` | ±minutes around HIGH-impact events |
