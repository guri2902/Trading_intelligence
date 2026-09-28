from __future__ import annotations

from .base import Strategy
from .models import StrategyContext, StrategySetup


class VWAPPullbackStrategy(Strategy):
    name = "VWAP_PULLBACK"

    def evaluate(self, context: StrategyContext) -> StrategySetup:
        f = context.features
        close = float(f["price"])
        vwap = f.get("vwap")
        atr = f.get("atr_14")

        if vwap is None or atr is None:
            return StrategySetup(
                strategy=self.name,
                direction="NONE",
                state="NO_SETUP",
                confidence=0,
                wait_for=["VWAP and ATR"],
            )

        trend = context.structure.get("trend", "RANGE")
        distance = abs(close - float(vwap))

        if trend == "BULLISH" and close >= float(vwap) and distance <= 0.35 * float(atr):
            entry = close
            sl = min(close - float(atr), float(vwap) - 0.25 * float(atr))
            tp1 = close + 1.5 * float(atr)
            tp2 = close + 2.5 * float(atr)
            rr = self.rr(entry, sl, tp1)
            return StrategySetup(
                strategy=self.name,
                direction="LONG",
                state="TRIGGERED",
                entry=entry,
                invalidation=sl,
                target_1=tp1,
                target_2=tp2,
                risk_reward=rr,
                confidence=72 if rr and rr >= 1.5 else 58,
                evidence=[
                    "Bullish structure",
                    "Price is near/above VWAP",
                    "ATR provides measurable risk distance",
                ],
                wait_for=["Confirm hold above VWAP"],
            )

        if trend == "BEARISH" and close <= float(vwap) and distance <= 0.35 * float(atr):
            entry = close
            sl = max(close + float(atr), float(vwap) + 0.25 * float(atr))
            tp1 = close - 1.5 * float(atr)
            tp2 = close - 2.5 * float(atr)
            rr = self.rr(entry, sl, tp1)
            return StrategySetup(
                strategy=self.name,
                direction="SHORT",
                state="TRIGGERED",
                entry=entry,
                invalidation=sl,
                target_1=tp1,
                target_2=tp2,
                risk_reward=rr,
                confidence=72 if rr and rr >= 1.5 else 58,
                evidence=[
                    "Bearish structure",
                    "Price is near/below VWAP",
                    "ATR provides measurable risk distance",
                ],
                wait_for=["Confirm rejection below VWAP"],
            )

        return StrategySetup(
            strategy=self.name,
            direction="NONE",
            state="WATCH",
            confidence=25,
            evidence=["No clean VWAP pullback trigger"],
            wait_for=[
                "Trend alignment",
                "Price return near VWAP",
                "Confirmation candle",
            ],
        )
