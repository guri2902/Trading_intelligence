from backend.app.options_backtest.ranking import rank_optionvault_strategies


def test_ranking_is_deterministic_and_filters_inactive():
    items = [
        {"strategy": "A", "quality_score": 78, "classification": "A", "active": True,
         "oos_profit_factor": 1.5, "oos_net_profit": 900, "max_drawdown_pct": 10, "oos_trades": 100},
        {"strategy": "B", "quality_score": 91, "classification": "A+", "active": True,
         "oos_profit_factor": 1.2, "oos_net_profit": 700, "max_drawdown_pct": 8, "oos_trades": 80},
        {"strategy": "C", "quality_score": 95, "classification": "DISABLED", "active": False,
         "oos_profit_factor": 3.0},
    ]
    out = rank_optionvault_strategies(items, top_n=2, min_score=70)
    assert [x["strategy"] for x in out["ranked"]] == ["B", "A"]
    assert any(x["strategy"] == "C" for x in out["excluded"])


def test_tiebreaks_use_oos_pf_then_profit_then_drawdown():
    items = [
        {"strategy": "LOWER_DD", "quality_score": 80, "classification": "A", "active": True,
         "oos_profit_factor": 1.5, "oos_net_profit": 1000, "max_drawdown_pct": 8, "oos_trades": 100},
        {"strategy": "HIGHER_PF", "quality_score": 80, "classification": "A", "active": True,
         "oos_profit_factor": 1.7, "oos_net_profit": 900, "max_drawdown_pct": 12, "oos_trades": 90},
    ]
    out = rank_optionvault_strategies(items, top_n=2)
    assert out["ranked"][0]["strategy"] == "HIGHER_PF"
