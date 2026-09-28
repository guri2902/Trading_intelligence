from __future__ import annotations

from .base import Strategy
from .models import StrategyContext, StrategySetup


class EMAContinuationStrategy(Strategy):
    name = "EMA_CONTINUATION"

    def evaluate(self, context: StrategyContext) -> StrategySetup:
        f = context.features
        close = float(f["price"])
        e9, e20, e50 = f.get("ema_9"), f.get("ema_20"), f.get("ema_50")
        atr = f.get("atr_14")
        if None in (e9, e20, e50, atr):
            return StrategySetup(
                strategy=self.name,
                direction="NONE",
                state="NO_SETUP",
                confidence=0,
                wait_for=["EMA 9/20/50 and ATR"],
            )

        rsi = f.get("rsi_14")
        rv = f.get("relative_volume_20")
        rr = None

        if e9 > e20 > e50 and close > e9 and (rsi is None or 52 <= rsi <= 75):
            entry = close
            sl = min(float(e20), close - float(atr))
            tp1 = close + 1.75 * float(atr)
            tp2 = close + 3.0 * float(atr)
            rr = self.rr(entry, sl, tp1)
            confidence = 70
            if rv is not None and rv >= 1.2:
                confidence += 8
            return StrategySetup(
                strategy=self.name,
                direction="LONG",
                state="TRIGGERED",
                entry=entry,
                invalidation=sl,
                target_1=tp1,
                target_2=tp2,
                risk_reward=rr,
                confidence=min(confidence, 95),
                evidence=["EMA 9 > EMA 20 > EMA 50", "Price above EMA 9"],
                wait_for=["Avoid entry after excessive extension"],
            )

        if e9 < e20 < e50 and close < e9 and (rsi is None or 25 <= rsi <= 48):
            entry = close
            sl = max(float(e20), close + float(atr))
            tp1 = close - 1.75 * float(atr)
            tp2 = close - 3.0 * float(atr)
            rr = self.rr(entry, sl, tp1)
            confidence = 70
            if rv is not None and rv >= 1.2:
                confidence += 8
            return StrategySetup(
                strategy=self.name,
                direction="SHORT",
                state="TRIGGERED",
                entry=entry,
                invalidation=sl,
                target_1=tp1,
                target_2=tp2,
                risk_reward=rr,
                confidence=min(confidence, 95),
                evidence=["EMA 9 < EMA 20 < EMA 50", "Price below EMA 9"],
                wait_for=["Avoid entry after excessive extension"],
            )

        return StrategySetup(
            strategy=self.name,
            direction="NONE",
            state="WATCH",
            confidence=25,
            wait_for=["Clean EMA alignment", "Price confirmation"],
        )
