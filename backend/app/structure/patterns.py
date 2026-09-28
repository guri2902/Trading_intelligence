from __future__ import annotations


def detect_pullback(
    rows: list[dict],
    *,
    trend: str,
    lookback: int = 6,
) -> bool:
    if len(rows) < lookback + 2:
        return False

    recent = rows[-lookback:]
    closes = [float(r["close"]) for r in recent]

    if trend == "BULLISH":
        return closes[-1] < max(closes[:-1]) and closes[-1] > closes[0]

    if trend == "BEARISH":
        return closes[-1] > min(closes[:-1]) and closes[-1] < closes[0]

    return False


def detect_retest(
    rows: list[dict],
    events: list[dict],
    *,
    tolerance_pct: float = 0.0025,
) -> bool:
    if len(rows) < 2:
        return False

    recent_event = None
    for event in reversed(events):
        if event["event"] in {"BREAKOUT", "BREAKDOWN", "BOS", "CHOCH"}:
            recent_event = event
            break

    if recent_event is None:
        return False

    level = recent_event.get("level")
    if level is None:
        return False

    for row in rows[-5:]:
        low = float(row["low"])
        high = float(row["high"])
        close = float(row["close"])
        if (
            low <= level * (1 + tolerance_pct)
            and high >= level * (1 - tolerance_pct)
            and (
                (recent_event["direction"] == "BULLISH" and close >= level)
                or (recent_event["direction"] == "BEARISH" and close <= level)
            )
        ):
            return True

    return False
