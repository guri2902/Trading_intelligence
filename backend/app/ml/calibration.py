from __future__ import annotations


def calibrate_estimator(estimator, x_calibration, y_calibration):
    """
    Optional post-training probability calibration.

    Kept isolated so calibration can later use a strictly separate
    chronological calibration slice.
    """
    try:
        from sklearn.calibration import CalibratedClassifierCV
    except ImportError as exc:
        raise RuntimeError("scikit-learn is required") from exc

    calibrated = CalibratedClassifierCV(
        estimator=estimator,
        method="sigmoid",
        cv="prefit",
    )
    calibrated.fit(x_calibration, y_calibration)
    return calibrated
