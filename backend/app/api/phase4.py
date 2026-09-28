from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter

from ..market_calendar import MarketCalendar
from ..instruments.upstox_master import (
    UpstoxInstrumentMaster,
    default_nse_index_and_fo_filters,
)
from ..data_validation.session_validation import validate_timestamp

router = APIRouter(prefix="/phase4", tags=["phase4"])

calendar = MarketCalendar()
master = UpstoxInstrumentMaster()


@router.get("/market-session")
def market_session(timestamp: datetime | None = None):
    value = timestamp or datetime.now(timezone.utc)
    result = validate_timestamp(value, calendar)
    return result


@router.post("/instruments/sync-core")
def sync_core_instruments():
    filters = default_nse_index_and_fo_filters()
    return master.sync(**filters)
