from pathlib import Path


def test_phase18_validator_exists():
    p = Path("scripts/validate_production.py")
    assert p.exists()


def test_validator_checks_the_final_research_contract():
    text = Path("scripts/validate_production.py").read_text(encoding="utf-8")
    for token in (
        "optionvault_research_suite_router",
        "synthetic_prices",
        "used_actual_option_prices",
        "compileall",
        "npm",
    ):
        assert token in text
