from __future__ import annotations

from .base import Strategy
from .models import StrategyContext, StrategySetup


class VolatilityBreakoutStrategy(Strategy):
    name = "VOLATILITY_BREAKOUT"

    def evaluate(self, context: StrategyContext) -> StrategySetup:
        f = context.features
        s = context.structure
        close = float(f["price"])
        atr = f.get("atr_14")
        day_high = f.get("day_high")
        day_low = f.get("day_low")
        rv = f.get("relative_volume_20")

        if None in (atr, day_high, day_low):
            return StrategySetup(
                strategy=self.name,
                direction="NONE",
                state="NO_SETUP",
                wait_for=["ATR and day range"],
            )

        # Require a structural breakout state plus participation.
        if s.get("regime") == "BREAKOUT" and close >= float(day_high) * 0.999:
            entry = close
            sl = close - float(atr)
            tp1 = close + 2.0 * float(atr)
            tp2 = close + 3.25 * float(atr)
            confidence = 74 if rv is None or rv >= 1.2 else 60
            return StrategySetup(
                strategy=self.name,
                direction="LONG",
                state="TRIGGERED",
                entry=entry,
                invalidation=sl,
                target_1=tp1,
                target_2=tp2,
                risk_reward=self.rr(entry, sl, tp1),
                confidence=confidence,
                evidence=["Structural breakout", "Price at/near day high"],
                wait_for=["Volume confirmation"],
            )

        if s.get("regime") == "BREAKDOWN" and close <= float(day_low) * 1.001:
            entry = close
            sl = close + float(atr)
            tp1 = close - 2.0 * float(atr)
            tp2 = close - 3.25 * float(atr)
            confidence = 74 if rv is None or rv >= 1.2 else 60
            return StrategySetup(
                strategy=self.name,
                direction="SHORT",
                state="TRIGGERED",
                entry=entry,
                invalidation=sl,
                target_1=tp1,
                target_2=tp2,
                risk_reward=self.rr(entry, sl, tp1),
                confidence=confidence,
                evidence=["Structural breakdown", "Price at/near day low"],
                wait_for=["Volume confirmation"],
            )

        return StrategySetup(
            strategy=self.name,
            direction="NONE",
            state="WATCH",
            confidence=20,
            wait_for=["Confirmed volatility expansion", "Structural breakout/breakdown"],
        )
