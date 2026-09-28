from __future__ import annotations

from datetime import datetime
from typing import Any

from .models import StrategyContext, StrategySetup


_SUPPORTED_OPERATORS = {
    "GT",
    "GTE",
    "LT",
    "LTE",
    "EQ",
    "NE",
    "CROSSES_ABOVE",
    "CROSSES_BELOW",
}


def _coerce(value: Any) -> Any:
    if isinstance(value, bool) or value is None:
        return value
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip()
        try:
            return float(text)
        except ValueError:
            return text
    return value


def _resolve_path(context: StrategyContext, path: str) -> Any:
    key = path.strip()
    if not key:
        return None

    # Common aliases keep the builder easy to use.
    if key in context.features:
        return context.features.get(key)

    if key.startswith("features."):
        return context.features.get(key.split(".", 1)[1])

    if key in context.structure:
        return context.structure.get(key)

    if key.startswith("structure."):
        return context.structure.get(key.split(".", 1)[1])

    if key.startswith("candle."):
        return context.candles[-1].get(key.split(".", 1)[1]) if context.candles else None

    if key in {"open", "high", "low", "close", "volume"}:
        return context.candles[-1].get(key) if context.candles else None

    if key == "regime":
        return context.regime

    if key == "timestamp":
        return context.timestamp

    return None


def _resolve_previous(context: StrategyContext, path: str) -> Any:
    if len(context.candles) < 2:
        return None

    # Candle-native previous values are available without rebuilding indicators.
    if path.startswith("candle."):
        return context.candles[-2].get(path.split(".", 1)[1])
    if path in {"open", "high", "low", "close", "volume"}:
        return context.candles[-2].get(path)

    # For indicator/feature crosses, rebuild the feature snapshot on the prior bar.
    try:
        from ..features.service import FeatureService

        features = FeatureService().calculate(context.candles[:-1], session_ids=None)
        if path in features:
            return features.get(path)
        if path.startswith("features."):
            return features.get(path.split(".", 1)[1])
    except Exception:
        return None
    return None


def evaluate_condition(context: StrategyContext, condition) -> bool:
    operator = condition.operator
    if operator not in _SUPPORTED_OPERATORS:
        raise ValueError(f"Unsupported condition operator: {operator}")

    lhs = _coerce(_resolve_path(context, condition.field))
    rhs = _coerce(condition.value)

    if lhs is None:
        return False

    if operator in {"GT", "GTE", "LT", "LTE", "CROSSES_ABOVE", "CROSSES_BELOW"}:
        try:
            lhs_n = float(lhs)
            rhs_n = float(rhs)
        except (TypeError, ValueError):
            return False

        if operator == "GT":
            return lhs_n > rhs_n
        if operator == "GTE":
            return lhs_n >= rhs_n
        if operator == "LT":
            return lhs_n < rhs_n
        if operator == "LTE":
            return lhs_n <= rhs_n

        previous = _resolve_previous(context, condition.field)
        if previous is None:
            return False
        try:
            previous_n = float(previous)
        except (TypeError, ValueError):
            return False
        if operator == "CROSSES_ABOVE":
            return previous_n <= rhs_n and lhs_n > rhs_n
        return previous_n >= rhs_n and lhs_n < rhs_n

    if operator == "EQ":
        return lhs == rhs or str(lhs) == str(rhs)
    if operator == "NE":
        return not (lhs == rhs or str(lhs) == str(rhs))
    return False


def evaluate_conditions(context: StrategyContext, conditions, *, logic: str = "ALL") -> bool:
    if not conditions:
        return True
    results = [evaluate_condition(context, item) for item in conditions]
    return all(results) if logic == "ALL" else any(results)


def _direction(rules, context: StrategyContext) -> str:
    if rules.direction in {"LONG", "SHORT"}:
        return rules.direction
    if rules.option_action == "BUY_CE":
        return "LONG"
    if rules.option_action == "BUY_PE":
        return "SHORT"

    alignment = context.features.get("ema_alignment")
    if alignment == "BULLISH":
        return "LONG"
    if alignment == "BEARISH":
        return "SHORT"
    return "NONE"


def _build_levels(rules, context: StrategyContext, direction: str) -> tuple[float, float, float]:
    entry = float(context.features["price"])
    atr = context.features.get("atr_14")
    atr = float(atr) if atr is not None else None

    if rules.stop_mode == "POINTS":
        stop_distance = float(rules.stop_value)
    elif rules.stop_mode == "PERCENT":
        stop_distance = entry * float(rules.stop_value) / 100.0
    elif rules.stop_mode == "ATR":
        if atr is None or atr <= 0:
            raise ValueError("ATR is required for ATR stop mode")
        stop_distance = atr * float(rules.stop_value)
    else:
        raise ValueError(f"Unsupported stop_mode: {rules.stop_mode}")

    if rules.target_mode == "POINTS":
        target_distance = float(rules.target_value)
    elif rules.target_mode == "PERCENT":
        target_distance = entry * float(rules.target_value) / 100.0
    elif rules.target_mode == "ATR":
        if atr is None or atr <= 0:
            raise ValueError("ATR is required for ATR target mode")
        target_distance = atr * float(rules.target_value)
    elif rules.target_mode == "RR":
        target_distance = stop_distance * float(rules.target_value)
    else:
        raise ValueError(f"Unsupported target_mode: {rules.target_mode}")

    if stop_distance <= 0 or target_distance <= 0:
        raise ValueError("Stop and target distances must be positive")

    if direction == "LONG":
        return entry, entry - stop_distance, entry + target_distance
    return entry, entry + stop_distance, entry - target_distance


class CustomRuleStrategy:
    """
    Executes a saved Strategy Studio condition definition through the existing
    StrategyEngine contract. It does not create a second strategy engine.
    """

    def __init__(self, definition):
        self.definition = definition
        self.rules = definition.rules
        self.name = definition.name

    def evaluate(self, context: StrategyContext) -> StrategySetup:
        passed = evaluate_conditions(
            context,
            self.rules.entry_conditions,
            logic=self.rules.condition_logic,
        )
        if not passed:
            return StrategySetup(
                strategy=self.name,
                direction="NONE",
                state="WATCH",
                confidence=0,
                wait_for=["Entry conditions"],
            )

        direction = _direction(self.rules, context)
        if direction == "NONE":
            return StrategySetup(
                strategy=self.name,
                direction="NONE",
                state="NO_SETUP",
                confidence=0,
                invalidation_reasons=["Direction could not be resolved from rules/context"],
            )

        entry, stop, target = _build_levels(self.rules, context, direction)
        rr = abs(target - entry) / abs(entry - stop) if entry != stop else None

        return StrategySetup(
            strategy=self.name,
            direction=direction,
            state="TRIGGERED",
            entry=entry,
            invalidation=stop,
            target_1=target,
            target_2=target,
            risk_reward=rr,
            confidence=70,
            evidence=[
                f"Custom conditions: {self.rules.condition_logic}",
                "Strategy Studio rule match",
            ],
            metadata={
                "source": self.definition.source,
                "strategy_id": self.definition.id,
                "option_action": self.rules.option_action,
            },
        )
