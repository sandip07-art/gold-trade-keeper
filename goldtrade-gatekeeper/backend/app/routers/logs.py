import csv
import io
from datetime import datetime, date
from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional

from ..database import get_db
from ..models import DecisionLog, TradeRecord

router = APIRouter(tags=["logs"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class TradeRecordIn(BaseModel):
    result:           str            # WIN | LOSS | BE
    rr:               Optional[float] = None
    dxy_state:        str
    volatility_state: str
    session:          str
    pnl_pct:          Optional[float] = None


# ── Decision log endpoints ────────────────────────────────────────────────────

@router.get("/logs", summary="Fetch recent gate decisions")
def get_logs(
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(DecisionLog)
        .order_by(DecisionLog.timestamp.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id":          r.id,
            "timestamp":   r.timestamp.isoformat(),
            "decision":    r.decision,
            "bias":        r.bias,
            "reasons":     r.reasons,
            "metrics":     r.metrics,
            "advisory":    r.advisory,
            "strict_mode": r.strict_mode,
        }
        for r in rows
    ]


@router.get("/logs/export", summary="Download all decision logs as CSV")
def export_logs(db: Session = Depends(get_db)):
    rows = db.query(DecisionLog).order_by(DecisionLog.timestamp.desc()).all()

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "id", "timestamp", "decision", "bias", "reasons",
        "atr", "atr_avg", "atr_ratio",
        "session", "vol_state", "dxy_state",
        "xauusd_price", "dxy_price",
        "trades_today", "daily_loss_pct", "strict_mode",
    ])
    for r in rows:
        m = r.metrics or {}
        writer.writerow([
            r.id,
            r.timestamp.isoformat(),
            r.decision,
            r.bias,
            " | ".join(r.reasons or []),
            m.get("atr", ""),
            m.get("atr_avg", ""),
            m.get("atr_ratio", ""),
            m.get("session", ""),
            m.get("vol_state", ""),
            m.get("dxy_state", ""),
            m.get("xauusd_price", ""),
            m.get("dxy_price", ""),
            m.get("trades_today", ""),
            m.get("daily_loss_pct", ""),
            r.strict_mode,
        ])

    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=gate_decisions.csv"},
    )


# ── Trade record endpoints ────────────────────────────────────────────────────

@router.post("/trades", summary="Record a completed trade outcome")
def record_trade(body: TradeRecordIn, db: Session = Depends(get_db)):
    record = TradeRecord(
        date=date.today().isoformat(),
        result=body.result.upper(),
        rr=body.rr,
        dxy_state=body.dxy_state,
        volatility_state=body.volatility_state,
        session=body.session,
        pnl_pct=body.pnl_pct,
    )
    db.add(record)
    db.commit()
    return {"status": "ok", "id": record.id}


@router.get("/trades", summary="List recorded trade outcomes")
def get_trades(
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(TradeRecord)
        .order_by(TradeRecord.timestamp.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id":               r.id,
            "timestamp":        r.timestamp.isoformat(),
            "date":             r.date,
            "result":           r.result,
            "rr":               r.rr,
            "dxy_state":        r.dxy_state,
            "volatility_state": r.volatility_state,
            "session":          r.session,
            "pnl_pct":          r.pnl_pct,
        }
        for r in rows
    ]
