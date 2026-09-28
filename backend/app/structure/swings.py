from __future__ import annotations


def detect_swings(
    rows: list[dict],
    *,
    left: int = 2,
    right: int = 2,
    min_prominence: float = 0.0,
) -> list[dict]:
    """
    Pivot-style swing detection.

    A swing high is higher than the `left` candles before it and the `right`
    candles after it. A swing low is lower than both sides.

    This is deliberately conservative: a swing is only confirmed once its
    right-hand context exists, preventing future-data leakage when used
    correctly in historical mode.
    """
    if left < 1 or right < 1:
        raise ValueError("left/right must be >= 1")

    highs = [float(r["high"]) for r in rows]
    lows = [float(r["low"]) for r in rows]

    swings: list[dict] = []

    for i in range(left, len(rows) - right):
        left_highs = highs[i-left:i]
        right_highs = highs[i+1:i+right+1]
        left_lows = lows[i-left:i]
        right_lows = lows[i+1:i+right+1]

        is_high = highs[i] >= max(left_highs) and highs[i] >= max(right_highs)
        is_low = lows[i] <= min(left_lows) and lows[i] <= min(right_lows)

        if is_high:
            prominence = highs[i] - max(max(left_highs), max(right_highs))
            if prominence >= min_prominence:
                swings.append({
                    "index": i,
                    "timestamp": rows[i]["timestamp"],
                    "price": highs[i],
                    "kind": "HIGH",
                    "strength": left + right,
                })

        if is_low:
            prominence = min(min(left_lows), min(right_lows)) - lows[i]
            if prominence >= min_prominence:
                swings.append({
                    "index": i,
                    "timestamp": rows[i]["timestamp"],
                    "price": lows[i],
                    "kind": "LOW",
                    "strength": left + right,
                })

    return sorted(swings, key=lambda x: x["index"])


def compress_swings(
    swings: list[dict],
    *,
    min_distance: float = 0.0,
) -> list[dict]:
    """
    Removes nearby same-kind pivots and retains the more meaningful one:
    higher high for HIGHs, lower low for LOWs.
    """
    if not swings:
        return []

    result: list[dict] = []

    for swing in swings:
        if not result:
            result.append(swing)
            continue

        prev = result[-1]

        if swing["kind"] != prev["kind"]:
            result.append(swing)
            continue

        if abs(float(swing["price"]) - float(prev["price"])) < min_distance:
            if swing["kind"] == "HIGH" and swing["price"] >= prev["price"]:
                result[-1] = swing
            elif swing["kind"] == "LOW" and swing["price"] <= prev["price"]:
                result[-1] = swing
        else:
            result.append(swing)

    return result
