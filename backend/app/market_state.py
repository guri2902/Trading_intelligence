from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field


class CanonicalMarketState(BaseModel):
    """
    Single normalized state object consumed by later feature/strategy/agent layers.
    It is intentionally mostly raw/normalized state at this phase.
    """

    generated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    market_status: str = "UNKNOWN"

    underlying_instrument: str
    underlying_ltp: float | None = None
    previous_close: float | None = None
    day_open: float | None = None
    day_high: float | None = None
    day_low: float | None = None

    timestamp: datetime | None = None
    data_sources: list[str] = Field(default_factory=list)
    data_freshness_seconds: float | None = None
    data_quality_status: str = "UNKNOWN"

    option_chain_available: bool = False
    option_chain_status: str = "UNAVAILABLE"
    expiry_dates: list[str] = Field(default_factory=list)

    metadata: dict[str, Any] = Field(default_factory=dict)
