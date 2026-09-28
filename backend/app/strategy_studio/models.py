from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, Field


StrategyStatus = Literal["DRAFT", "ACTIVE", "DISABLED"]
StrategySource = Literal["USER", "AI", "BUILT_IN"]

BUILT_IN_STRATEGIES = [
    "VWAP_PULLBACK",
    "EMA_CONTINUATION",
    "ORB",
    "ORB_RETEST",
    "SR_REJECTION",
    "RANGE_FADE",
    "MOMENTUM_CONTINUATION",
    "VOLATILITY_BREAKOUT",
    "OPTION_DIRECTIONAL",
]


class StrategyCondition(BaseModel):
    field: str = Field(min_length=1)
    operator: Literal[
        "GT",
        "GTE",
        "LT",
        "LTE",
        "EQ",
        "NE",
        "CROSSES_ABOVE",
        "CROSSES_BELOW",
    ] = "GT"
    value: float | str = 0


class StrategyLeg(BaseModel):
    """
    One option leg configured in the Strategy Builder.

    strike_offset is stored in the existing backend representation:
    one strike step = 50 NIFTY points for the current builder.
    The frontend is responsible for presenting signed point values (+200/-200).
    """

    action: Literal["BUY", "SELL"] = "BUY"
    option_type: Literal["CE", "PE"] = "CE"
    expiry_mode: Literal["AUTO", "NEAREST", "SPECIFIC"] = "AUTO"
    expiry: str | None = None

    # Backend-compatible strike representation.
    # ATM_PLUS / ATM_MINUS are used to preserve the existing deterministic
    # strike-selection implementation.
    strike_mode: Literal[
        "ATM",
        "ATM_PLUS",
        "ATM_MINUS",
        "SPECIFIC",
    ] = "ATM"
    strike: float | None = None
    strike_offset: int = 0

    lots: int = Field(default=1, ge=1)

    # Optional UI-only/reference premium. It is harmless to persist and gives
    # the builder a place for an explicit entry premium when one is supplied.
    price: float | None = Field(default=None, ge=0)


class StrategyRules(BaseModel):
    condition_logic: Literal["ALL", "ANY"] = "ALL"
    direction: Literal["LONG", "SHORT", "AUTO"] = "AUTO"
    option_action: Literal["AUTO", "BUY_CE", "BUY_PE", "NONE"] = "AUTO"
    expiry_mode: Literal["AUTO", "NEAREST", "SPECIFIC"] = "AUTO"
    strike_mode: Literal["ATM", "ATM_PLUS", "ATM_MINUS", "SPECIFIC"] = "ATM"
    strike_offset: int = 0

    # Multi-leg option strategy definition from the Strategy Builder.
    # Default empty list keeps all older saved strategies backward compatible.
    legs: list[StrategyLeg] = Field(default_factory=list)

    stop_mode: Literal["POINTS", "PERCENT", "ATR"] = "ATR"
    stop_value: float = Field(default=1.0, gt=0)
    target_mode: Literal["POINTS", "PERCENT", "RR", "ATR"] = "RR"
    target_value: float = Field(default=1.5, gt=0)
    max_trades_per_day: int = Field(default=1, ge=1)

    entry_conditions: list[StrategyCondition] = Field(default_factory=list)
    exit_conditions: list[StrategyCondition] = Field(default_factory=list)


class StrategyVersion(BaseModel):
    version: int
    saved_at: datetime
    snapshot: dict


class StrategyDefinition(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    name: str = Field(min_length=1, max_length=120)
    description: str = ""
    source: StrategySource = "USER"
    status: StrategyStatus = "DRAFT"
    instruments: list[str] = Field(default_factory=lambda: ["NIFTY"])
    timeframe: str = "5m"

    # Existing deterministic StrategyEngine implementation to run.
    # This is a bridge field; it does not replace the engine.
    engine_strategy: str | None = None

    rules: StrategyRules = Field(default_factory=StrategyRules)
    version: int = 1
    versions: list[StrategyVersion] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class StrategyCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = ""
    source: StrategySource = "USER"
    instruments: list[str] = Field(default_factory=lambda: ["NIFTY"])
    timeframe: str = "5m"
    engine_strategy: str | None = None
    rules: StrategyRules = Field(default_factory=StrategyRules)


class StrategyUpdateRequest(StrategyCreateRequest):
    pass


class StrategyBacktestRequest(BaseModel):
    rows: list[dict] = Field(min_length=15)
    initial_capital: float = Field(default=100000.0, gt=0)
    quantity: float = Field(default=1.0, gt=0)
    slippage_bps: float = Field(default=5.0, ge=0)
    latency_bars: int = Field(default=1, ge=0)
