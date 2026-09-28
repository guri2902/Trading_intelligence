from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from ..options_backtest.models import (
    HistoricalOptionBar,
    OptionsBacktestConfig,
)


class OptionsBacktestRequest(BaseModel):
    strategy_name: str = Field(min_length=1)
    bars: list[HistoricalOptionBar] = Field(min_length=1)
    signal: dict
    config: OptionsBacktestConfig = Field(default_factory=OptionsBacktestConfig)


class OptionVaultBacktestRequest(BaseModel):
    strategy_name: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    expiry: date | None = None
    strike: float | None = None
    side: str | None = None
    from_date: date | None = None
    to_date: date | None = None
    signal: dict
    config: OptionsBacktestConfig = Field(default_factory=OptionsBacktestConfig)