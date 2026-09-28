
from validation.walk_forward import WalkForwardValidator


def _optimizer(train):
    # Params deliberately depend only on the train slice.
    return {"threshold": round(sum(train) / len(train), 2)}, {"train_pnl": sum(train)}


def _tester(test, params):
    # Positive mean produces a positive OOS result.
    mean = sum(test) / len(test)
    return {
        "net_pnl": mean * 10,
        "trades": len(test),
        "win_rate": 1.0 if mean > 0 else 0.0,
        "max_drawdown_pct": 2.0,
    }


def test_windows_are_chronological_and_non_overlapping():
    v = WalkForwardValidator(_optimizer, _tester, train_size=4, test_size=2,
                             step_size=2, min_windows=2)
    ws = v.windows(10)
    assert [(w.train_start, w.train_end, w.test_start, w.test_end) for w in ws] == [
        (0, 4, 4, 6), (2, 6, 6, 8), (4, 8, 8, 10)
    ]
    for w in ws:
        assert w.train_end == w.test_start


def test_positive_oos_can_promote():
    data = [1, 2, 3, 4, 5, 6, 7, 8]
    v = WalkForwardValidator(_optimizer, _tester, train_size=2, test_size=2,
                             step_size=2, min_windows=3, min_oos_trades=1)
    report = v.validate(data)
    assert report.promoted is True
    assert report.aggregate_oos["total_oos_pnl"] > 0


def test_negative_oos_fails_stability_gate():
    data = [1, 2, -3, -4, 5, 6, -7, -8]
    v = WalkForwardValidator(_optimizer, _tester, train_size=2, test_size=2,
                             step_size=2, min_windows=3, min_oos_trades=1,
                             min_positive_windows_pct=0.75)
    report = v.validate(data)
    assert report.promoted is False
    assert "positive_window_pct" in report.promotion_reason


def test_oos_trade_gate_can_reject_window():
    data = [1, 2, 3, 4, 5, 6]
    v = WalkForwardValidator(_optimizer, _tester, train_size=2, test_size=1,
                             step_size=1, min_windows=3, min_oos_trades=5)
    report = v.validate(data)
    assert report.promoted is False
    assert any("min_oos_trades" in r.reason for r in report.windows)


def test_insufficient_data_fails_closed():
    v = WalkForwardValidator(_optimizer, _tester, train_size=5, test_size=5)
    try:
        v.validate([1, 2, 3])
    except ValueError as e:
        assert "insufficient" in str(e)
    else:
        assert False


def test_optimizer_error_isolated_to_window():
    def bad_optimizer(train):
        if train[0] == 3:
            raise RuntimeError("boom")
        return _optimizer(train)

    v = WalkForwardValidator(bad_optimizer, _tester, train_size=2, test_size=1,
                             step_size=1, min_windows=3)
    report = v.validate([1, 2, 3, 4, 5, 6])
    assert any(r.reason.startswith("window_error") for r in report.windows)
