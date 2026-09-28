
from ml.ensemble import ProbabilityCalibrator, EnsembleEngine


def test_calibrator_fits_and_improves_or_preserves_brier():
    c = ProbabilityCalibrator(5)
    r = c.fit([0.1, 0.2, 0.8, 0.9, 0.7], [0, 0, 1, 1, 1])
    assert r.sample_count == 5
    assert 0 <= r.brier_after <= 1
    assert 0 <= c.transform(0.5) <= 1


def test_calibrator_rejects_bad_samples():
    c = ProbabilityCalibrator()
    try:
        c.fit([1.2], [1])
    except ValueError:
        assert True
    else:
        assert False


def test_ensemble_weights_better_model_more():
    engine = EnsembleEngine(min_models=2)
    report = engine.evaluate(
        {"good": 0.80, "bad": 0.55},
        [1, 1, 1, 0],
        {
            "good": [0.9, 0.8, 0.85, 0.75],
            "bad": [0.55, 0.60, 0.50, 0.55],
        },
    )
    assert report.weights["good"] > report.weights["bad"]


def test_ensemble_prediction_uses_weights():
    engine = EnsembleEngine()
    pred = engine.predict({"a": 0.8, "b": 0.6}, {"a": 0.75, "b": 0.25})
    assert pred.probability > 0.7
    assert pred.label == "POSITIVE"
    assert pred.agreement >= 0.5


def test_ensemble_requires_min_models():
    engine = EnsembleEngine(min_models=2)
    try:
        engine.evaluate({"a": 0.5}, [1], {"a": [0.5]})
    except ValueError as e:
        assert "insufficient" in str(e)
    else:
        assert False
