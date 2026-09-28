from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable
from zoneinfo import ZoneInfo

from ..market_calendar import MarketCalendar


@dataclass(frozen=True)
class QualityResult:
    status: str
    reason: str
    stale: bool
    duplicate_count: int
    gap_count: int
    malformed_count: int

    @property
    def signal_safe(self) -> bool:
        return (
            self.status == "PASS"
            and not self.stale
            and self.duplicate_count == 0
            and self.gap_count == 0
            and self.malformed_count == 0
        )


def evaluate_candles(
    candles: list[dict],
    *,
    timeframe_minutes: int | None = None,
    max_age_seconds: int | None = None,
    calendar: MarketCalendar | None = None,
) -> QualityResult:
    timestamps = []
    malformed = 0

    for row in candles:
        try:
            ts = datetime.fromisoformat(
                str(row["timestamp"]).replace("Z", "+00:00")
            )
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            timestamps.append(ts.astimezone(timezone.utc))

            o = float(row["open"])
            h = float(row["high"])
            l = float(row["low"])
            c = float(row["close"])

            if o < 0 or h < 0 or l < 0 or c < 0:
                malformed += 1
            if h < max(o, c) or l > min(o, c) or l > h:
                malformed += 1
        except (KeyError, ValueError, TypeError):
            malformed += 1

    duplicate_count = len(timestamps) - len(set(timestamps))
    ordered = sorted(set(timestamps))
    gap_count = 0

    if timeframe_minutes and len(ordered) > 1:
        expected_seconds = timeframe_minutes * 60
        ist = ZoneInfo("Asia/Kolkata")

        for previous, current in zip(ordered, ordered[1:]):
            previous_ist = previous.astimezone(ist)
            current_ist = current.astimezone(ist)

            # Do not treat overnight, weekend, or holiday boundaries
            # as missing intraday candles.
            if previous_ist.date() != current_ist.date():
                continue

            delta = (current - previous).total_seconds()

            # A genuine intraday gap exists when one or more expected
            # candles are missing inside the same trading session.
            if delta > expected_seconds:
                missing_intervals = int(
                    delta // expected_seconds
                ) - 1

                if missing_intervals > 0:
                    gap_count += missing_intervals

    stale = False
    if max_age_seconds is not None and ordered:
        age = (
            datetime.now(timezone.utc) - ordered[-1]
        ).total_seconds()
        stale = age > max_age_seconds

    if not candles:
        return QualityResult(
            status="FAIL",
            reason="No candle rows",
            stale=False,
            duplicate_count=0,
            gap_count=0,
            malformed_count=0,
        )

    if malformed:
        reason = "Malformed OHLC rows"
        status = "FAIL"
    elif stale:
        reason = "Latest candle is stale"
        status = "FAIL"
    elif duplicate_count:
        reason = "Duplicate timestamps detected"
        status = "FAIL"
    elif gap_count:
        reason = "Unexpected candle gaps detected"
        status = "WARN"
    else:
        reason = "Candle data passed structural checks"
        status = "PASS"

    return QualityResult(
        status=status,
        reason=reason,
        stale=stale,
        duplicate_count=duplicate_count,
        gap_count=gap_count,
        malformed_count=malformed,
    )


def evaluate_option_quotes(
    quotes: list[dict],
    *,
    snapshot_timestamp: datetime,
    max_age_seconds: int = 60,
    max_relative_spread: float = 0.10,
) -> QualityResult:
    ts = snapshot_timestamp
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    else:
        ts = ts.astimezone(timezone.utc)

    stale = (
        datetime.now(timezone.utc) - ts
    ).total_seconds() > max_age_seconds

    keys = []
    missing = 0
    wide_spreads = 0
    malformed = 0

    for row in quotes:
        key = (
            row.get("instrument_key"),
            row.get("expiry"),
            row.get("strike"),
            row.get("option_type"),
        )
        keys.append(key)

        ltp = row.get("ltp")
        bid = row.get("bid")
        ask = row.get("ask")

        if ltp is None:
            missing += 1
        if bid is not None and ask is not None:
            try:
                if ask < bid or bid < 0 or ask < 0:
                    malformed += 1
                elif ltp and ltp > 0:
                    if (float(ask) - float(bid)) / float(ltp) > max_relative_spread:
                        wide_spreads += 1
            except (ValueError, TypeError, ZeroDivisionError):
                malformed += 1

    duplicates = len(keys) - len(set(keys))

    if not quotes:
        return QualityResult(
            status="FAIL",
            reason="No option-chain quotes",
            stale=stale,
            duplicate_count=0,
            gap_count=0,
            malformed_count=0,
        )

    if stale:
        reason = "Option-chain snapshot is stale"
        status = "FAIL"
    elif duplicates:
        reason = "Duplicate option contracts detected"
        status = "FAIL"
    elif malformed:
        reason = "Malformed option quotes detected"
        status = "FAIL"
    elif missing == len(quotes):
        reason = "All quotes missing LTP"
        status = "FAIL"
    elif wide_spreads > 0:
        reason = f"{wide_spreads} quote(s) exceed spread threshold"
        status = "PASS"
    else:
        reason = "Option-chain data passed structural checks"
        status = "PASS"

    return QualityResult(
        status=status,
        reason=reason,
        stale=stale,
        duplicate_count=duplicates,
        gap_count=0,
        malformed_count=malformed,
    )
