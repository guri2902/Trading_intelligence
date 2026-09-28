from __future__ import annotations

from datetime import datetime, timezone

from ..market_calendar import MarketCalendar


def validate_timestamp(
    timestamp: datetime,
    calendar: MarketCalendar,
    *,
    allow_preopen: bool = True,
) -> dict:
    ts = timestamp
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)

    session = calendar.session_at(ts)

    allowed = {"REGULAR"}
    if allow_preopen:
        allowed.add("PRE_OPEN")

    return {
        "timestamp_utc": ts.astimezone(timezone.utc).isoformat(),
        "timestamp_ist": calendar.as_ist(ts).isoformat(),
        "session": session,
        "is_trading_session": session in allowed,
        "weekend": calendar.is_weekend(calendar.as_ist(ts).date()),
        "holiday": calendar.is_holiday(calendar.as_ist(ts).date()),
    }


def validate_candle_timestamps(
    timestamps: list[datetime],
    calendar: MarketCalendar,
) -> dict:
    checks = [validate_timestamp(ts, calendar, allow_preopen=False) for ts in timestamps]
    invalid = [x for x in checks if not x["is_trading_session"]]

    return {
        "count": len(checks),
        "invalid_count": len(invalid),
        "valid": len(invalid) == 0,
        "invalid_samples": invalid[:20],
    }
