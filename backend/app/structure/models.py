from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class SwingPoint(BaseModel):
    index: int
    timestamp: datetime | str
    price: float
    kind: str  # HIGH / LOW
    strength: int = Field(default=1, ge=1)


class StructureEvent(BaseModel):
    index: int
    timestamp: datetime | str
    event: str  # BOS / CHOCH / BREAKOUT / BREAKDOWN / REJECTION / FAILED_BREAKOUT
    direction: str | None = None  # BULLISH / BEARISH / NONE
    level: float | None = None
    swing_index: int | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    reason: str = ""


class StructureSnapshot(BaseModel):
    timestamp: datetime | str
    trend: str  # BULLISH / BEARISH / RANGE / UNKNOWN
    regime: str  # TREND / RANGE / CONSOLIDATION / BREAKOUT / BREAKDOWN
    last_swing_high: SwingPoint | None = None
    last_swing_low: SwingPoint | None = None
    previous_swing_high: SwingPoint | None = None
    previous_swing_low: SwingPoint | None = None
    structure_sequence: list[str] = Field(default_factory=list)
    events: list[StructureEvent] = Field(default_factory=list)
    support_zones: list[dict] = Field(default_factory=list)
    resistance_zones: list[dict] = Field(default_factory=list)
    pullback: bool = False
    retest: bool = False
    rejection: bool = False
    failed_breakout: bool = False
