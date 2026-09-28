from __future__ import annotations

from datetime import date, datetime
from pydantic import BaseModel, Field


class OptionContract(BaseModel):
    instrument_key: str
    underlying_key: str
    underlying_symbol: str
    expiry: date
    strike: float
    option_type: str  # CE / PE
    lot_size: int | None = None
    tick_size: float | None = None


class OptionQuoteState(BaseModel):
    contract: OptionContract
    timestamp: datetime
    underlying_spot: float | None = None

    ltp: float | None = None
    close_price: float | None = None
    bid: float | None = None
    ask: float | None = None
    bid_qty: int | None = None
    ask_qty: int | None = None
    volume: float | None = None
    open_interest: float | None = None
    previous_oi: float | None = None

    iv: float | None = None
    delta: float | None = None
    gamma: float | None = None
    theta: float | None = None
    vega: float | None = None
    rho: float | None = None
    pop: float | None = None


class OptionMetrics(BaseModel):
    intrinsic_value: float | None = None
    extrinsic_value: float | None = None
    mid_price: float | None = None
    spread: float | None = None
    spread_pct: float | None = None
    oi_change: float | None = None
    moneyness: float | None = None
    days_to_expiry: float | None = None
    liquidity_score: float = 0.0
    quality_score: float = 0.0


class OptionCandidate(BaseModel):
    quote: OptionQuoteState
    metrics: OptionMetrics
    rejection_reasons: list[str] = Field(default_factory=list)
    eligible: bool = False
    rank_score: float = 0.0


class CEPEDebate(BaseModel):
    underlying_symbol: str
    expiry: date
    atm_strike: float | None
    ce_candidate: OptionCandidate | None
    pe_candidate: OptionCandidate | None
    ce_score: float
    pe_score: float
    winner: str  # CE / PE / NO_TRADE
    reason: str
