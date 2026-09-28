from __future__ import annotations
from datetime import datetime
from fastapi import APIRouter
from pydantic import BaseModel, Field
from ..paper.execution import CostConfig, MarketQuote, RealisticExecutionSimulator

router = APIRouter(prefix="/phase20", tags=["phase20"])

class ExecutionRequest(BaseModel):
    side: str
    quantity: int = Field(gt=0)
    ltp: float = Field(gt=0)
    bid: float | None = Field(default=None, gt=0)
    ask: float | None = Field(default=None, gt=0)
    available_qty: int | None = Field(default=None, ge=0)

class CostRequest(BaseModel):
    buy_turnover: float = Field(ge=0)
    sell_turnover: float = Field(ge=0)
    orders: int = Field(default=2, ge=0)

class ExpiryRequest(BaseModel):
    option_type: str
    strike: float = Field(gt=0)
    underlying_ltp: float = Field(gt=0)

@router.get("/health")
def health():
    return {"status":"ok","phase":20,"mode":"realistic_paper_execution","live_execution":False}

@router.post("/fill")
def fill(req: ExecutionRequest):
    sim = RealisticExecutionSimulator()
    return sim.fill(req.side, req.quantity, MarketQuote(req.ltp, req.bid, req.ask, req.available_qty)).__dict__

@router.post("/costs")
def costs(req: CostRequest):
    return RealisticExecutionSimulator().costs(req.buy_turnover, req.sell_turnover, req.orders).as_dict()

@router.post("/expiry-value")
def expiry_value(req: ExpiryRequest):
    return {"intrinsic_value": RealisticExecutionSimulator.expiry_value(req.option_type, req.strike, req.underlying_ltp)}
