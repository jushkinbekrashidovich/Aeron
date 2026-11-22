from datetime import date

import numpy as np
import pandas as pd
import pytest

from aeron import uncertainty
from aeron.evaluation import splits
from aeron.models import trees
from tests.test_models_baselines import synthetic_daily

TINY = ({"max_depth": 3, "min_samples_leaf": 5},)


def small_forest():
    def make(params, seed):
        return trees.RandomForestRegressor(
            n_estimators=15, random_state=seed, n_jobs=1, **params
        )

    return trees.TreeModel("forecast", "rf", make, TINY)


def test_plain_intervals_cover_about_the_nominal_share_on_iid_errors():
    rng = np.random.default_rng(0)
    f = rng.uniform(10, 100, 3000)
    y = f + rng.normal(0, 8, 3000)
    cal = uncertainty.IntervalCalibrator().fit(f[:1500], y[:1500])
    test = pd.DataFrame(
        {"y": y[1500:], "target_date": pd.date_range("2020-01-01", periods=1500)}
    )
    iv = cal.intervals(f[1500:])
    test = pd.concat([test, iv], axis=1)
    assert uncertainty.coverage(test, "lo90_plain", "hi90_plain") == pytest.approx(
        0.9, abs=0.03
    )
    assert uncertainty.coverage(test, "lo80_plain", "hi80_plain") == pytest.approx(
        0.8, abs=0.04
    )


def test_scaled_intervals_are_wider_on_polluted_days_and_ordered():
    rng = np.random.default_rng(1)
    f = rng.uniform(10, 150, 2000)
    y = f + rng.normal(0, 0.2, 2000) * np.maximum(f, 15)
    cal = uncertainty.IntervalCalibrator().fit(f, y)
    iv = cal.intervals(np.array([20.0, 120.0]))
    width = iv["hi90_scaled"] - iv["lo90_scaled"]
    assert width[1] > 3 * width[0]
    assert (iv["lo80_scaled"] >= iv["lo90_scaled"]).all()
    assert (iv["hi80_scaled"] <= iv["hi90_scaled"]).all()
    assert (iv["lo90_plain"] >= 0).all()


def test_probabilities_increase_with_the_forecast_and_stay_in_range():
    rng = np.random.default_rng(2)
    f = rng.uniform(0, 120, 2000)
    y = f + rng.normal(0, 15, 2000)
    cal = uncertainty.IntervalCalibrator().fit(f, y)
    p = cal.probabilities(np.array([10.0, 50.0, 100.0]))
    for col in ("p55.5_platt", "p55.5_conformal"):
        assert p[col].is_monotonic_increasing
        assert p[col].between(0, 1).all()
    assert p.loc[2, "p55.5_platt"] > 0.8
    assert p.loc[0, "p55.5_platt"] < 0.1


def test_calibrator_refuses_tiny_samples():
    with pytest.raises(ValueError):
        uncertainty.IntervalCalibrator().fit(np.arange(10.0), np.arange(10.0))


def test_miss_clustering_detects_spells():
    n = 100
    y = np.full(n, 50.0)
    y[10:15] = 500.0
    frame = pd.DataFrame(
        {
            "y": y,
            "lo": 0.0,
            "hi": 100.0,
            "target_date": pd.date_range("2020-01-01", periods=n),
        }
    )
    out = uncertainty.miss_clustering(frame, "lo", "hi")
    assert out["miss_rate"] == pytest.approx(0.05)
    assert out["miss_rate_after_miss"] == pytest.approx(0.8)


def test_run_intervals_uses_only_past_targets_for_calibration():
    daily = synthetic_daily(n=1700)
    blocks = splits.seasonal_blocks(2023, date(2025, 1, 15))
    out = uncertainty.run_intervals(daily, small_forest, 1, blocks, ("observed",))
    frame = out["observed"]
    assert {"pred", "lo90_scaled", "hi90_scaled", "p55.5_platt"} <= set(frame.columns)
    assert (frame["hi90_scaled"] >= frame["pred"]).all()
    assert frame["target_date"].min() >= pd.Timestamp("2023-11-01")
    assert frame["target_date"].nunique() > 300
    # the future cannot change the intervals of earlier blocks
    changed = daily.copy()
    changed.loc[changed.index >= "2024-11-01", "pm25_mean"] = 400.0
    again = uncertainty.run_intervals(changed, small_forest, 1, blocks, ("observed",))
    first = frame[frame["target_date"] < "2024-11-01"].reset_index(drop=True)
    first2 = again["observed"]
    first2 = first2[first2["target_date"] < "2024-11-01"].reset_index(drop=True)
    cols = ["pred", "lo90_scaled", "hi90_scaled", "p55.5_platt"]
    assert np.allclose(first[cols], first2[cols])
