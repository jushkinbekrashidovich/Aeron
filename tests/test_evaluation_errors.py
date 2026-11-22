import numpy as np
import pandas as pd
import pytest

from aeron.evaluation import errors


def frame(y, pred, start="2024-01-01"):
    days = pd.date_range(start, periods=len(y), freq="D")
    return pd.DataFrame({"target_date": days, "y": y, "m": pred, "season": "winter"})


def test_error_by_level_signs_and_shares():
    pred = frame([10, 10, 80, 120], [12, 8, 70, 90])
    out = errors.error_by_level(pred, "m")
    assert out.loc["<25", "bias"] == pytest.approx(0.0)
    assert out.loc["55.5-100", "bias"] == pytest.approx(-10)
    assert out.loc[">=100", "bias"] == pytest.approx(-30)
    assert out["days"].sum() == 4
    assert out["share_of_abs_error"].sum() == pytest.approx(1.0)


def test_find_episodes_needs_consecutive_high_days():
    y = [50, 110, 120, 60, 130, 50, 105, 106, 107]
    pred = frame(y, [50, 60, 40, 60, 140, 50, 70, 100, 110])
    out = errors.find_episodes(pred, "m", 100, 2)
    assert len(out) == 2  # day 5 alone is not an episode
    assert list(out["days"]) == [2, 3]
    assert out.loc[0, "peak_observed"] == 120
    assert out.loc[0, "days_alerted"] == 1
    assert out.loc[1, "days_alerted"] == 3


def test_episode_does_not_cross_a_gap_in_days():
    pred = frame([110, 120, 130, 140], [0, 0, 0, 0])
    pred.loc[2:, "target_date"] += pd.Timedelta(days=3)
    assert list(errors.find_episodes(pred, "m", 100, 2)["days"]) == [2, 2]


def test_false_alarm_runs():
    y = [10, 10, 10, 80, 10, 10]
    pred = frame(y, [60, 70, 10, 90, 60, 10])
    out = errors.false_alarm_runs(pred, "m", 55.5, 2)
    assert list(out["days"]) == [2]
    assert out.loc[0, "mean_forecast"] == pytest.approx(65)


def test_tail_performance():
    pred = frame([20, 100, 200], [20, 60, 90])
    out = errors.tail_performance(pred, "m", 100, 55.5)
    assert out["days"] == 2
    assert out["mean_error"] == pytest.approx(-75)
    assert out["share_forecast_at_alert"] == pytest.approx(1.0)
    assert out["share_forecast_at_threshold"] == 0.0
    assert errors.tail_performance(frame([1, 2], [1, 2]), "m")["days"] == 0


def test_error_autocorrelation_uses_calendar_lags():
    rng = np.random.default_rng(0)
    e = np.cumsum(rng.normal(size=300)) * 0.1 + rng.normal(size=300)
    pred = frame(np.full(300, 50.0), 50 + e)
    ac = errors.error_autocorrelation(pred, "m", 3)
    assert ac[1] > 0.2
    assert set(ac) == {1, 2, 3}


def test_rolling_mae_and_calendar_tables():
    pred = frame(np.full(60, 10.0), np.full(60, 14.0))
    assert errors.rolling_mae(pred, "m", 28).dropna().iloc[-1] == pytest.approx(4)
    assert errors.error_by_month(pred, "m").loc[1, "bias"] == pytest.approx(4)
    assert errors.error_by_weekday(pred, "m")["days"].sum() == 60
