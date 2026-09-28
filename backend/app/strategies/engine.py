from __future__ import annotations

from .custom_rules import CustomRuleStrategy
from .ema_continuation import EMAContinuationStrategy
from .momentum import MomentumContinuationStrategy
from .models import StrategyBatchResult, StrategyContext, StrategySetup
from .option_specific import OptionSpecificStrategy
from .orb import ORBStrategy
from .orb_retest import ORBRetestStrategy
from .range_fade import RangeFadeStrategy
from .sr_rejection import SRRejectionStrategy
from .volatility_breakout import VolatilityBreakoutStrategy
from .vwap_pullback import VWAPPullbackStrategy


class StrategyEngine:
    def __init__(self):
        self.strategies = [
            VWAPPullbackStrategy(),
            EMAContinuationStrategy(),
            ORBStrategy(),
            ORBRetestStrategy(),
            SRRejectionStrategy(),
            RangeFadeStrategy(),
            MomentumContinuationStrategy(),
            VolatilityBreakoutStrategy(),
            OptionSpecificStrategy(),
        ]

    def evaluate(self, context: StrategyContext, custom_strategy=None) -> StrategyBatchResult:
        setups: list[StrategySetup] = []

        for strategy in self.strategies:
            try:
                setups.append(strategy.evaluate(context))
            except Exception as exc:
                setups.append(
                    StrategySetup(
                        strategy=strategy.name,
                        direction="NONE",
                        state="NO_SETUP",
                        confidence=0,
                        invalidation_reasons=[f"Strategy error: {exc}"],
                    )
                )

        if custom_strategy is not None:
            try:
                setups.append(CustomRuleStrategy(custom_strategy).evaluate(context))
            except Exception as exc:
                name = getattr(custom_strategy, "name", "CUSTOM")
                setups.append(
                    StrategySetup(
                        strategy=name,
                        direction="NONE",
                        state="NO_SETUP",
                        confidence=0,
                        invalidation_reasons=[f"Custom strategy error: {exc}"],
                    )
                )

        triggered = [s for s in setups if s.state == "TRIGGERED"]
        triggered = sorted(
            triggered,
            key=lambda s: (
                s.risk_reward or 0.0,
                s.confidence,
            ),
            reverse=True,
        )

        best = triggered[0] if triggered else None

        return StrategyBatchResult(
            timestamp=context.timestamp,
            setups=setups,
            triggered_count=len(triggered),
            best_setup=best,
            regime=context.regime or context.structure.get("regime", "UNKNOWN"),
        )
