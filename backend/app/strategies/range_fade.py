from __future__ import annotations

from .base import Strategy
from .models import StrategyContext, StrategySetup


class RangeFadeStrategy(Strategy):
    name = "RANGE_FADE"

    def evaluate(self, context: StrategyContext) -> StrategySetup:
        f = context.features
        s = context.structure
        close = float(f["price"])
        atr = f.get("atr_14")

        if s.get("trend") != "RANGE" or atr is None:
            return StrategySetup(
                strategy=self.name,
                direction="NONE",
                state="INVALID",
                confidence=15,
                invalidation_reasons=["Market is not classified as range"],
            )

        supports = s.get("support_zones", [])
        resistances = s.get("resistance_zones", [])

        if not supports or not resistances:
            return StrategySetup(
                strategy=self.name,
                direction="NONE",
                state="WATCH",
                confidence=20,
                wait_for=["Both range boundaries"],
            )

        support = float(supports[0]["center"])
        resistance = float(resistances[0]["center"])

        if resistance <= support:
            return StrategySetup(
                strategy=self.name,
                direction="NONE",
                state="INVALID",
                invalidation_reasons=["Invalid range geometry"],
            )

        width = resistance - support

        if abs(close - support) <= 0.15 * width:
            entry = close
            sl = support - 0.35 * float(atr)
            tp1 = support + 0.50 * width
            tp2 = resistance - 0.15 * width
            return StrategySetup(
                strategy=self.name,
                direction="LONG",
                state="TRIGGERED",
                entry=entry,
                invalidation=sl,
                target_1=tp1,
                target_2=tp2,
                risk_reward=self.rr(entry, sl, tp1),
                confidence=61,
                evidence=["Range regime", "Price near lower boundary"],
                metadata={"support": support, "resistance": resistance},
            )

        if abs(resistance - close) <= 0.15 * width:
            entry = close
            sl = resistance + 0.35 * float(atr)
            tp1 = resistance - 0.50 * width
            tp2 = support + 0.15 * width
            return StrategySetup(
                strategy=self.name,
                direction="SHORT",
                state="TRIGGERED",
                entry=entry,
                invalidation=sl,
                target_1=tp1,
                target_2=tp2,
                risk_reward=self.rr(entry, sl, tp1),
                confidence=61,
                evidence=["Range regime", "Price near upper boundary"],
                metadata={"support": support, "resistance": resistance},
            )

        return StrategySetup(
            strategy=self.name,
            direction="NONE",
            state="WATCH",
            confidence=25,
            metadata={"support": support, "resistance": resistance},
            wait_for=["Price approaches range boundary"],
        )
