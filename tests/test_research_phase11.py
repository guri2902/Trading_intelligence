from datetime import datetime, timedelta, timezone

from backend.app.backtest.engine import BacktestEngine
from backend.app.research.walk_forward import walk_forward_splits
from backend.app.research.promotion import evaluate_promotion
from backend.app.research.scoring import score_backtest
from backend.app.backtest.models import BacktestConfig


def rows(n=30):
    start = datetime(2026,9,10,9,15,tzinfo=timezone.utc)
    return [
        {
            "timestamp": start + timedelta(minutes=i),
            "open": 100+i,
            "high": 102+i,
            "low": 99+i,
            "close": 101+i,
            "volume": 1000,
        }
        for i in range(n)
    ]


def test_walk_forward_is_chronological():
    result = walk_forward_splits(
        list(range(100)),
        train_size=40,
        validation_size=20,
        test_size=20,
        step=20,
    )
    assert len(result) == 2
    assert max(result[0].train) < min(result[0].validation)
    assert max(result[0].validation) < min(result[0].test)
    assert max(result[0].test) < min(result[1].test)


def test_scoring_fails_tiny_sample():
    engine = BacktestEngine()
    result = engine.run(
        rows(),
        lambda history: None,
        strategy_name="EMPTY",
        config=BacktestConfig(),
    )
    score = score_backtest(result.metrics, min_trades=30)
    assert score.passed is False
    assert score.reasons


def test_promotion_gate_is_fail_closed():
    gate = evaluate_promotion(
        in_sample_score=90,
        validation_score=80,
        oos_score=30,
        robustness_pass=True,
        baseline_outperformance=True,
        paper_validation_pass=True,
    )
    assert gate.passed is False
    assert gate.checks["oos_stability"] is False


def test_promotion_gate_requires_all_external_checks():
    gate = evaluate_promotion(
        in_sample_score=80,
        validation_score=75,
        oos_score=70,
        robustness_pass=False,
        baseline_outperformance=False,
        paper_validation_pass=False,
    )
    assert gate.passed is False
