from datetime import date

import numpy as np
import pandas as pd
import pytest

from aeron.evaluation import splits
from aeron.evaluation.runner import common_rows, run_models
from aeron.features import build as build_module
from aeron.features import build_features
from aeron.models import baselines
from aeron.models.baselines import Context

NAMES = (
    set(build_module.FORECASTABLE)
    | set(build_module.UPPER_BOUND_ONLY)
    | set(build_module.OBSERVED_ORIGIN)
)


def synthetic_daily(start="2021-01-01", n=1100, forecast_from="2023-11-01", seed=0):
    rng = np.random.default_rng(seed)
    index = pd.date_range(start, periods=n, freq="D")
    daily = pd.DataFrame(index=index)
    season = 30 + 20 * np.cos(2 * np.pi * (index.day_of_year - 15) / 365.25)
    wind = rng.normal(0, 1, n)
    daily["pm25_mean"] = np.clip(season - 8 * wind + rng.normal(0, 5, n), 3, None)
    daily["pm25_max"] = daily["pm25_mean"] * 1.5
    daily["pm25_eve_mean"] = daily["pm25_mean"] * 1.1
    daily["pm25_hours"] = 24.0
    for name in NAMES:
        daily[f"era5_{name}"] = rng.normal(size=n)
    daily["era5_wind_mean"] = wind
    for lead in (1, 2, 3):
        for name in build_module.FORECASTABLE:
            daily[f"fc_lead{lead}_{name}"] = daily[f"era5_{name}"] + rng.normal(
                0, 0.3, n
            )
            daily.loc[daily.index < forecast_from, f"fc_lead{lead}_{name}"] = np.nan
    return daily


def context(daily, lead=1, test_start="2023-11-01"):
    return Context(
        lead=lead, test_start=pd.Timestamp(test_start), daily_mean=daily["pm25_mean"]
    )


# --------------------------------------------------------------------------
# Naive forecasts
# --------------------------------------------------------------------------
def test_persistence_and_seven_day_mean_read_known_columns():
    daily = synthetic_daily()
    rows = build_features(daily, 2).dropna(subset=["y", "y_origin"])
    ctx = context(daily, 2)
    assert (baselines.Persistence().predict(rows, ctx) == rows["y_origin"]).all()
    assert baselines.Mean7Days().predict(rows, ctx) == pytest.approx(
        rows["hist_pm_roll7_mean"].to_numpy(), nan_ok=True
    )


def test_climatology_window_wraps_around_the_new_year():
    train = pd.DataFrame(
        {
            "target_date": pd.to_datetime(
                ["2020-12-28", "2021-01-03", "2020-06-15", "2021-01-20"]
            ),
            "y": [10.0, 20.0, 99.0, 500.0],
        }
    )
    test = pd.DataFrame({"target_date": pd.to_datetime(["2022-01-01", "2022-09-01"])})
    model = baselines.Climatology(window_days=15).fit(train, None)
    pred = model.predict(test, None)
    assert pred[0] == pytest.approx(
        15.0
    )  # Dec 28 and Jan 3 are within 15 days of Jan 1; Jan 20 is not
    assert np.isnan(pred[1])  # nothing within 15 days of September 1


def test_climatology_uses_training_rows_only():
    daily = synthetic_daily()
    rows = build_features(daily, 1)
    train = rows[rows["target_date"] < "2022-01-01"].dropna(subset=["y"])
    later = rows[rows["target_date"] >= "2023-06-01"].dropna(subset=["y"]).head(30)
    shifted = train.copy()
    first = baselines.Climatology().fit(train, None).predict(later, None)
    second = baselines.Climatology().fit(shifted, None).predict(later, None)
    assert np.allclose(first, second, equal_nan=True)
    extra = later.assign(y=1e6)
    assert np.allclose(
        baselines.Climatology().fit(pd.concat([train]), None).predict(extra, None),
        first,
        equal_nan=True,
    )


def test_seasonal_naive_looks_one_year_back():
    daily = synthetic_daily()
    rows = build_features(daily, 3).dropna(subset=["y"])
    ctx = context(daily, 3)
    sample = rows[rows["target_date"] >= "2022-03-01"].head(5)
    pred = baselines.SeasonalNaive().predict(sample, ctx)
    expected = (
        daily["pm25_mean"]
        .reindex(pd.DatetimeIndex(sample["target_date"]) - pd.Timedelta(days=365))
        .to_numpy()
    )
    assert np.allclose(pred, expected)
    early = rows[rows["target_date"] < "2021-12-01"].head(3)
    assert np.isnan(
        baselines.SeasonalNaive().predict(early, ctx)
    ).all()  # no earlier year in the data


# --------------------------------------------------------------------------
# Ridge models
# --------------------------------------------------------------------------
def split_rows(daily, lead=1, start="2023-11-01"):
    rows = build_features(daily, lead)
    cutoff = pd.Timestamp(start) - pd.Timedelta(days=lead)
    train = rows[(rows["target_date"] <= cutoff) & rows["y"].notna()]
    test = rows[
        (rows["target_date"] >= start)
        & rows["y"].notna()
        & rows["wxf_temp_mean"].notna()
    ]
    return train, test


def test_ridge_predictions_are_non_negative_and_use_the_penalty_grid():
    daily = synthetic_daily()
    train, test = split_rows(daily)
    model = baselines.RidgeModel("forecast", "r").fit(train, context(daily))
    pred = model.predict(test, context(daily))
    assert len(pred) == len(test) and (pred >= 0).all() and np.isfinite(pred).all()
    assert model.chosen_alpha in baselines.RIDGE_ALPHAS


def test_ridge_weather_model_reacts_to_the_forecast_and_history_model_does_not():
    daily = synthetic_daily()
    train, test = split_rows(daily)
    ctx = context(daily)
    weather = baselines.RidgeModel("forecast", "w").fit(train, ctx)
    history = baselines.RidgeModel("history", "h").fit(train, ctx)
    changed = test.assign(wxf_wind_mean=test["wxf_wind_mean"] + 3.0)
    assert not np.allclose(weather.predict(test, ctx), weather.predict(changed, ctx))
    assert np.allclose(history.predict(test, ctx), history.predict(changed, ctx))


def test_ridge_refuses_training_rows_from_the_test_period():
    daily = synthetic_daily()
    train, test = split_rows(daily)
    leaky = pd.concat([train, test.head(5)])
    with pytest.raises(ValueError):
        baselines.RidgeModel("history", "h").fit(leaky, context(daily))


def test_ridge_beats_persistence_when_weather_drives_the_target():
    daily = synthetic_daily(n=1400, forecast_from="2022-01-01")
    train, test = split_rows(daily, start="2024-01-01")
    ctx = context(daily, 1, "2024-01-01")
    ridge = baselines.RidgeModel("forecast", "w").fit(train, ctx)
    mae_ridge = np.mean(np.abs(ridge.predict(test, ctx) - test["y"]))
    mae_persistence = np.mean(np.abs(test["y_origin"] - test["y"]))
    assert mae_ridge < mae_persistence


# --------------------------------------------------------------------------
# Runner
# --------------------------------------------------------------------------
class Spy:
    """Model that records what it was trained on."""

    name = "spy"
    uses_weather = False

    def __init__(self):
        self.fits = []

    def fit(self, train, ctx):
        self.fits.append(
            (train["target_date"].max(), ctx.test_start, ctx.lead, len(train))
        )
        return self

    def predict(self, test, ctx):
        return test["y_origin"].to_numpy(dtype=float)


@pytest.mark.parametrize("lead", [1, 2, 3])
def test_runner_trains_only_on_rows_known_before_each_block(lead):
    daily = synthetic_daily()
    blocks = splits.seasonal_blocks(2022, date(2024, 1, 1))
    spy = Spy()
    out = run_models(daily, [spy], lead, blocks, "observed")
    assert spy.fits and len(spy.fits) == out["block"].nunique()
    for latest_train_target, test_start, fit_lead, _ in spy.fits:
        assert latest_train_target <= test_start - pd.Timedelta(days=fit_lead)
    sizes = [n for *_, n in spy.fits]
    assert sizes == sorted(sizes)  # expanding window


def test_runner_forecast_view_scores_only_rows_with_a_real_forecast():
    daily = synthetic_daily()
    blocks = splits.seasonal_blocks(2022, date(2024, 1, 1))
    models = [baselines.Persistence(), baselines.RidgeModel("forecast", "w")]
    forecast = run_models(daily, models, 1, blocks, "forecast")
    assert forecast["target_date"].min() >= pd.Timestamp("2023-11-01")
    observed = run_models(
        daily,
        [baselines.Persistence(), baselines.RidgeModel("forecast", "w")],
        1,
        blocks,
        "observed",
    )
    assert observed["target_date"].min() < pd.Timestamp("2023-01-01")
    assert len(observed) > len(forecast)
    assert forecast[["persistence", "w"]].notna().all().all()


def test_runner_rows_are_unique_and_inside_their_blocks():
    daily = synthetic_daily()
    blocks = splits.seasonal_blocks(2022, date(2024, 1, 1))
    out = run_models(daily, [baselines.Persistence()], 2, blocks, "observed")
    assert not out["target_date"].duplicated().any()
    by_name = {b.name: b for b in blocks}
    for name, group in out.groupby("block"):
        assert group["target_date"].min() >= pd.Timestamp(by_name[name].start)
        assert group["target_date"].max() <= pd.Timestamp(by_name[name].end)


def test_common_rows_keeps_only_rows_every_model_predicted():
    frame = pd.DataFrame(
        {
            "y": [1.0, 2.0, 3.0, np.nan],
            "a": [1.0, np.nan, 3.0, 4.0],
            "b": [1.0, 2.0, 3.0, 4.0],
        }
    )
    kept = common_rows(frame, ["a", "b"])
    assert kept["y"].tolist() == [1.0, 3.0]


def test_runner_rejects_an_unknown_view():
    with pytest.raises(ValueError):
        run_models(synthetic_daily(), [baselines.Persistence()], 1, [], "nonsense")
