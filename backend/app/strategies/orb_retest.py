from __future__ import annotations

from .base import Strategy
from .models import StrategyContext, StrategySetup


class ORBRetestStrategy(Strategy):
    name = "ORB_RETEST"

    def __init__(self, opening_bars: int = 3, retest_bars: int = 3):
        self.opening_bars = opening_bars
        self.retest_bars = retest_bars

    def evaluate(self, context: StrategyContext) -> StrategySetup:
        candles = context.candles
        f = context.features

        if len(candles) < self.opening_bars + self.retest_bars + 1:
            return StrategySetup(
                strategy=self.name,
                direction="NONE",
                state="NO_SETUP",
                wait_for=["Opening range + retest candles"],
            )

        from datetime import datetime
        latest_ts = candles[-1].get("timestamp")
        if isinstance(latest_ts, str):
            latest_ts = datetime.fromisoformat(latest_ts.replace("Z", "+00:00"))
        session_date = latest_ts.date() if hasattr(latest_ts, "date") else None
        session_candles = []
        for item in candles:
            ts = item.get("timestamp")
            if isinstance(ts, str):
                ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            if session_date is None or ts.date() == session_date:
                session_candles.append(item)
        if len(session_candles) < self.opening_bars + self.retest_bars + 1:
            return StrategySetup(
                strategy=self.name,
                direction="NONE",
                state="NO_SETUP",
                wait_for=["Current-session opening range + retest candles"],
            )
        opening = session_candles[:self.opening_bars]
        hi = max(float(x["high"]) for x in opening)
        lo = min(float(x["low"]) for x in opening)
        recent = session_candles[-self.retest_bars:]
        close = float(recent[-1]["close"])
        atr = f.get("atr_14")

        if atr is None:
            return StrategySetup(
                strategy=self.name,
                direction="NONE",
                state="NO_SETUP",
                wait_for=["ATR"],
            )

        touched_high = any(float(x["low"]) <= hi <= float(x["high"]) for x in recent)
        touched_low = any(float(x["low"]) <= lo <= float(x["high"]) for x in recent)

        if context.structure.get("regime") in {"BREAKOUT", "TREND"} and touched_high and close > hi:
            entry = close
            sl = hi - 0.5 * float(atr)
            tp1 = entry + 1.5 * float(atr)
            tp2 = entry + 2.5 * float(atr)
            return StrategySetup(
                strategy=self.name,
                direction="LONG",
                state="TRIGGERED",
                entry=entry,
                invalidation=sl,
                target_1=tp1,
                target_2=tp2,
                risk_reward=self.rr(entry, sl, tp1),
                confidence=75,
                evidence=["Opening-range high retested and held"],
                metadata={"opening_range_high": hi, "opening_range_low": lo},
            )

        if context.structure.get("regime") in {"BREAKDOWN", "TREND"} and touched_low and close < lo:
            entry = close
            sl = lo + 0.5 * float(atr)
            tp1 = entry - 1.5 * float(atr)
            tp2 = entry - 2.5 * float(atr)
            return StrategySetup(
                strategy=self.name,
                direction="SHORT",
                state="TRIGGERED",
                entry=entry,
                invalidation=sl,
                target_1=tp1,
                target_2=tp2,
                risk_reward=self.rr(entry, sl, tp1),
                confidence=75,
                evidence=["Opening-range low retested and held"],
                metadata={"opening_range_high": hi, "opening_range_low": lo},
            )

        return StrategySetup(
            strategy=self.name,
            direction="NONE",
            state="WATCH",
            confidence=35,
            metadata={"opening_range_high": hi, "opening_range_low": lo},
            wait_for=["Valid breakout", "Retest of broken range edge"],
        )
