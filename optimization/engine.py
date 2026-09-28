
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence
import math
import random


@dataclass(frozen=True)
class OptimizationObjective:
    pnl_weight: float = 1.0
    expectancy_weight: float = 1.0
    profit_factor_weight: float = 1.0
    sharpe_weight: float = 0.5
    sortino_weight: float = 0.5
    drawdown_weight: float = 1.0
    consistency_weight: float = 0.5
    min_trades: int = 5
    max_drawdown_pct: Optional[float] = None


@dataclass
class TrialResult:
    trial_number: int
    params: Dict[str, Any]
    objective: float
    metrics: Dict[str, float]
    feasible: bool
    reason: str = ""
    pruned: bool = False


@dataclass
class OptimizationReport:
    best: Optional[TrialResult]
    trials: List[TrialResult] = field(default_factory=list)
    objective_name: str = "risk_adjusted_score"


class StrategyOptimizer:
    """
    Provider-independent optimization wrapper.

    The evaluator receives a parameter mapping and must return a metric mapping.
    This keeps the optimization layer agnostic to the Phase 22 backtester and
    prevents the optimizer from inventing market data.
    """

    def __init__(self, evaluator: Callable[[Mapping[str, Any]], Mapping[str, Any]],
                 search_space: Mapping[str, Sequence[Any]],
                 objective: Optional[OptimizationObjective] = None,
                 seed: int = 42):
        self.evaluator = evaluator
        self.search_space = dict(search_space)
        self.objective = objective or OptimizationObjective()
        self.random = random.Random(seed)

    @staticmethod
    def _num(metrics: Mapping[str, Any], *keys: str, default: float = 0.0) -> float:
        for key in keys:
            value = metrics.get(key)
            if isinstance(value, (int, float)) and math.isfinite(float(value)):
                return float(value)
        return default

    def score(self, metrics: Mapping[str, Any]) -> tuple[float, bool, str]:
        trades = int(self._num(metrics, "trades", "trade_count"))
        dd = abs(self._num(metrics, "max_drawdown_pct", "drawdown_pct"))
        if trades < self.objective.min_trades:
            return float("-inf"), False, f"min_trades:{trades}<{self.objective.min_trades}"
        if self.objective.max_drawdown_pct is not None and dd > self.objective.max_drawdown_pct:
            return float("-inf"), False, f"max_drawdown:{dd}>{self.objective.max_drawdown_pct}"

        pnl = self._num(metrics, "net_pnl", "pnl")
        expectancy = self._num(metrics, "expectancy")
        pf = self._num(metrics, "profit_factor")
        sharpe = self._num(metrics, "sharpe")
        sortino = self._num(metrics, "sortino")
        consistency = self._num(metrics, "consistency", "win_day_ratio")

        # Profit factor is capped so one pathological value cannot dominate.
        pf_component = min(max(pf, 0.0), 5.0)
        penalty_dd = dd * self.objective.drawdown_weight
        raw = (
            pnl * self.objective.pnl_weight
            + expectancy * self.objective.expectancy_weight
            + pf_component * self.objective.profit_factor_weight
            + sharpe * self.objective.sharpe_weight
            + sortino * self.objective.sortino_weight
            + consistency * self.objective.consistency_weight
            - penalty_dd
        )
        return float(raw), True, ""

    def _sample_params(self) -> Dict[str, Any]:
        return {k: self.random.choice(list(v)) for k, v in self.search_space.items()}

    def run(self, n_trials: int = 20) -> OptimizationReport:
        if n_trials < 1:
            raise ValueError("n_trials must be >= 1")
        if not self.search_space:
            raise ValueError("search_space cannot be empty")

        results: List[TrialResult] = []
        for i in range(n_trials):
            params = self._sample_params()
            try:
                metrics = dict(self.evaluator(params))
                score, feasible, reason = self.score(metrics)
                results.append(TrialResult(i, params, score, {
                    k: float(v) for k, v in metrics.items()
                    if isinstance(v, (int, float)) and math.isfinite(float(v))
                }, feasible, reason))
            except Exception as exc:
                results.append(TrialResult(
                    i, params, float("-inf"), {}, False, f"evaluator_error:{type(exc).__name__}"
                ))
        feasible = [r for r in results if r.feasible and not r.pruned]
        best = max(feasible, key=lambda r: r.objective) if feasible else None
        return OptimizationReport(best=best, trials=results)
