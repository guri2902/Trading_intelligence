from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Any

from .scoring import score_backtest


@dataclass(frozen=True)
class OptimizationResult:
    parameter_set: dict[str, Any]
    objective: float
    metrics: dict
    score: dict


class OptunaOptimizer:
    """
    Optional Optuna wrapper.

    The objective receives a parameter dictionary and must return a backtest
    result object with `.metrics`.

    The optimizer only searches; it does not promote parameters.
    """

    def __init__(self, seed: int = 42):
        self.seed = seed

    def optimize(
        self,
        *,
        objective_fn: Callable[[dict[str, Any]], Any],
        search_space: dict[str, tuple],
        n_trials: int = 30,
        direction: str = "maximize",
    ) -> list[OptimizationResult]:
        try:
            import optuna
        except ImportError as exc:
            raise RuntimeError(
                "Optuna is not installed. Add optuna to the environment before optimization."
            ) from exc

        sampler = optuna.samplers.TPESampler(seed=self.seed)
        study = optuna.create_study(
            direction=direction,
            sampler=sampler,
        )

        trial_results: dict[int, tuple[dict, Any]] = {}

        def objective(trial):
            params = {}

            for name, spec in search_space.items():
                kind = spec[0]
                if kind == "int":
                    params[name] = trial.suggest_int(
                        name, spec[1], spec[2], step=spec[3] if len(spec) > 3 else 1
                    )
                elif kind == "float":
                    params[name] = trial.suggest_float(
                        name,
                        spec[1],
                        spec[2],
                        step=spec[3] if len(spec) > 3 and spec[3] else None,
                        log=spec[4] if len(spec) > 4 else False,
                    )
                elif kind == "categorical":
                    params[name] = trial.suggest_categorical(
                        name,
                        spec[1],
                    )
                else:
                    raise ValueError(f"Unknown search-space type: {kind}")

            result = objective_fn(params)
            score = score_backtest(result.metrics)
            trial_results[trial.number] = (params, result)
            return score.total

        study.optimize(objective, n_trials=n_trials)

        output = []
        for number, (params, result) in trial_results.items():
            score = score_backtest(result.metrics)
            output.append(
                OptimizationResult(
                    parameter_set=params,
                    objective=float(study.trials[number].value or 0.0),
                    metrics=result.metrics.model_dump(mode="json"),
                    score={
                        "total": score.total,
                        "passed": score.passed,
                        "reasons": score.reasons,
                        "components": score.components,
                    },
                )
            )

        output.sort(key=lambda x: x.objective, reverse=(direction == "maximize"))
        return output
