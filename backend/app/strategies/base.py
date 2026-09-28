from __future__ import annotations

from abc import ABC, abstractmethod

from .models import StrategyContext, StrategySetup


class Strategy(ABC):
    name: str

    @abstractmethod
    def evaluate(self, context: StrategyContext) -> StrategySetup:
        raise NotImplementedError

    @staticmethod
    def rr(entry: float | None, invalidation: float | None, target: float | None) -> float | None:
        if None in (entry, invalidation, target):
            return None
        risk = abs(entry - invalidation)
        reward = abs(target - entry)
        if risk <= 0:
            return None
        return reward / risk

    @staticmethod
    def latest_body(candles: list[dict]) -> tuple[float, float, float, float]:
        row = candles[-1]
        return (
            float(row["open"]),
            float(row["high"]),
            float(row["low"]),
            float(row["close"]),
        )
