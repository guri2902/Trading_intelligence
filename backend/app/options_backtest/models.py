from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field, field_validator


class HistoricalOptionBar(BaseModel):
    timestamp: datetime
    contract_key: str = Field(min_length=1)
    underlying_symbol: str = Field(min_length=1)
    expiry: str = Field(min_length=8)
    strike: float = Field(gt=0)
    option_type: str
    open: float = Field(gt=0)
    high: float = Field(gt=0)
    low: float = Field(gt=0)
    close: float = Field(gt=0)
    volume: int | None = Field(default=None, ge=0)
    open_interest: int | None = Field(default=None, ge=0)
    bid: float | None = Field(default=None, gt=0)
    ask: float | None = Field(default=None, gt=0)
    underlying_close: float | None = Field(default=None, gt=0)

    @field_validator("option_type")
    @classmethod
    def validate_option_type(cls, value: str) -> str:
        value = value.upper()
        if value not in {"CE", "PE"}:
            raise ValueError("OPTION_TYPE_MUST_BE_CE_OR_PE")
        return value


class OptionsBacktestConfig(BaseModel):
    initial_capital: float = Field(default=100000.0, gt=0)
    quantity: int = Field(default=1, gt=0)
    slippage_bps: float = Field(default=5.0, ge=0)
    brokerage_per_order: float = Field(default=20.0, ge=0)
    exchange_txn_rate: float = Field(default=0.0003553, ge=0)
    sebi_rate: float = Field(default=0.000001, ge=0)
    gst_rate: float = Field(default=0.18, ge=0)
    stamp_duty_rate: float = Field(default=0.00003, ge=0)
    stt_sell_rate: float = Field(default=0.001, ge=0)
    latency_bars: int = Field(default=1, ge=1)
    max_trades: int | None = Field(default=None, ge=1)


class OptionsTradeRecord(BaseModel):
    trade_id: int
    contract_key: str
    option_type: str
    strike: float
    expiry: str
    entry_time: datetime
    exit_time: datetime
    entry_price: float
    exit_price: float
    quantity: int
    gross_pnl: float
    costs: float
    net_pnl: float
    exit_reason: str


class OptionsBacktestResult(BaseModel):
    strategy: str
    mode: str = "HISTORICAL_OPTIONS"
    metrics: dict[str, object]
    trades: list[OptionsTradeRecord]
    warnings: list[str] = Field(default_factory=list)
    no_lookahead: bool = True
    used_actual_option_prices: bool = True
