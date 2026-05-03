from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import engine
from .models import Base
from .routers import ingest, decision, logs

# Auto-create all tables (idempotent)
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="GoldTrade Gatekeeper",
    description=(
        "Rule-based trade gate for XAUUSD. "
        "Enforces session, news, volatility and risk discipline. "
        "No AI prediction — pure rule enforcement."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ingest.router)
app.include_router(decision.router)
app.include_router(logs.router)


@app.get("/health", tags=["system"])
def health():
    return {"status": "ok", "service": "GoldTrade Gatekeeper"}
