from datetime import datetime, time
from zoneinfo import ZoneInfo

from backend.app.market_calendar import MarketCalendar


def test_regular_session():
    cal = MarketCalendar()

    ts = datetime(
        2026, 9, 10, 10, 0,
        tzinfo=ZoneInfo("Asia/Kolkata"),
    )
    assert cal.session_at(ts) == "REGULAR"


def test_before_open_is_closed():
    cal = MarketCalendar()

    ts = datetime(
        2026, 9, 10, 8, 59,
        tzinfo=ZoneInfo("Asia/Kolkata"),
    )
    assert cal.session_at(ts) == "CLOSED"


def test_preopen():
    cal = MarketCalendar()

    ts = datetime(
        2026, 9, 10, 9, 5,
        tzinfo=ZoneInfo("Asia/Kolkata"),
    )
    assert cal.session_at(ts) == "PRE_OPEN"


def test_weekend_closed():
    cal = MarketCalendar()

    ts = datetime(
        2026, 9, 12, 10, 0,
        tzinfo=ZoneInfo("Asia/Kolkata"),
    )
    assert cal.session_at(ts) == "CLOSED"
