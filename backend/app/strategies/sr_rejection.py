from __future__ import annotations

from .base import Strategy
from .models import StrategyContext, StrategySetup


class SRRejectionStrategy(Strategy):
    name = "SR_REJECTION"

    def evaluate(self, context: StrategyContext) -> StrategySetup:
        f = context.features
        s = context.structure
        close = float(f["price"])
        atr = f.get("atr_14")

        if atr is None:
            return StrategySetup(
                strategy=self.name,
                direction="NONE",
                state="NO_SETUP",
                wait_for=["ATR"],
            )

        supports = s.get("support_zones", [])
        resistances = s.get("resistance_zones", [])

        nearest_support = min(
            supports,
            key=lambda z: abs(close - float(z["center"])),
            default=None,
        )
        nearest_resistance = min(
            resistances,
            key=lambda z: abs(close - float(z["center"])),
            default=None,
        )

        if nearest_support:
            level = float(nearest_support["center"])
            distance = abs(close - level)
            if distance <= 0.5 * float(atr) and s.get("rejection"):
                entry = close
                sl = level - 0.75 * float(atr)
                tp1 = close + 1.5 * float(atr)
                tp2 = close + 2.5 * float(atr)
                return StrategySetup(
                    strategy=self.name,
                    direction="LONG",
                    state="TRIGGERED",
                    entry=entry,
                    invalidation=sl,
                    target_1=tp1,
                    target_2=tp2,
                    risk_reward=self.rr(entry, sl, tp1),
                    confidence=68,
                    evidence=["Price near support zone", "Recent rejection detected"],
                    metadata={"level": level},
                    wait_for=["Confirmation above rejection candle"],
                )

        if nearest_resistance:
            level = float(nearest_resistance["center"])
            distance = abs(close - level)
            if distance <= 0.5 * float(atr) and s.get("rejection"):
                entry = close
                sl = level + 0.75 * float(atr)
                tp1 = close - 1.5 * float(atr)
                tp2 = close - 2.5 * float(atr)
                return StrategySetup(
                    strategy=self.name,
                    direction="SHORT",
                    state="TRIGGERED",
                    entry=entry,
                    invalidation=sl,
                    target_1=tp1,
                    target_2=tp2,
                    risk_reward=self.rr(entry, sl, tp1),
                    confidence=68,
                    evidence=["Price near resistance zone", "Recent rejection detected"],
                    metadata={"level": level},
                    wait_for=["Confirmation below rejection candle"],
                )

        return StrategySetup(
            strategy=self.name,
            direction="NONE",
            state="WATCH",
            confidence=25,
            wait_for=["Price reaches a meaningful S/R zone", "Clear rejection"],
        )
