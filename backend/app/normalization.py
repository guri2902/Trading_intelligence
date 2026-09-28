from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Iterable

from .providers.base import Candle, OptionChainSnapshot


IST = timezone(timedelta(hours=5, minutes=30))


def normalize_candles(candles: Iterable[Candle]) -> list[Candle]:
    """
    Deterministic normalization:
    - UTC timestamps
    - de-duplicate by timestamp
    - stable chronological ordering
    - reject malformed OHLC
    """
    normalized: dict[datetime, Candle] = {}

    for c in candles:
        ts = c.timestamp
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        else:
            ts = ts.astimezone(timezone.utc)

        if c.high < max(c.open, c.close) or c.low > min(c.open, c.close):
            continue
        if c.low > c.high or c.open < 0 or c.high < 0 or c.low < 0 or c.close < 0:
            continue

        normalized[ts] = c.model_copy(update={"timestamp": ts})

    return [normalized[k] for k in sorted(normalized)]


def candle_quality_report(
    candles: list[Candle],
    *,
    expected_interval_minutes: int | None = None,
    max_staleness_seconds: int | None = None,
) -> dict:
    timestamps = [c.timestamp for c in candles]
    duplicate_count = len(timestamps) - len(set(timestamps))

    gaps = []
    if expected_interval_minutes and len(timestamps) > 1:
        expected = timedelta(minutes=expected_interval_minutes)
        for prev, curr in zip(timestamps, timestamps[1:]):
            delta = curr - prev
            if delta > expected * 2:
                gaps.append(
                    {
                        "from": prev.isoformat(),
                        "to": curr.isoformat(),
                        "seconds": delta.total_seconds(),
                    }
                )

    now = datetime.now(timezone.utc)
    last = max(timestamps) if timestamps else None
    stale = (
        max_staleness_seconds is not None
        and last is not None
        and (now - last).total_seconds() > max_staleness_seconds
    )

    return {
        "count": len(candles),
        "duplicates": duplicate_count,
        "gaps": gaps,
        "last_timestamp": last.isoformat() if last else None,
        "stale": stale,
        "valid": bool(candles) and duplicate_count == 0 and not stale,
    }


def option_chain_quality_report(
    snapshot: OptionChainSnapshot,
    *,
    max_staleness_seconds: int = 60,
) -> dict:
    now = datetime.now(timezone.utc)
    ts = snapshot.timestamp
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    age = (now - ts).total_seconds()

    duplicate_keys = [
        (q.instrument_key, q.expiry, q.strike, q.option_type)
        for q in snapshot.quotes
    ]
    duplicate_count = len(duplicate_keys) - len(set(duplicate_keys))

    missing_ltp = sum(q.ltp is None for q in snapshot.quotes)
    wide_spread = 0
    for q in snapshot.quotes:
        if q.bid is not None and q.ask is not None and q.ltp is not None and q.ltp > 0:
            if (q.ask - q.bid) / q.ltp > 0.10:
                wide_spread += 1

    return {
        "status": snapshot.status,
        "age_seconds": age,
        "stale": age > max_staleness_seconds,
        "quotes": len(snapshot.quotes),
        "duplicate_quotes": duplicate_count,
        "missing_ltp": missing_ltp,
        "wide_spread_quotes": wide_spread,
        "valid_for_signal_engine": (
            snapshot.status == "OK"
            and len(snapshot.quotes) > 0
            and duplicate_count == 0
            and age <= max_staleness_seconds
        ),
        "reason": snapshot.reason,
    }
