from __future__ import annotations


def build_zones(
    swings: list[dict],
    *,
    tolerance_pct: float = 0.0025,
    max_zones: int = 5,
) -> tuple[list[dict], list[dict]]:
    """
    Groups nearby swing prices into contextual support/resistance zones.

    The output is intentionally a zone/range rather than a magical exact price.
    """
    highs = [s for s in swings if s["kind"] == "HIGH"]
    lows = [s for s in swings if s["kind"] == "LOW"]

    def group(points):
        zones = []

        for point in sorted(points, key=lambda x: x["price"]):
            price = float(point["price"])
            placed = False

            for zone in zones:
                center = zone["center"]
                if abs(price - center) / max(center, 1e-9) <= tolerance_pct:
                    zone["prices"].append(price)
                    zone["touches"] += 1
                    zone["low"] = min(zone["low"], price)
                    zone["high"] = max(zone["high"], price)
                    zone["center"] = sum(zone["prices"]) / len(zone["prices"])
                    placed = True
                    break

            if not placed:
                zones.append({
                    "center": price,
                    "low": price,
                    "high": price,
                    "touches": 1,
                    "prices": [price],
                })

        zones.sort(key=lambda z: (z["touches"], z["center"]), reverse=True)
        return zones[:max_zones]

    return group(lows), group(highs)
