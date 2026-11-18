import math

import numpy as np
import pandas as pd
import pytest

from aeron.evaluation import metrics


def test_point_metrics_known_values():
    m = metrics.point_metrics([10, 20, 30], [12, 18, 36])
    assert m["n"] == 3
    assert m["mae"] == pytest.approx((2 + 2 + 6) / 3)
    assert m["rmse"] == pytest.approx(math.sqrt((4 + 4 + 36) / 3))
    assert m["bias"] == pytest.approx((2 - 2 + 6) / 3)
    assert m["r2"] == pytest.approx(1 - 44 / 200)


def test_point_metrics_ignore_missing_and_handle_empty():
    m = metrics.point_metrics([10, np.nan, 30], [12, 5, np.nan])
    assert m["n"] == 1 and m["mae"] == 2
    assert metrics.point_metrics([], [])["n"] == 0
    assert math.isnan(
        metrics.point_metrics([5, 5], [5, 6])["r2"]
    )  # no spread in the truth


def test_r2_is_zero_for_the_mean_and_one_for_a_perfect_forecast():
    y = np.array([1.0, 2.0, 3.0, 4.0])
    assert metrics.point_metrics(y, y)["r2"] == pytest.approx(1.0)
    assert metrics.point_metrics(y, np.full(4, y.mean()))["r2"] == pytest.approx(0.0)


def test_mape_guard_leaves_out_low_values():
    assert metrics.mape([100, 200, 2], [110, 180, 50]) == pytest.approx(
        10.0
    )  # the 2 is ignored
    assert metrics.mape([100, 200, 2], [110, 180, 50], min_true=1) > 100
    assert math.isnan(metrics.mape([1, 2], [1, 2]))


def test_skill_score():
    assert metrics.skill_score(15, 20) == pytest.approx(0.25)
    assert metrics.skill_score(25, 20) == pytest.approx(-0.25)


def test_slice_metrics_selects_rows_and_predictions():
    frame = pd.DataFrame(
        {"y": [10, 20, 100, 120], "a": [12, 22, 90, 100], "b": [10, 20, 100, 120]}
    )
    out = metrics.slice_metrics(
        frame, "y", ["a", "b"], {"all": frame["y"] >= 0, "high": frame["y"] >= 100}
    )
    high_a = out[(out["slice"] == "high") & (out["prediction"] == "a")].iloc[0]
    assert (
        high_a["n"] == 2
        and high_a["mae"] == pytest.approx(15)
        and high_a["bias"] == pytest.approx(-15)
    )
    assert out[(out["slice"] == "all") & (out["prediction"] == "b")].iloc[0]["mae"] == 0


def test_event_metrics_counts_and_always_yes():
    y = [10, 60, 70, 20, 80, 30]  # events at or above 55.5: three of six
    pred = [60, 60, 20, 10, 90, 10]  # hits: 60, 80; false alarm: 10 -> 60; miss: 70
    m = metrics.event_metrics(y, pred, 55.5)
    assert (m["events"], m["n"], m["base_rate"]) == (3, 6, 0.5)
    assert m["precision"] == pytest.approx(2 / 3) and m["recall"] == pytest.approx(
        2 / 3
    )
    assert m["f1"] == pytest.approx(2 / 3)
    assert m["always_yes_f1"] == pytest.approx(2 * 0.5 / 1.5)


def test_event_metrics_no_events_predicted():
    m = metrics.event_metrics([60, 70], [10, 10], 55.5)
    assert m["f1"] == 0.0 and m["recall"] == 0.0 and math.isnan(m["precision"])


def test_probability_metrics_perfect_and_constant_forecasts():
    y = np.array([10, 60, 70, 20, 80, 30, 90, 15], dtype=float)
    event = (y >= 55.5).astype(float)
    perfect = metrics.probability_metrics(y, event, 55.5, bins=4)
    assert (
        perfect["auc"] == 1.0
        and perfect["brier"] == 0.0
        and perfect["brier_skill"] == 1.0
    )
    constant = metrics.probability_metrics(y, np.full(8, event.mean()), 55.5, bins=4)
    assert constant["brier_skill"] == pytest.approx(0.0)
    assert constant["ece"] == pytest.approx(0.0)
    assert math.isnan(
        metrics.probability_metrics([1, 2], [0.1, 0.2], 55.5)["auc"]
    )  # no events


def test_calibration_error_detects_overconfidence():
    rng = np.random.default_rng(0)
    p = rng.uniform(0.0, 1.0, 20000)
    calibrated = (rng.uniform(size=p.size) < p).astype(float)
    assert metrics.expected_calibration_error(calibrated, p) < 0.02
    assert metrics.expected_calibration_error(calibrated, np.clip(p * 1.5, 0, 1)) > 0.1
    table = metrics.reliability_table(calibrated, p, bins=5)
    assert len(table) == 5 and table["n"].sum() == p.size
    assert (table["mean_predicted"].diff().dropna() > 0).all()


def test_quantile_coverage():
    assert metrics.quantile_coverage([1, 2, 3, 4], [2, 2, 2, 5]) == {
        "n": 4,
        "coverage": 0.75,
    }


def test_block_ids_group_consecutive_days():
    days = pd.Series(pd.date_range("2024-01-01", periods=30, freq="D"))
    ids = metrics.block_ids(days, 14)
    assert ids[0] == 0 and ids[13] == 0 and ids[14] == 1 and ids[-1] == 2


def make_days(n=400):
    return pd.Series(pd.date_range("2023-01-01", periods=n, freq="D"))


def test_bootstrap_of_a_constant_difference_is_tight():
    days = make_days()
    loss_b = np.random.default_rng(1).uniform(10, 30, len(days))
    result = metrics.paired_block_bootstrap(days, loss_b - 5, loss_b)
    assert (
        result["diff"] == pytest.approx(-5)
        and result["lo"] == pytest.approx(-5)
        and result["hi"] == pytest.approx(-5)
    )


def test_bootstrap_of_identical_losses_covers_zero_and_is_reproducible():
    days = make_days()
    noise = np.random.default_rng(2).normal(size=len(days))
    a = metrics.paired_block_bootstrap(days, noise, noise[::-1])
    b = metrics.paired_block_bootstrap(days, noise, noise[::-1])
    assert a == b
    assert a["lo"] < 0 < a["hi"]
    zero = metrics.paired_block_bootstrap(days, noise, noise)
    assert zero["diff"] == 0 and zero["lo"] == 0 and zero["hi"] == 0


def test_bootstrap_interval_is_wider_with_dependent_data_than_naive():
    # Strongly autocorrelated differences: a block bootstrap must be wider than resampling single days.
    rng = np.random.default_rng(3)
    n = 800
    diff = np.zeros(n)
    for i in range(1, n):
        diff[i] = 0.9 * diff[i - 1] + rng.normal()
    days = pd.Series(pd.date_range("2022-01-01", periods=n, freq="D"))
    block = metrics.paired_block_bootstrap(days, diff, np.zeros(n), block_days=14)
    single = metrics.paired_block_bootstrap(days, diff, np.zeros(n), block_days=1)
    assert (block["hi"] - block["lo"]) > 1.5 * (single["hi"] - single["lo"])


def test_bootstrap_ignores_missing_pairs():
    days = make_days(100)
    a = np.ones(100)
    a[:10] = np.nan
    assert metrics.paired_block_bootstrap(days, a, np.zeros(100))["n"] == 90
