from __future__ import annotations

from datetime import datetime

from ..backtest.engine import BacktestEngine
from ..backtest.models import BacktestConfig, CostConfig
from ..backtest.strategy_adapter import StrategyBacktestAdapter
from ..features.service import FeatureService
from ..structure.service import StructureService
from ..strategies.models import StrategyContext
from ..strategies.service import StrategyService
from ..strategies.custom_rules import evaluate_conditions
from .models import BUILT_IN_STRATEGIES, StrategyBacktestRequest, StrategyDefinition


def _normalize_rows(rows: list[dict]) -> list[dict]:
    normalized = []
    for row in rows:
        item = dict(row)
        ts = item.get("timestamp")
        if ts is None:
            raise ValueError("Every historical row must contain timestamp")
        if isinstance(ts, str):
            item["timestamp"] = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        normalized.append(item)
    normalized.sort(key=lambda x: x["timestamp"])
    return normalized


def _build_context(history: list[dict]) -> StrategyContext:
    features = FeatureService().calculate(history, session_ids=None)
    structure = StructureService().analyze(history)
    return StrategyContext(
        timestamp=history[-1]["timestamp"],
        candles=history,
        features=features,
        structure=structure,
        options=None,
        regime=structure.get("regime"),
    )


def backtest_saved_strategy(strategy: StrategyDefinition, request: StrategyBacktestRequest):
    rows = _normalize_rows(request.rows)
    service = StrategyService()

    # Existing deterministic engine strategies remain the default execution path.
    engine_strategy = (strategy.engine_strategy or "").upper().strip()

    if engine_strategy in BUILT_IN_STRATEGIES:
        adapter = StrategyBacktestAdapter(
            state_fn=_build_context,
            preferred_strategy=engine_strategy,
        )

        def signal_fn(history):
            if len(history) < 15:
                return None
            return adapter.signal(history)

        exit_fn = None
    elif not engine_strategy:
        # User-defined conditions execute through the existing StrategyEngine layer.
        trade_days: dict[str, int] = {}

        def signal_fn(history):
            if len(history) < 15:
                return None
            context = _build_context(history)
            result = service.evaluate(context, custom_strategy=strategy)
            setup = next(
                (x for x in result.setups if x.strategy == strategy.name and x.state == "TRIGGERED"),
                None,
            )
            if setup is None:
                return None

            day_key = str(context.timestamp.date())
            used = trade_days.get(day_key, 0)
            if used >= strategy.rules.max_trades_per_day:
                return None
            trade_days[day_key] = used + 1

            return {
                "strategy": strategy.name,
                "direction": setup.direction,
                "entry": setup.entry,
                "invalidation": setup.invalidation,
                "target_1": setup.target_1,
                "target_2": setup.target_2,
            }

        def exit_fn(history, signal, row):
            if not strategy.rules.exit_conditions:
                return False
            context = _build_context(history)
            return evaluate_conditions(
                context,
                strategy.rules.exit_conditions,
                logic=strategy.rules.condition_logic,
            )
    else:
        raise ValueError(
            "STRATEGY_EXECUTOR_NOT_CONFIGURED: engine_strategy must be a supported "
            "deterministic strategy or omitted so Strategy Studio rules are used."
        )

    config = BacktestConfig(
        initial_capital=request.initial_capital,
        quantity=request.quantity,
        max_concurrent_positions=1,
        allow_short=True,
        costs=CostConfig(
            slippage_bps=request.slippage_bps,
            latency_bars=request.latency_bars,
        ),
    )

    return BacktestEngine().run(
        rows,
        signal_fn,
        strategy_name=strategy.name,
        config=config,
        mode="UNDERLYING",
        exit_fn=exit_fn,
    )
