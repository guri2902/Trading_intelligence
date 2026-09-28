from __future__ import annotations

from .classifier import infer_trend, label_latest_structure
from .events import detect_bos_choch
from .patterns import detect_pullback, detect_retest
from .swings import compress_swings, detect_swings
from .zones import build_zones


class MarketStructureEngine:
    def __init__(
        self,
        *,
        left: int = 2,
        right: int = 2,
        min_prominence: float = 0.0,
        zone_tolerance_pct: float = 0.0025,
    ):
        self.left = left
        self.right = right
        self.min_prominence = min_prominence
        self.zone_tolerance_pct = zone_tolerance_pct

    def analyze(self, rows: list[dict]) -> dict:
        if len(rows) < self.left + self.right + 3:
            raise ValueError("Insufficient candles for structure analysis")

        swings = detect_swings(
            rows,
            left=self.left,
            right=self.right,
            min_prominence=self.min_prominence,
        )
        swings = compress_swings(swings)

        trend = infer_trend(swings)
        latest = label_latest_structure(swings)
        events = detect_bos_choch(rows, swings)
        supports, resistances = build_zones(
            swings,
            tolerance_pct=self.zone_tolerance_pct,
        )

        pullback = detect_pullback(rows, trend=trend)
        retest = detect_retest(rows, events)

        regime = "CONSOLIDATION"
        if events:
            last_event = events[-1]["event"]
            if last_event in {"BREAKOUT", "BOS"} and events[-1]["direction"] == "BULLISH":
                regime = "BREAKOUT"
            elif last_event in {"BREAKDOWN", "BOS"} and events[-1]["direction"] == "BEARISH":
                regime = "BREAKDOWN"
            elif last_event == "CHOCH":
                regime = "TREND"
        elif trend in {"BULLISH", "BEARISH"}:
            regime = "TREND"
        elif supports and resistances:
            regime = "RANGE"

        rejection = any(e["event"] == "REJECTION" for e in events[-5:])
        failed_breakout = any(e["event"] == "FAILED_BREAKOUT" for e in events[-5:])

        return {
            "timestamp": rows[-1]["timestamp"],
            "trend": trend,
            "regime": regime,
            "swings": swings,
            "structure": latest,
            "events": events,
            "support_zones": supports,
            "resistance_zones": resistances,
            "pullback": pullback,
            "retest": retest,
            "rejection": rejection,
            "failed_breakout": failed_breakout,
        }
