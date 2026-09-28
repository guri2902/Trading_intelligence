from backend.app.options_backtest.qualification import qualify_optionvault_research


def _evidence():
    return {
        "strategy": "VWAP_PULLBACK",
        "used_actual_option_prices": True,
        "synthetic_prices": False,
        "oos_summary": {
            "windows_evaluated": 4,
            "qualification_rate_pct": 75,
            "aggregate_oos_net_profit": 1200,
        },
        "walk_forward": {"windows": [
            {"oos": {"profit_factor": 1.4, "max_drawdown_pct": 12}},
            {"oos": {"profit_factor": 1.2, "max_drawdown_pct": 18}},
        ]},
    }, {
        "used_actual_option_prices": True,
        "synthetic_prices": False,
        "monte_carlo": {"status": "PASS", "probability_of_loss_pct": 30, "p95_max_drawdown": 900},
        "cost_slippage_sensitivity": {"baseline": {"net_pnl": 800}, "scenarios": [{"net_pnl": 800}]},
    }, {
        "regimes": {
            "UPTREND_NORMAL": {"trades": 5, "net_profit": 600},
            "RANGE_NORMAL": {"trades": 4, "net_profit": 100},
        },
        "trade_count_classified": 9,
        "regime_coverage_pct": 90,
    }


def test_qualification_passes():
    wf, rob, reg = _evidence()
    out = qualify_optionvault_research(walkforward=wf, robustness=rob, regime=reg)
    assert out["promotion_gate"] == "PASS"
    assert out["actual_option_prices"] is True
    assert out["synthetic_prices"] is False


def test_qualification_fails_on_mc_loss_probability():
    wf, rob, reg = _evidence()
    rob["monte_carlo"]["probability_of_loss_pct"] = 55
    out = qualify_optionvault_research(walkforward=wf, robustness=rob, regime=reg)
    assert out["promotion_gate"] == "FAIL"
    assert out["checks"]["monte_carlo_loss_probability"] is False
