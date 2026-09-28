from __future__ import annotations

from .base import Strategy
from .models import StrategyContext, StrategySetup


class OptionSpecificStrategy(Strategy):
    name = "OPTION_DIRECTIONAL"

    def evaluate(self, context: StrategyContext) -> StrategySetup:
        options = context.options or {}
        debate = options.get("debate") or {}
        winner = debate.get("winner", "NO_TRADE")
        feature = context.features
        atr = feature.get("atr_14")
        price = feature.get("price")

        if atr is None or price is None:
            return StrategySetup(
                strategy=self.name,
                direction="NONE",
                state="NO_SETUP",
                wait_for=["Underlying ATR/price"],
            )

        if winner == "CE":
            return StrategySetup(
                strategy=self.name,
                direction="LONG",
                state="TRIGGERED",
                entry=float(price),
                invalidation=float(price) - float(atr),
                target_1=float(price) + 1.5 * float(atr),
                target_2=float(price) + 2.5 * float(atr),
                risk_reward=1.5,
                confidence=min(float(debate.get("ce_score", 0)), 95),
                evidence=["Options engine ranks CE stronger than PE"],
                metadata={
                    "trade_expression": "BUY_CE",
                    "option_candidate": options.get("best_ce"),
                },
                wait_for=["Underlying strategy confirmation", "Risk approval"],
            )

        if winner == "PE":
            return StrategySetup(
                strategy=self.name,
                direction="SHORT",
                state="TRIGGERED",
                entry=float(price),
                invalidation=float(price) + float(atr),
                target_1=float(price) - 1.5 * float(atr),
                target_2=float(price) - 2.5 * float(atr),
                risk_reward=1.5,
                confidence=min(float(debate.get("pe_score", 0)), 95),
                evidence=["Options engine ranks PE stronger than CE"],
                metadata={
                    "trade_expression": "BUY_PE",
                    "option_candidate": options.get("best_pe"),
                },
                wait_for=["Underlying strategy confirmation", "Risk approval"],
            )

        return StrategySetup(
            strategy=self.name,
            direction="NONE",
            state="WATCH",
            confidence=15,
            evidence=["Options engine did not produce a clear CE/PE winner"],
            wait_for=["Clear CE vs PE advantage"],
        )
