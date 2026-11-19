import numpy as np
import pandas as pd
import pytest

from aeron.config import ROOT
from aeron.features import FEATURE_SETS, bias, build_features, feature_columns
from aeron.features import build as build_module

LEADS = (1, 2, 3)
PM_COLUMNS = ["pm25_mean", "pm25_max", "pm25_eve_mean", "pm25_hours"]
GROUPS_KNOWN_AT_ORIGIN = ("hist_", "time_", "wxo_", "wxf_")


def synthetic_daily(n=240, seed=0):
    rng = np.random.default_rng(seed)
    index = pd.date_range("2023-10-01", periods=n, freq="D")
    daily = pd.DataFrame(index=index)
    daily["pm25_mean"] = rng.gamma(4.0, 10.0, n)
    daily["pm25_max"] = daily["pm25_mean"] * 1.5
    daily["pm25_eve_mean"] = daily["pm25_mean"] * 1.1
    daily["pm25_hours"] = 24.0
    names = (
        set(build_module.FORECASTABLE)
        | set(build_module.UPPER_BOUND_ONLY)
        | set(build_module.OBSERVED_ORIGIN)
    )
    for name in names:
        daily[f"era5_{name}"] = rng.normal(size=n)
    for lead in LEADS:
        for name in build_module.FORECASTABLE:
            daily[f"fc_lead{lead}_{name}"] = rng.normal(size=n)
    daily.loc[daily.index[10], "pm25_mean"] = np.nan  # a day without a daily mean
    return daily


def group(frame, *prefixes):
    return [c for c in frame.columns if c.startswith(prefixes)]


# --------------------------------------------------------------------------
# Definitions
# --------------------------------------------------------------------------
@pytest.mark.parametrize("lead", LEADS)
def test_target_and_history_alignment(lead):
    daily = synthetic_daily()
    f = build_features(daily, lead)
    origin = pd.Timestamp("2024-01-20")
    row = f.loc[origin]
    assert row["target_date"] == origin + pd.Timedelta(days=lead)
    assert row["y"] == daily.loc[origin + pd.Timedelta(days=lead), "pm25_mean"]
    assert row["y_origin"] == daily.loc[origin, "pm25_mean"]
    for j in range(7):
        assert (
            row[f"hist_pm_lag{j}"]
            == daily.loc[origin - pd.Timedelta(days=j), "pm25_mean"]
        )
    last7 = daily.loc[origin - pd.Timedelta(days=6) : origin, "pm25_mean"]
    assert row["hist_pm_roll7_mean"] == pytest.approx(last7.mean())
    assert row["hist_pm_roll7_max"] == last7.max()
    assert row["hist_pm_trend7"] == pytest.approx(
        daily.loc[origin, "pm25_mean"] - last7.mean()
    )


def test_time_features_describe_the_target_day():
    daily = synthetic_daily()
    f = build_features(daily, 2)
    origin = pd.Timestamp("2024-01-04")  # target: Saturday 2024-01-06
    row = f.loc[origin]
    assert row["time_weekend"] == 1 and row["time_dow"] == 5
    assert row["time_winter"] == 1 and row["time_month"] == 1
    angle = 2 * np.pi * pd.Timestamp("2024-01-06").day_of_year / 365.25
    assert row["time_doy_sin"] == pytest.approx(np.sin(angle))


def test_forecast_group_uses_the_forecast_for_the_target_day():
    daily = synthetic_daily()
    f = build_features(daily, 3)
    origin = pd.Timestamp("2024-01-10")
    target = origin + pd.Timedelta(days=3)
    assert f.loc[origin, "wxf_temp_mean"] == daily.loc[target, "fc_lead3_temp_mean"]
    assert f.loc[origin, "wxt_temp_mean"] == daily.loc[target, "era5_temp_mean"]
    assert (
        f.loc[origin, "wxo_temp_mean_l1"]
        == daily.loc[origin - pd.Timedelta(days=1), "era5_temp_mean"]
    )


def test_feature_sets_keep_the_perfect_forecast_group_out_of_headline_models():
    f = build_features(synthetic_daily(), 1)
    for name in ("history", "history_weather_now", "forecast", "forecast_no_wind"):
        cols = feature_columns(list(f.columns), name)
        assert not [c for c in cols if c.startswith("wxt_")], name
        assert not [c for c in cols if any(k in c for k in ("blh", "snow", "vent"))], (
            name
        )
        assert not {"y", "y_origin", "target_date", "origin_date"} & set(cols), name
    upper = feature_columns(list(f.columns), "observed_upper_bound")
    assert "wxt_blh_mean" in upper and "wxt_temp_mean" in upper
    no_wind = feature_columns(list(f.columns), "forecast_no_wind")
    assert not [
        c
        for c in no_wind
        if c.startswith("wxf_") and any(w in c for w in ("wind", "gust"))
    ]
    assert {"wxo_wind_mean_l0"} <= set(no_wind)  # wind observed at the origin stays
    assert set(feature_columns(list(f.columns), "forecast")) > set(no_wind)
    with pytest.raises(KeyError):
        feature_columns(list(f.columns), "nonsense")
    assert set(FEATURE_SETS) == {
        "history",
        "history_weather_now",
        "forecast",
        "forecast_no_wind",
        "observed_upper_bound",
    }


def test_observed_as_forecast_swaps_only_the_forecast_columns():
    f = build_features(synthetic_daily(), 2)
    train_view = build_module.observed_as_forecast(f)
    pd.testing.assert_series_equal(
        train_view["wxf_temp_mean"], f["wxt_temp_mean"], check_names=False
    )
    pd.testing.assert_series_equal(
        train_view["wxf_temp_range"], f["wxt_temp_range"], check_names=False
    )
    untouched = [c for c in f.columns if not c.startswith("wxf_")]
    pd.testing.assert_frame_equal(train_view[untouched], f[untouched])
    assert not (
        f["wxf_temp_mean"] == f["wxt_temp_mean"]
    ).all()  # the original is not modified


# --------------------------------------------------------------------------
# Leakage: nothing after the origin may change the features of that origin
# --------------------------------------------------------------------------
def perturb_after(daily, origin):
    """Replace every observation after the origin day by garbage (forecast columns are untouched)."""
    bad = daily.copy()
    after = bad.index > origin
    for col in PM_COLUMNS:
        bad.loc[after, col] = 1e6
    for col in [c for c in bad.columns if c.startswith("era5_")]:
        bad.loc[after, col] = 1e6
    return bad


def assert_same(a, b, columns):
    pd.testing.assert_series_equal(a[columns], b[columns], check_names=False)


@pytest.mark.parametrize("lead", LEADS)
def test_features_known_at_the_origin_ignore_everything_after_it(lead):
    daily = synthetic_daily()
    clean = build_features(daily, lead)
    for origin in [
        pd.Timestamp("2023-12-15"),
        pd.Timestamp("2024-01-20"),
        pd.Timestamp("2024-03-01"),
    ]:
        bad = build_features(perturb_after(daily, origin), lead)
        columns = group(clean, *GROUPS_KNOWN_AT_ORIGIN)
        assert_same(clean.loc[origin], bad.loc[origin], columns)


@pytest.mark.parametrize("lead", LEADS)
def test_the_test_can_fail_target_day_weather_does_change(lead):
    """A sanity check of the leakage test: the perfect-forecast group must react to the perturbation."""
    daily = synthetic_daily()
    origin = pd.Timestamp("2024-01-20")
    clean = build_features(daily, lead).loc[origin]
    bad = build_features(perturb_after(daily, origin), lead).loc[origin]
    assert (
        clean[group(pd.DataFrame([clean]), "wxt_")]
        != bad[group(pd.DataFrame([bad]), "wxt_")]
    ).all()
    assert clean["y"] != bad["y"]  # and so does the target


def test_a_leaky_feature_would_be_caught():
    """If a feature used a centred rolling window, the same perturbation would change it."""
    daily = synthetic_daily()
    origin = pd.Timestamp("2024-01-20")
    leaky = daily["pm25_mean"].rolling(7, center=True, min_periods=1).mean()
    bad = (
        perturb_after(daily, origin)["pm25_mean"]
        .rolling(7, center=True, min_periods=1)
        .mean()
    )
    assert leaky.loc[origin] != bad.loc[origin]
    honest = daily["pm25_mean"].rolling(7, min_periods=1).mean()
    bad_honest = (
        perturb_after(daily, origin)["pm25_mean"].rolling(7, min_periods=1).mean()
    )
    assert honest.loc[origin] == bad_honest.loc[origin]


def test_forecast_group_depends_only_on_the_forecast_of_the_target_day():
    daily = synthetic_daily()
    lead, origin = 2, pd.Timestamp("2024-01-20")
    target = origin + pd.Timedelta(days=lead)
    clean = build_features(daily, lead).loc[origin]
    other_days = daily.copy()
    mask = other_days.index != target
    for col in [c for c in other_days.columns if c.startswith("fc_lead")]:
        other_days.loc[mask, col] = 1e6
    wxf = group(pd.DataFrame([clean]), "wxf_")
    assert_same(clean, build_features(other_days, lead).loc[origin], wxf)
    changed = daily.copy()
    changed.loc[target, "fc_lead2_temp_mean"] = 1e6
    assert build_features(changed, lead).loc[origin, "wxf_temp_mean"] == 1e6


@pytest.mark.parametrize("lead", LEADS)
def test_changing_the_target_does_not_change_any_feature_of_the_same_row(lead):
    daily = synthetic_daily()
    origin = pd.Timestamp("2024-01-20")
    target = origin + pd.Timedelta(days=lead)
    changed = daily.copy()
    changed.loc[target, "pm25_mean"] = 1e6
    a, b = (
        build_features(daily, lead).loc[origin],
        build_features(changed, lead).loc[origin],
    )
    assert b["y"] == 1e6
    columns = [
        c
        for c in feature_columns(list(build_features(daily, lead).columns), "forecast")
    ]
    assert_same(a, b, columns)


DAILY_TABLE = ROOT / "data" / "processed" / "daily_us_embassy.csv"


@pytest.mark.skipif(not DAILY_TABLE.exists(), reason="processed data not built")
@pytest.mark.parametrize("lead", LEADS)
def test_leakage_check_on_the_real_processed_table(lead):
    daily = pd.read_csv(DAILY_TABLE, index_col=0, parse_dates=True)
    clean = build_features(daily, lead)
    for origin in [
        pd.Timestamp("2021-12-10"),
        pd.Timestamp("2023-01-20"),
        pd.Timestamp("2024-12-15"),
    ]:
        bad = build_features(perturb_after(daily, origin), lead)
        assert_same(
            clean.loc[origin], bad.loc[origin], group(clean, *GROUPS_KNOWN_AT_ORIGIN)
        )


# --------------------------------------------------------------------------
# Bias correction of forecast wind
# --------------------------------------------------------------------------
def wind_series(n=300, ratio=0.7, seed=0):
    rng = np.random.default_rng(seed)
    index = pd.date_range("2024-01-20", periods=n, freq="D")
    observed = pd.Series(rng.uniform(4, 12, n), index=index)
    forecast = observed * ratio + rng.normal(0, 0.3, n)
    return forecast, observed


def test_fitted_ratio_removes_a_systematic_bias():
    forecast, observed = wind_series(ratio=0.7)
    cutoff = forecast.index[150]
    ratio = bias.fit_ratio(forecast, observed, cutoff)
    assert ratio == pytest.approx(1 / 0.7, rel=0.03)
    report = bias.bias_report(forecast, observed, ratio, forecast.index[160:])
    assert report["bias_before"] < -2 and abs(report["bias_after"]) < 0.3
    assert report["mae_after"] < report["mae_before"]


def test_ratio_uses_only_days_up_to_the_cutoff():
    forecast, observed = wind_series()
    cutoff = forecast.index[150]
    base = bias.fit_ratio(forecast, observed, cutoff)
    changed = observed.copy()
    changed.iloc[151:] = 999.0  # data after the cutoff
    assert bias.fit_ratio(forecast, changed, cutoff) == base
    assert (
        bias.fit_ratio(
            forecast.where(forecast.index <= cutoff), observed, forecast.index[-1]
        )
        == base
    )


def test_too_little_history_gives_no_correction():
    forecast, observed = wind_series(n=300)
    assert bias.fit_ratio(forecast, observed, forecast.index[20], min_days=60) is None
    assert bias.correct_wind(forecast, None) is forecast


def test_vector_correction_keeps_the_direction():
    u, v = pd.Series([3.0, -4.0]), pd.Series([4.0, 3.0])
    cu, cv = bias.correct_wind_vector(u, v, 1.5)
    assert np.allclose(np.arctan2(cv, cu), np.arctan2(v, u))  # same direction
    assert np.allclose(np.hypot(cu, cv), 1.5 * np.hypot(u, v))  # speed scaled
