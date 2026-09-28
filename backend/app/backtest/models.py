from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class CostConfig(BaseModel):
    brokerage_per_order: float = 0.0
    stt_rate: float = 0.0
    exchange_txn_rate: float = 0.0
    gst_rate: float = 0.0
    sebi_rate: float = 0.0
    stamp_duty_rate: float = 0.0
    slippage_bps: float = 0.0
    latency_bars: int = Field(default=0, ge=0)
    partial_fill_ratio: float = Field(default=1.0, gt=0, le=1.0)


class BacktestConfig(BaseModel):
    initial_capital: float = Field(default=10000.0, gt=0)
    risk_per_trade_pct: float = Field(default=1.0, gt=0)
    max_concurrent_positions: int = Field(default=1, ge=1)
    quantity: float = Field(default=1.0, gt=0)
    allow_short: bool = True
    costs: CostConfig = Field(default_factory=CostConfig)


class TradeRecord(BaseModel):
    trade_id: int
    strategy: str
    direction: str
    entry_time: datetime | str
    exit_time: datetime | str | None = None
    requested_entry: float
    filled_entry: float | None = None
    exit_price: float | None = None
    quantity: float
    gross_pnl: float = 0.0
    total_cost: float = 0.0
    net_pnl: float = 0.0
    max_favorable_excursion: float = 0.0
    max_adverse_excursion: float = 0.0
    exit_reason: str | None = None
    duration_bars: int = 0
    win: bool | None = None


class EquityPoint(BaseModel):
    timestamp: datetime | str
    equity: float
    realized_pnl: float
    drawdown: float
    drawdown_pct: float


class BacktestMetrics(BaseModel):
    initial_capital: float
    final_equity: float
    net_profit: float
    return_pct: float
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate_pct: float
    gross_profit: float
    gross_loss: float
    profit_factor: float | None
    expectancy_per_trade: float
    max_drawdown: float
    max_drawdown_pct: float
    sharpe: float | None
    sortino: float | None
    average_win: float
    average_loss: float
    largest_win: float
    largest_loss: float


class BacktestResult(BaseModel):
    strategy: str
    mode: str  # UNDERLYING / OPTIONS
    metrics: BacktestMetrics
    trades: list[TradeRecord]
    equity_curve: list[EquityPoint]
    warnings: list[str] = Field(default_factory=list)
