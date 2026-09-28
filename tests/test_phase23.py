
from optimization.engine import StrategyOptimizer, OptimizationObjective


def test_optimizer_selects_best_feasible_trial():
    results = {
        "fast=5|slow=20": {"net_pnl": 100, "expectancy": 5, "profit_factor": 1.7, "sharpe": 1.0, "sortino": 1.2, "consistency": .7, "max_drawdown_pct": 5, "trades": 20},
        "fast=10|slow=30": {"net_pnl": 180, "expectancy": 8, "profit_factor": 2.0, "sharpe": 1.3, "sortino": 1.5, "consistency": .8, "max_drawdown_pct": 6, "trades": 30},
    }

    def evaluator(params):
        return results["|".join(f"{k}={params[k]}" for k in sorted(params))]

    opt = StrategyOptimizer(evaluator, {"fast": [5, 10], "slow": [20, 30]}, seed=1,
                            objective=OptimizationObjective(min_trades=10, max_drawdown_pct=10))
    report = opt.run(20)
    assert report.best is not None
    assert report.best.params == {"fast": 10, "slow": 30}


def test_optimizer_rejects_low_trade_trial():
    def evaluator(_):
        return {"net_pnl": 500, "expectancy": 20, "profit_factor": 5, "max_drawdown_pct": 1, "trades": 2}

    report = StrategyOptimizer(evaluator, {"p": [1]}, objective=OptimizationObjective(min_trades=5)).run(1)
    assert report.best is None
    assert "min_trades" in report.trials[0].reason


def test_optimizer_rejects_excessive_drawdown():
    def evaluator(_):
        return {"net_pnl": 500, "expectancy": 20, "profit_factor": 5, "max_drawdown_pct": 25, "trades": 50}

    report = StrategyOptimizer(
        evaluator, {"p": [1]}, objective=OptimizationObjective(min_trades=5, max_drawdown_pct=10)
    ).run(1)
    assert report.best is None
    assert "max_drawdown" in report.trials[0].reason


def test_empty_search_space_fails_closed():
    try:
        StrategyOptimizer(lambda _: {}, {}).run()
    except ValueError as e:
        assert "search_space" in str(e)
    else:
        assert False
