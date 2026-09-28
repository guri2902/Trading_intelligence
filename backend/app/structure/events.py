from __future__ import annotations


def detect_bos_choch(
    rows: list[dict],
    swings: list[dict],
    *,
    body_confirmation: bool = True,
) -> list[dict]:
    """
    Detects structural breaks only after a confirmed swing exists.

    BOS:
      - continuation through the prior structural swing in the current trend.

    CHOCH:
      - break against the previous structural direction.

    Uses close for confirmation, rather than a wick alone, when
    body_confirmation=True.
    """
    if not rows or not swings:
        return []

    events: list[dict] = []
    current_trend = "RANGE"
    broken_levels: set[tuple[int, str]] = set()

    high_swings = [s for s in swings if s["kind"] == "HIGH"]
    low_swings = [s for s in swings if s["kind"] == "LOW"]

    for i, row in enumerate(rows):
        close = float(row["close"])
        high_candidates = [s for s in high_swings if s["index"] < i]
        low_candidates = [s for s in low_swings if s["index"] < i]

        last_high = high_candidates[-1] if high_candidates else None
        last_low = low_candidates[-1] if low_candidates else None

        if last_high and close > float(last_high["price"]):
            key = (last_high["index"], "HIGH")
            if key not in broken_levels:
                broken_levels.add(key)
                direction = "BULLISH"
                event_type = "BOS" if current_trend in ("BULLISH", "RANGE") else "CHOCH"
                current_trend = "BULLISH"
                events.append({
                    "index": i,
                    "timestamp": row["timestamp"],
                    "event": event_type,
                    "direction": direction,
                    "level": float(last_high["price"]),
                    "swing_index": last_high["index"],
                    "confidence": 0.75 if body_confirmation else 0.65,
                    "reason": "Close broke above the latest confirmed swing high.",
                })

        if last_low and close < float(last_low["price"]):
            key = (last_low["index"], "LOW")
            if key not in broken_levels:
                broken_levels.add(key)
                direction = "BEARISH"
                event_type = "BOS" if current_trend in ("BEARISH", "RANGE") else "CHOCH"
                current_trend = "BEARISH"
                events.append({
                    "index": i,
                    "timestamp": row["timestamp"],
                    "event": event_type,
                    "direction": direction,
                    "level": float(last_low["price"]),
                    "swing_index": last_low["index"],
                    "confidence": 0.75 if body_confirmation else 0.65,
                    "reason": "Close broke below the latest confirmed swing low.",
                })

    return events


def detect_breakout_rejection(
    rows: list[dict],
    levels: list[dict],
    *,
    tolerance: float = 0.001,
) -> list[dict]:
    """
    Detects contextual breakout/rejection around externally supplied zones.

    levels:
      {"price": ..., "kind": "SUPPORT"|"RESISTANCE"}
    """
    events = []
    if len(rows) < 2:
        return events

    for i in range(1, len(rows)):
        previous = rows[i - 1]
        current = rows[i]

        prev_close = float(previous["close"])
        close = float(current["close"])
        high = float(current["high"])
        low = float(current["low"])

        for level in levels:
            price = float(level["price"])
            kind = level["kind"]

            if kind == "RESISTANCE":
                broke = close > price * (1 + tolerance)
                rejected = high >= price and close < price
                failed = (
                    float(previous["close"]) > price
                    and close < price
                )

                if broke:
                    events.append({
                        "index": i,
                        "timestamp": current["timestamp"],
                        "event": "BREAKOUT",
                        "direction": "BULLISH",
                        "level": price,
                        "reason": "Close confirmed above resistance.",
                    })
                elif rejected:
                    events.append({
                        "index": i,
                        "timestamp": current["timestamp"],
                        "event": "REJECTION",
                        "direction": "BEARISH",
                        "level": price,
                        "reason": "Price traded into resistance and closed back below it.",
                    })
                elif failed:
                    events.append({
                        "index": i,
                        "timestamp": current["timestamp"],
                        "event": "FAILED_BREAKOUT",
                        "direction": "BEARISH",
                        "level": price,
                        "reason": "Prior candle was above resistance but price closed back below.",
                    })

            elif kind == "SUPPORT":
                broke = close < price * (1 - tolerance)
                rejected = low <= price and close > price
                failed = (
                    float(previous["close"]) < price
                    and close > price
                )

                if broke:
                    events.append({
                        "index": i,
                        "timestamp": current["timestamp"],
                        "event": "BREAKDOWN",
                        "direction": "BEARISH",
                        "level": price,
                        "reason": "Close confirmed below support.",
                    })
                elif rejected:
                    events.append({
                        "index": i,
                        "timestamp": current["timestamp"],
                        "event": "REJECTION",
                        "direction": "BULLISH",
                        "level": price,
                        "reason": "Price tested support and closed back above it.",
                    })
                elif failed:
                    events.append({
                        "index": i,
                        "timestamp": current["timestamp"],
                        "event": "FAILED_BREAKOUT",
                        "direction": "BULLISH",
                        "level": price,
                        "reason": "Prior candle was below support but price closed back above.",
                    })

    return events
