from pathlib import Path


def test_research_suite_is_orchestration_only():
    text = Path("backend/app/api/optionvault_research_suite.py").read_text()
    assert "run_strategy_option_backtest" in text
    assert "run_optionvault_walkforward" in text
    assert "run_optionvault_robustness" in text
    assert "qualify_optionvault_research" in text
    assert "score_optionvault_strategy" in text
    assert '"synthetic_prices": False' in text
