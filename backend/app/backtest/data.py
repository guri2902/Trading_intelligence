from __future__ import annotations

from datetime import datetime
from typing import Iterable


def validate_historical_rows(
    rows: list[dict],
    *,
    timestamp_key: str = "timestamp",
) -> list[dict]:
    """
    Produces a chronological, duplicate-free copy.

    Backtests must operate on monotonically increasing historical data.
    """
    normalized = []

    for row in rows:
        ts = row[timestamp_key]
        if isinstance(ts, str):
            ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        normalized.append((ts, row))

    normalized.sort(key=lambda x: x[0])

    output = []
    seen = set()

    for ts, row in normalized:
        if ts in seen:
            raise ValueError(f"Duplicate historical timestamp: {ts}")
        seen.add(ts)
        output.append(row)

    if len(output) < 2:
        raise ValueError("At least two historical rows are required")

    return output


def ensure_no_future_data(
    *,
    signal_time: datetime,
    decision_time: datetime,
) -> None:
    # A historical decision may only use information available at or before
    # the signal timestamp. The execution timestamp may legitimately be later.
    if decision_time < signal_time:
        raise ValueError(
            f"Chronology violation: execution/decision time={decision_time} "
            f"< signal time={signal_time}"
        )
