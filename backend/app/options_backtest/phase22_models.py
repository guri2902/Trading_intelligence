from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel, Field
from .models import HistoricalOptionBar, OptionsBacktestConfig

class OptionLeg(BaseModel):
    contract_key: str = Field(min_length=1)
    side: str = Field(default='BUY')
    quantity: int = Field(gt=0)

class ExpirySettlement(BaseModel):
    contract_key: str
    timestamp: datetime
    expiry: str
    strike: float
    option_type: str
    underlying_close: float | None
    settlement_price: float
    intrinsic_value: float

class SpreadTradeRecord(BaseModel):
    trade_id: int
    entry_time: datetime
    exit_time: datetime
    legs: list[OptionLeg]
    entry_value: float
    exit_value: float
    gross_pnl: float
    costs: float
    net_pnl: float
    exit_reason: str

class MultiLegOptionsBacktestConfig(OptionsBacktestConfig):
    auto_expiry_exit: bool = True
    allow_expiry_mismatch: bool = False
    max_legs: int = Field(default=8, ge=1, le=20)

class MultiLegOptionsBacktestResult(BaseModel):
    strategy: str
    trades: list[SpreadTradeRecord]
    settlements: list[ExpirySettlement]
    metrics: dict[str, float | int | None]
    warnings: list[str] = Field(default_factory=list)
    no_lookahead: bool = True
    used_actual_option_prices: bool = True
    live_execution: bool = False
