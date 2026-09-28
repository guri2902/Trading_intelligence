from __future__ import annotations

from pydantic import BaseModel, Field


class RiskConfig(BaseModel):
    capital: float = Field(default=100000.0, gt=0)

    # Cash-risk budgets, not percentage-only controls.
    per_trade_risk: float = Field(default=1000.0, ge=0)
    daily_risk_budget: float = Field(default=2000.0, ge=0)
    weekly_risk_budget: float = Field(default=5000.0, ge=0)
    monthly_risk_budget: float = Field(default=10000.0, ge=0)

    max_concurrent_risk: float = Field(default=2000.0, ge=0)
    max_open_positions: int = Field(default=1, ge=1)
    max_trades_per_day: int = Field(default=5, ge=1)
    max_drawdown_pct: float = Field(default=5.0, ge=0, le=100)
    square_off_time: str = "15:20"

    # User-editable lot sizes. These are configuration values, not hardcoded
    # exchange assumptions.
    lot_sizes: dict[str, int] = Field(
        default_factory=lambda: {
            "NIFTY": 65,
            "BANKNIFTY": 30,
            "FINNIFTY": 60,
            "SENSEX": 20,
        }
    )


class RiskCalculationRequest(BaseModel):
    instrument: str = Field(min_length=1)
    entry_price: float = Field(gt=0)
    stop_loss: float = Field(gt=0)
    lot_size: int | None = Field(default=None, ge=1)

    realized_loss_today: float = Field(default=0.0, ge=0)
    realized_loss_week: float = Field(default=0.0, ge=0)
    realized_loss_month: float = Field(default=0.0, ge=0)
    open_risk: float = Field(default=0.0, ge=0)
    open_positions: int = Field(default=0, ge=0)
    trades_today: int = Field(default=0, ge=0)


class RiskCalculation(BaseModel):
    instrument: str
    capital: float
    lot_size: int
    unit_risk: float
    risk_per_lot: float
    configured_per_trade_risk: float
    daily_remaining: float
    weekly_remaining: float
    monthly_remaining: float
    concurrent_remaining: float
    effective_risk_budget: float
    max_lots_by_risk: int
    quantity: int
    estimated_trade_risk: float
    capital_required: float
    max_open_positions_reached: bool
    max_trades_reached: bool
    eligible: bool
    reasons: list[str] = Field(default_factory=list)
