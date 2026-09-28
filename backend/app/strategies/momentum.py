from __future__ import annotations

from .base import Strategy
from .models import StrategyContext, StrategySetup


class MomentumContinuationStrategy(Strategy):
    name = "MOMENTUM_CONTINUATION"

    def evaluate(self, context: StrategyContext) -> StrategySetup:
        f = context.features
        s = context.structure
        close = float(f["price"])
        atr = f.get("atr_14")
        rv = f.get("relative_volume_20")
        mom = f.get("momentum_10")

        if None in (atr, mom):
            return StrategySetup(
                strategy=self.name,
                direction="NONE",
                state="NO_SETUP",
                wait_for=["ATR and momentum"],
            )

        volume_ok = rv is None or rv >= 1.2

        if (
            s.get("trend") == "BULLISH"
            and mom > 0
            and volume_ok
            and f.get("price_vs_vwap") == "ABOVE"
        ):
            entry = close
            sl = close - float(atr)
            tp1 = close + 1.8 * float(atr)
            tp2 = close + 3.0 * float(atr)
            return StrategySetup(
                strategy=self.name,
                direction="LONG",
                state="TRIGGERED",
                entry=entry,
                invalidation=sl,
                target_1=tp1,
                target_2=tp2,
                risk_reward=self.rr(entry, sl, tp1),
                confidence=69,
                evidence=["Bullish structure", "Positive momentum", "Price above VWAP"],
                wait_for=["Avoid late-stage exhaustion"],
            )

        if (
            s.get("trend") == "BEARISH"
            and mom < 0
            and volume_ok
            and f.get("price_vs_vwap") == "BELOW"
        ):
            entry = close
            sl = close + float(atr)
            tp1 = close - 1.8 * float(atr)
            tp2 = close - 3.0 * float(atr)
            return StrategySetup(
                strategy=self.name,
                direction="SHORT",
                state="TRIGGERED",
                entry=entry,
                invalidation=sl,
                target_1=tp1,
                target_2=tp2,
                risk_reward=self.rr(entry, sl, tp1),
                confidence=69,
                evidence=["Bearish structure", "Negative momentum", "Price below VWAP"],
                wait_for=["Avoid late-stage exhaustion"],
            )

        return StrategySetup(
            strategy=self.name,
            direction="NONE",
            state="WATCH",
            confidence=25,
            wait_for=["Momentum + structure alignment"],
        )
