from backend.app.options_backtest.robustness import monte_carlo_trade_bootstrap

def test_monte_carlo_deterministic():
    a = monte_carlo_trade_bootstrap([100, -50, 80, -20], simulations=500, seed=7)
    b = monte_carlo_trade_bootstrap([100, -50, 80, -20], simulations=500, seed=7)
    assert a["status"] == "PASS"
    assert a["median_final_pnl"] == b["median_final_pnl"]
    assert a["p05_final_pnl"] == b["p05_final_pnl"]
