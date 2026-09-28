from __future__ import annotations


def classify_sequence(swings: list[dict]) -> list[str]:
    """
    Labels each swing relative to the previous swing of the same type:
    HH, LH for highs; HL, LL for lows.
    """
    last_high = None
    last_low = None
    labels = []

    for swing in swings:
        kind = swing["kind"]

        if kind == "HIGH":
            if last_high is not None:
                labels.append(
                    "HH" if swing["price"] > last_high["price"] else "LH"
                )
            last_high = swing

        elif kind == "LOW":
            if last_low is not None:
                labels.append(
                    "HL" if swing["price"] > last_low["price"] else "LL"
                )
            last_low = swing

    return labels


def infer_trend(swings: list[dict], recent_count: int = 6) -> str:
    labels = classify_sequence(swings[-recent_count:])

    bullish = labels.count("HH") + labels.count("HL")
    bearish = labels.count("LH") + labels.count("LL")

    if bullish >= 2 and bullish > bearish + 1:
        return "BULLISH"
    if bearish >= 2 and bearish > bullish + 1:
        return "BEARISH"
    return "RANGE"


def last_same_kind(
    swings: list[dict],
    kind: str,
    offset: int = 0,
) -> dict | None:
    found = [s for s in swings if s["kind"] == kind]
    if len(found) <= offset:
        return None
    return found[-1 - offset]


def label_latest_structure(swings: list[dict]) -> dict:
    latest_high = last_same_kind(swings, "HIGH", 0)
    previous_high = last_same_kind(swings, "HIGH", 1)
    latest_low = last_same_kind(swings, "LOW", 0)
    previous_low = last_same_kind(swings, "LOW", 1)

    return {
        "last_swing_high": latest_high,
        "previous_swing_high": previous_high,
        "last_swing_low": latest_low,
        "previous_swing_low": previous_low,
        "latest_high_label": (
            None
            if not previous_high or not latest_high
            else "HH" if latest_high["price"] > previous_high["price"] else "LH"
        ),
        "latest_low_label": (
            None
            if not previous_low or not latest_low
            else "HL" if latest_low["price"] > previous_low["price"] else "LL"
        ),
    }
