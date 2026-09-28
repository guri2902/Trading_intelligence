from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class AccountRiskContext(BaseModel):
    equity: float = Field(gt=0)
    realized_pnl_today: float = 0.0
    unrealized_pnl: float = 0.0
    open_risk: float = Field(default=0.0, ge=0)
    open_positions: int = Field(default=0, ge=0)
    trades_today: int = Field(default=0, ge=0)
    peak_equity: float | None = Field(default=None, gt=0)

    risk_per_trade_pct: float = Field(default=1.0, gt=0, le=5.0)
    max_daily_loss: float = Field(default=0.0, ge=0)
    daily_profit_lock: float = Field(default=0.0, ge=0)
    max_concurrent_risk: float = Field(default=0.0, ge=0)
    max_trades_per_day: int = Field(default=0, ge=0)
    max_open_positions: int = Field(default=0, ge=0)
    max_drawdown_pct: float = Field(default=0.0, ge=0, le=100)

    square_off_time: str | None = None  # HH:MM in supplied market timezone
    market_timestamp: datetime | None = None

    enabled: bool = True


class RiskAssessment(BaseModel):
    approved: bool
    action: str
    reason_codes: list[str] = Field(default_factory=list)
    risk_budget: float = 0.0
    unit_risk: float | None = None
    quantity: int = 0
    lot_size: int = 0
    lots: int = 0
    estimated_trade_risk: float = 0.0
    resulting_open_risk: float = 0.0
    risk_pct_of_equity: float = 0.0
    remaining_daily_loss_capacity: float | None = None
    remaining_profit_lock_capacity: float | None = None
    square_off_required: bool = False
    notes: list[str] = Field(default_factory=list)


class RiskDecision(BaseModel):
    timestamp: str
    symbol: str | None = None
    signal_action: str
    final_action: str
    approved: bool
    assessment: RiskAssessment
    trade_plan: dict | None = None
    policy: str = "Portfolio risk gates are authoritative; no order is submitted by this layer."
