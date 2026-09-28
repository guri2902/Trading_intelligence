from __future__ import annotations

from dataclasses import asdict, dataclass
from math import isfinite
from typing import Any


@dataclass(frozen=True)
class QualityConfig:
    # Component weights. They intentionally sum to 100.
    backtest_weight: float = 15.0
    oos_weight: float = 25.0
    robustness_weight: float = 20.0
    regime_weight: float = 15.0
    drawdown_weight: float = 10.0
    consistency_weight: float = 10.0
    trade_count_weight: float = 5.0

    a_plus_min: float = 90.0
    a_min: float = 80.0
    b_min: float = 70.0
    c_min: float = 60.0

    min_trades_for_full_trade_count_score: int = 100
    minimum_qualification_gate: bool = True


def _num(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


def _linear_score(value: float, worst: float, best: float) -> float:
    if best == worst:
        return 100.0 if value >= best else 0.0
    return _clamp((value - worst) / (best - worst) * 100.0)


def _metric_score(
    metrics: dict[str, Any],
    *,
    positive_pnl_bonus: float = 20.0,
    pf_good: float = 1.5,
    pf_bad: float = 0.8,
) -> float:
    pnl = _num(metrics.get("net_profit", metrics.get("net_pnl")))
    pf = _num(metrics.get("profit_factor"), 0.0)
    win_rate = _num(metrics.get("win_rate_pct"), 0.0)
    base = _linear_score(pf, pf_bad, pf_good) * 0.55 + _clamp(win_rate) * 0.45
    if pnl > 0:
        base = _clamp(base + positive_pnl_bonus)
    return base


def _extract_oos(walkforward: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    windows = list((walkforward.get("walk_forward") or {}).get("windows") or [])
    summary = walkforward.get("oos_summary") or {}
    return windows, summary


def _backtest_score(walkforward: dict[str, Any], robustness: dict[str, Any]) -> float:
    # Prefer aggregate metrics when present; otherwise use OOS windows as evidence.
    summary = walkforward.get("backtest_summary") or {}
    if summary:
        return _metric_score(summary)
    windows, _ = _extract_oos(walkforward)
    rows = [w.get("in_sample") or w.get("test") or w.get("oos") or {} for w in windows]
    if not rows:
        rows = [robustness.get("baseline_metrics") or {}]
    scores = [_metric_score(r, positive_pnl_bonus=10.0) for r in rows if r]
    return sum(scores) / len(scores) if scores else 0.0


def _oos_score(walkforward: dict[str, Any]) -> float:
    windows, summary = _extract_oos(walkforward)
    rate = _num(summary.get("qualification_rate_pct"))
    agg_profit = _num(summary.get("aggregate_oos_net_profit"))
    window_scores: list[float] = []
    for row in windows:
        oos = row.get("oos") or {}
        pf = _num(oos.get("profit_factor"), 0.0)
        dd = _num(oos.get("max_drawdown_pct"), 100.0)
        profit = _num(oos.get("net_profit"))
        score = _linear_score(pf, 0.8, 1.5) * 0.45
        score += _linear_score(dd, 35.0, 5.0) * 0.30
        score += 25.0 if profit > 0 else 0.0
        window_scores.append(_clamp(score))
    window_component = sum(window_scores) / len(window_scores) if window_scores else 0.0
    summary_component = _clamp(rate) * 0.65 + (35.0 if agg_profit > 0 else 0.0)
    return _clamp(0.65 * summary_component + 0.35 * window_component)


def _robustness_score(robustness: dict[str, Any]) -> float:
    mc = robustness.get("monte_carlo") or {}
    loss_prob = _num(mc.get("probability_of_loss_pct"), 100.0)
    baseline = (robustness.get("cost_slippage_sensitivity") or {}).get("baseline") or {}
    baseline_pnl = _num(baseline.get("net_pnl"))
    scenarios = (robustness.get("cost_slippage_sensitivity") or {}).get("scenarios") or []
    profitable_scenarios = sum(1 for x in scenarios if _num(x.get("net_pnl")) > 0)
    sensitivity_score = (profitable_scenarios / len(scenarios) * 100.0) if scenarios else (100.0 if baseline_pnl > 0 else 0.0)
    mc_score = _linear_score(100.0 - loss_prob, 40.0, 90.0)
    baseline_score = 100.0 if baseline_pnl > 0 else 0.0
    return _clamp(0.45 * mc_score + 0.35 * sensitivity_score + 0.20 * baseline_score)


def _regime_score(regime: dict[str, Any]) -> float:
    regimes = regime.get("regimes") or {}
    if not regimes:
        return 0.0
    positive = sum(1 for v in regimes.values() if _num(v.get("net_profit")) > 0)
    coverage = _num(regime.get("regime_coverage_pct"))
    positive_share = positive / len(regimes) * 100.0
    return _clamp(0.65 * positive_share + 0.35 * coverage)


def _drawdown_score(walkforward: dict[str, Any], robustness: dict[str, Any]) -> float:
    windows, _ = _extract_oos(walkforward)
    dd = [_num((w.get("oos") or {}).get("max_drawdown_pct"), 100.0) for w in windows]
    if dd:
        oos_dd = max(dd)
    else:
        oos_dd = 100.0
    mc_dd = _num((robustness.get("monte_carlo") or {}).get("p95_max_drawdown"), float("nan"))
    if isfinite(mc_dd):
        # p95 drawdown is assumed to be in currency; we don't normalize it against
        # capital without an explicit capital field, so it is used as a warning signal.
        mc_component = 60.0 if mc_dd >= 0 else 0.0
    else:
        mc_component = 50.0
    return _clamp(0.75 * _linear_score(oos_dd, 35.0, 5.0) + 0.25 * mc_component)


def _consistency_score(walkforward: dict[str, Any], regime: dict[str, Any]) -> float:
    windows, _ = _extract_oos(walkforward)
    if windows:
        profits = [_num((w.get("oos") or {}).get("net_profit")) for w in windows]
        positive = sum(1 for x in profits if x > 0)
        window_consistency = positive / len(profits) * 100.0
    else:
        window_consistency = 0.0
    regimes = regime.get("regimes") or {}
    if regimes:
        positive = sum(1 for v in regimes.values() if _num(v.get("net_profit")) > 0)
        regime_consistency = positive / len(regimes) * 100.0
    else:
        regime_consistency = 0.0
    return _clamp(0.7 * window_consistency + 0.3 * regime_consistency)


def _trade_count_score(walkforward: dict[str, Any], config: QualityConfig) -> float:
    _, summary = _extract_oos(walkforward)
    trades = _num(summary.get("aggregate_oos_trades", summary.get("total_oos_trades")))
    if trades <= 0:
        # Fall back to summing OOS windows.
        windows, _ = _extract_oos(walkforward)
        trades = sum(_num((w.get("oos") or {}).get("total_trades")) for w in windows)
    return _linear_score(trades, 0.0, float(config.min_trades_for_full_trade_count_score))


def classify_quality(score: float, *, qualified: bool, config: QualityConfig) -> str:
    if config.minimum_qualification_gate and not qualified:
        return "DISABLED"
    if score >= config.a_plus_min:
        return "A+"
    if score >= config.a_min:
        return "A"
    if score >= config.b_min:
        return "B"
    if score >= config.c_min:
        return "C"
    return "D"


def score_optionvault_strategy(
    *,
    qualification: dict[str, Any],
    walkforward: dict[str, Any],
    robustness: dict[str, Any],
    regime: dict[str, Any],
    config: QualityConfig | None = None,
) -> dict[str, Any]:
    cfg = config or QualityConfig()
    qualified = qualification.get("promotion_gate") == "PASS"
    components = {
        "backtest": _backtest_score(walkforward, robustness),
        "oos": _oos_score(walkforward),
        "robustness": _robustness_score(robustness),
        "regime": _regime_score(regime),
        "drawdown": _drawdown_score(walkforward, robustness),
        "consistency": _consistency_score(walkforward, regime),
        "trade_count": _trade_count_score(walkforward, cfg),
    }
    weights = {
        "backtest": cfg.backtest_weight,
        "oos": cfg.oos_weight,
        "robustness": cfg.robustness_weight,
        "regime": cfg.regime_weight,
        "drawdown": cfg.drawdown_weight,
        "consistency": cfg.consistency_weight,
        "trade_count": cfg.trade_count_weight,
    }
    total_weight = sum(weights.values())
    score = sum(components[k] * weights[k] for k in components) / total_weight if total_weight else 0.0
    classification = classify_quality(score, qualified=qualified, config=cfg)

    reasons: list[str] = []
    avoid: list[str] = []
    for name, value in components.items():
        if value >= 80:
            reasons.append(f"{name.upper()} evidence is strong ({value:.1f}/100)")
        elif value < 60:
            avoid.append(f"{name.upper()} evidence is weak ({value:.1f}/100)")
    if not qualified:
        avoid.append("Qualification gate is not passed")
    if components["trade_count"] < 50:
        avoid.append("Trade sample is small; do not over-trust the score")

    return {
        "strategy": qualification.get("strategy") or walkforward.get("strategy") or regime.get("strategy"),
        "quality_score": round(score, 2),
        "classification": classification,
        "qualified": qualified,
        "active": classification in {"A+", "A", "B"},
        "components": {k: round(v, 2) for k, v in components.items()},
        "weights": weights,
        "why_active": reasons[:6],
        "when_to_avoid": avoid[:8],
        "qualification_status": qualification.get("status"),
        "config": asdict(cfg),
    }
