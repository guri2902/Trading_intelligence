from backend.app.options_backtest.quality import score_optionvault_strategy


def _evidence():
    qualification = {"strategy": "VWAP_PULLBACK", "status": "QUALIFIED", "promotion_gate": "PASS"}
    walkforward = {
        "strategy": "VWAP_PULLBACK",
        "oos_summary": {
            "qualification_rate_pct": 80,
            "aggregate_oos_net_profit": 1800,
            "aggregate_oos_trades": 120,
        },
        "walk_forward": {"windows": [
            {"oos": {"profit_factor": 1.6, "max_drawdown_pct": 9, "net_profit": 800, "total_trades": 30}},
            {"oos": {"profit_factor": 1.4, "max_drawdown_pct": 14, "net_profit": 500, "total_trades": 30}},
        ]},
    }
    robustness = {
        "monte_carlo": {"probability_of_loss_pct": 25, "p95_max_drawdown": 1200},
        "cost_slippage_sensitivity": {
            "baseline": {"net_pnl": 1000},
            "scenarios": [{"net_pnl": 1000}, {"net_pnl": 500}, {"net_pnl": -10}],
        },
    }
    regime = {
        "regimes": {
            "UPTREND_NORMAL": {"net_profit": 800},
            "RANGE_NORMAL": {"net_profit": 400},
            "DOWNTREND_HIGH_VOL": {"net_profit": -50},
        },
        "regime_coverage_pct": 92,
    }
    return qualification, walkforward, robustness, regime


def test_quality_returns_rating_and_components():
    q, w, r, g = _evidence()
    out = score_optionvault_strategy(qualification=q, walkforward=w, robustness=r, regime=g)
    assert out["quality_score"] >= 0
    assert set(out["components"]) == {"backtest", "oos", "robustness", "regime", "drawdown", "consistency", "trade_count"}
    assert out["classification"] in {"A+", "A", "B", "C", "D", "DISABLED"}
    assert out["active"] is True


def test_failed_qualification_disables_even_with_high_score():
    q, w, r, g = _evidence()
    q["promotion_gate"] = "FAIL"
    out = score_optionvault_strategy(qualification=q, walkforward=w, robustness=r, regime=g)
    assert out["classification"] == "DISABLED"
    assert out["active"] is False
