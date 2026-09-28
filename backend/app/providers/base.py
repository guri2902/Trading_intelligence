from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field


class ProviderStatus(BaseModel):
    provider: str
    available: bool
    authenticated: bool = False
    latency_ms: float | None = None
    checked_at: datetime
    message: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class Candle(BaseModel):
    instrument_key: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float | None = None
    open_interest: float | None = None
    source: str


class OptionQuote(BaseModel):
    instrument_key: str
    underlying_key: str
    expiry: date
    strike: float
    option_type: str
    ltp: float | None = None
    bid: float | None = None
    ask: float | None = None
    bid_qty: int | None = None
    ask_qty: int | None = None
    volume: float | None = None
    open_interest: float | None = None
    change_in_oi: float | None = None
    iv: float | None = None
    delta: float | None = None
    gamma: float | None = None
    theta: float | None = None
    vega: float | None = None
    rho: float | None = None
    source: str


class OptionChainSnapshot(BaseModel):
    underlying_key: str
    timestamp: datetime
    underlying_ltp: float | None = None
    expiry_dates: list[date] = Field(default_factory=list)
    quotes: list[OptionQuote] = Field(default_factory=list)
    source: str
    status: str = "OK"
    reason: str = ""


class MarketDataProvider(ABC):
    name: str

    @abstractmethod
    def health(self) -> ProviderStatus:
        raise NotImplementedError

    @abstractmethod
    def candles(
        self,
        instrument_key: str,
        unit: str,
        interval: int,
        from_date: date,
        to_date: date,
    ) -> list[Candle]:
        raise NotImplementedError


class OptionChainProvider(ABC):
    name: str

    @abstractmethod
    def health(self) -> ProviderStatus:
        raise NotImplementedError

    @abstractmethod
    def option_chain(
        self,
        underlying_key: str,
        expiry_date: date | None = None,
    ) -> OptionChainSnapshot:
        raise NotImplementedError
