from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel, Field

class PaperOrderRequest(BaseModel):
    account_id: str = "default"
    symbol: str
    action: str
    option_type: str
    strike: float
    expiry: str
    quantity: int = Field(gt=0)
    entry_price: float = Field(gt=0)
    stop_loss: float = Field(gt=0)
    target_1: float | None = Field(default=None, gt=0)
    target_2: float | None = Field(default=None, gt=0)
    timestamp: datetime
    bid: float | None = Field(default=None, gt=0)
    ask: float | None = Field(default=None, gt=0)
    available_quantity: int | None = Field(default=None, ge=0)
    signal_id: str | None = None
    requested_quantity: int | None = None
    filled_quantity: int | None = None
    total_costs: float = 0.0
    partial_fill: bool = False
    source: str = "signal_engine"

class PaperMarkRequest(BaseModel):
    account_id: str = "default"
    instrument_key: str
    price: float = Field(gt=0)
    timestamp: datetime
    bid: float | None = Field(default=None, gt=0)
    ask: float | None = Field(default=None, gt=0)
    available_quantity: int | None = Field(default=None, ge=0)
    underlying_ltp: float | None = Field(default=None, gt=0)
    market_closed: bool = False

class PaperCloseRequest(BaseModel):
    account_id: str = "default"
    position_id: str
    exit_price: float = Field(gt=0)
    timestamp: datetime
    reason: str = "MANUAL_CLOSE"

class PaperPosition(BaseModel):
    position_id: str
    account_id: str
    symbol: str
    option_type: str
    strike: float
    expiry: str
    quantity: int
    entry_price: float
    mark_price: float
    stop_loss: float
    target_1: float | None = None
    target_2: float | None = None
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    status: str = "OPEN"
    opened_at: datetime
    closed_at: datetime | None = None
    exit_price: float | None = None
    close_reason: str | None = None
    signal_id: str | None = None
    requested_quantity: int | None = None
    filled_quantity: int | None = None
    total_costs: float = 0.0
    partial_fill: bool = False

class PaperAccount(BaseModel):
    account_id: str
    starting_equity: float
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    open_positions: int = 0
    total_trades: int = 0
    win_trades: int = 0
    loss_trades: int = 0
    status: str = "ACTIVE"
