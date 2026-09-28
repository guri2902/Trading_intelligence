from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class ResearchScore:
    total: float
    components: dict[str, float]
    passed: bool
    reasons: list[str]


def safe_metric(value, default=0.0) -> float:
    if value is None:
        return default
    try:
        x = float(value)
        return x if math.isfinite(x) else default
    except (TypeError, ValueError):
        return default


def score_backtest(
    metrics,
    *,
    min_trades: int = 30,
    max_drawdown_pct: float = 20.0,
    min_profit_factor: float = 1.1,
    min_expectancy: float = 0.0,
    min_oos_return_pct: float | None = None,
) -> ResearchScore:
    reasons = []
    components = {}

    trades = int(getattr(metrics, "total_trades", 0))
    pf = safe_metric(getattr(metrics, "profit_factor", None))
    expectancy = safe_metric(getattr(metrics, "expectancy_per_trade", None))
    sharpe = safe_metric(getattr(metrics, "sharpe", None))
    sortino = safe_metric(getattr(metrics, "sortino", None))
    dd = safe_metric(getattr(metrics, "max_drawdown_pct", None))
    ret = safe_metric(getattr(metrics, "return_pct", None))
    win_rate = safe_metric(getattr(metrics, "win_rate_pct", None))

    components["profit_factor"] = min(max((pf - 1.0) * 25.0, 0.0), 25.0)
    components["expectancy"] = min(max(expectancy, 0.0), 20.0)
    components["sharpe"] = min(max(sharpe * 8.0, 0.0), 15.0)
    components["sortino"] = min(max(sortino * 8.0, 0.0), 15.0)
    components["return"] = min(max(ret / 2.0, 0.0), 10.0)
    components["win_rate"] = min(max((win_rate - 40.0) / 2.0, 0.0), 10.0)
    components["drawdown"] = max(0.0, 10.0 - dd * 0.5)

    if trades < min_trades:
        reasons.append(f"too_few_trades:{trades}<{min_trades}")

    if pf < min_profit_factor:
        reasons.append(f"profit_factor_below_threshold:{pf:.3f}")

    if expectancy <= min_expectancy:
        reasons.append(f"non_positive_expectancy:{expectancy:.4f}")

    if dd > max_drawdown_pct:
        reasons.append(f"drawdown_too_high:{dd:.2f}%")

    if min_oos_return_pct is not None and ret < min_oos_return_pct:
        reasons.append(
            f"oos_return_below_threshold:{ret:.2f}%<{min_oos_return_pct:.2f}%"
        )

    total = sum(components.values())

    return ResearchScore(
        total=round(total, 4),
        components={k: round(v, 4) for k, v in components.items()},
        passed=not reasons,
        reasons=reasons,
    )
