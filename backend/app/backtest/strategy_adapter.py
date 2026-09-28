from __future__ import annotations

from ..strategies.custom_rules import CustomRuleStrategy
from ..strategies.ema_continuation import EMAContinuationStrategy
from ..strategies.momentum import MomentumContinuationStrategy
from ..strategies.option_specific import OptionSpecificStrategy
from ..strategies.orb import ORBStrategy
from ..strategies.orb_retest import ORBRetestStrategy
from ..strategies.range_fade import RangeFadeStrategy
from ..strategies.sr_rejection import SRRejectionStrategy
from ..strategies.volatility_breakout import VolatilityBreakoutStrategy
from ..strategies.vwap_pullback import VWAPPullbackStrategy
from ..strategies.service import StrategyService


class StrategyBacktestAdapter:
    """Bridge strategy logic into the historical-options backtester.

    For a deterministic preferred strategy, only that strategy is evaluated.
    The original adapter ultimately selected that same preferred setup, so
    evaluating unrelated strategies was wasted CPU. Unknown/custom names use
    the original full StrategyService behavior.
    """

    def __init__(self, state_fn, preferred_strategy: str | None = None):
        self.state_fn = state_fn
        self.preferred_strategy = preferred_strategy
        self.service = StrategyService()
        strategy_objects = [
            VWAPPullbackStrategy(), EMAContinuationStrategy(), ORBStrategy(),
            ORBRetestStrategy(), SRRejectionStrategy(), RangeFadeStrategy(),
            MomentumContinuationStrategy(), VolatilityBreakoutStrategy(),
            OptionSpecificStrategy(),
        ]
        self._strategy_by_name = {str(s.name).upper(): s for s in strategy_objects}

    def signal(self, history: list[dict]) -> dict | None:
        context = self.state_fn(history)
        preferred = str(self.preferred_strategy).upper().strip() if self.preferred_strategy else ""
        selected = self._strategy_by_name.get(preferred)
        if selected is not None:
            try:
                setup = selected.evaluate(context)
            except Exception:
                return None
            if setup is None or setup.state != "TRIGGERED":
                return None
            return {
                "strategy": setup.strategy, "direction": setup.direction,
                "entry": setup.entry, "invalidation": setup.invalidation,
                "target_1": setup.target_1, "target_2": setup.target_2,
            }

        result = self.service.evaluate(context)
        setup = result.best_setup
        if preferred:
            matches = [x for x in result.setups if x.strategy == self.preferred_strategy and x.state == "TRIGGERED"]
            setup = matches[0] if matches else None
        if setup is None or setup.state != "TRIGGERED":
            return None
        return {
            "strategy": setup.strategy, "direction": setup.direction,
            "entry": setup.entry, "invalidation": setup.invalidation,
            "target_1": setup.target_1, "target_2": setup.target_2,
        }
