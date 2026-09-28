from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo


IST = ZoneInfo("Asia/Kolkata")


@dataclass(frozen=True)
class SessionWindow:
    name: str
    start: time
    end: time


EQUITY_DERIVATIVES_PREOPEN = SessionWindow(
    name="pre_open",
    start=time(9, 0),
    end=time(9, 15),
)

EQUITY_DERIVATIVES_REGULAR = SessionWindow(
    name="regular",
    start=time(9, 15),
    end=time(15, 40),
)

EQUITY_DERIVATIVES_MODIFICATION = SessionWindow(
    name="trade_modification",
    start=time(15, 40),
    end=time(16, 15),
)


class MarketCalendar:
    """
    NSE India equity-derivatives session semantics.

    Holiday dates are externalized so the list can be refreshed from official
    NSE holiday data without changing application code.
    """

    def __init__(self, holidays: set[date] | None = None) -> None:
        self.holidays = holidays or set()

    @staticmethod
    def as_ist(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=IST)
        return value.astimezone(IST)

    def is_weekend(self, d: date) -> bool:
        return d.weekday() >= 5

    def is_holiday(self, d: date) -> bool:
        return d in self.holidays

    def is_trading_day(self, d: date) -> bool:
        return not self.is_weekend(d) and not self.is_holiday(d)

    def session_at(self, value: datetime) -> str:
        ts = self.as_ist(value)

        if not self.is_trading_day(ts.date()):
            return "CLOSED"

        t = ts.time()

        if EQUITY_DERIVATIVES_PREOPEN.start <= t < EQUITY_DERIVATIVES_PREOPEN.end:
            return "PRE_OPEN"

        if EQUITY_DERIVATIVES_REGULAR.start <= t <= EQUITY_DERIVATIVES_REGULAR.end:
            return "REGULAR"

        if (
            EQUITY_DERIVATIVES_MODIFICATION.start
            <= t
            < EQUITY_DERIVATIVES_MODIFICATION.end
        ):
            return "TRADE_MODIFICATION"

        return "CLOSED"

    def next_trading_day(self, d: date) -> date:
        candidate = d + timedelta(days=1)
        while not self.is_trading_day(candidate):
            candidate += timedelta(days=1)
        return candidate
