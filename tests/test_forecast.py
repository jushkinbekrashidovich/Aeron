import json

import numpy as np
import pandas as pd
import pytest

from aeron import forecast
from aeron.config import ROOT
from aeron.models import trees
from tests.test_models_baselines import synthetic_daily

GRID = ({"max_depth": 3, "min_samples_leaf": 5},)


def _small_rf(params, seed):
    # module-level so that joblib can pickle the fitted model
    return trees.RandomForestRegressor(
        n_estimators=15, random_state=seed, n_jobs=1, **params
    )


def small_forest():
    return trees.TreeModel("forecast", "rf", _small_rf, GRID)


@pytest.fixture(scope="module")
def trained():
    daily = synthetic_daily(n=1700)
    models = {
        lead: forecast.train_final(daily, lead, small_forest) for lead in (1, 2, 3)
    }
    return daily, models


def known_on(daily: pd.DataFrame, origin: str) -> pd.DataFrame:
    return forecast.known_at(daily, origin)


def test_save_and_load_round_trip(trained, tmp_path):
    daily, models = trained
    path = forecast.save(models, tmp_path, ROOT, None)
    card = json.loads((path / "model_card.json").read_text())
    assert card["leads_days"] == [1, 2, 3]
    assert card["last_training_target_date"] == str(daily.index.max().date())
    assert "known_limits" in card
    service = forecast.ForecastService.load(path)
    origin = "2025-03-01"
    table = known_on(daily, origin)
    a = forecast.ForecastService(models, card).forecast(table, origin)
    b = service.forecast(table, origin)
    assert a["forecasts"].keys() == b["forecasts"].keys() == {1, 2, 3}
    assert a["forecasts"][1]["forecast"] == b["forecasts"][1]["forecast"]


def test_forecast_output_is_consistent(trained):
    daily, models = trained
    service = forecast.ForecastService(
        models, {"version": "test", "leads_days": [1, 2, 3]}
    )
    out = service.forecast(known_on(daily, "2025-03-01"), "2025-03-01")
    assert out["problems"] == []
    for lead, f in out["forecasts"].items():
        assert f["target_date"] == str(
            (pd.Timestamp("2025-03-01") + pd.Timedelta(days=lead)).date()
        )
        lo, hi = f["interval_90"]
        lo80, hi80 = f["interval_80"]
        assert lo <= lo80 <= f["forecast"] <= hi80 <= hi
        assert 0 <= f["probability_at_least_55_5"]["conformal"] <= 1
        assert (
            f["probability_at_least_35_5"]["platt"]
            >= f["probability_at_least_55_5"]["platt"] - 1e-9
        )


def test_forecast_ignores_everything_after_the_origin(trained):
    daily, models = trained
    service = forecast.ForecastService(
        models, {"version": "test", "leads_days": [1, 2, 3]}
    )
    origin = "2025-03-01"
    clean = service.forecast(known_on(daily, origin), origin)
    # the full table also holds later PM2.5 and weather, which must not matter
    full = daily.loc[: pd.Timestamp(origin) + pd.Timedelta(days=3)].copy()
    full = full.copy()
    full.loc[full.index > origin, "pm25_mean"] = 999.0
    again = service.forecast(full, origin)
    for lead in (1, 2, 3):
        assert (
            clean["forecasts"][lead]["forecast"] == again["forecasts"][lead]["forecast"]
        )


def test_missing_origin_value_and_target_rows_are_reported(trained):
    daily, models = trained
    service = forecast.ForecastService(
        models, {"version": "test", "leads_days": [1, 2, 3]}
    )
    table = known_on(daily, "2025-03-01")
    table.loc["2025-03-01", "pm25_mean"] = np.nan
    out = service.forecast(table, "2025-03-01")
    assert any("origin day" in p for p in out["problems"])
    short = known_on(daily, "2025-03-01").loc[:"2025-03-02"]
    out = service.forecast(short, "2025-03-01")
    assert set(out["forecasts"]) == {1}
    assert any("target day" in p for p in out["problems"])


def test_training_needs_enough_history():
    daily = synthetic_daily(n=600)
    with pytest.raises(ValueError):
        forecast.train_final(daily, 1, small_forest)


def test_cutoff_keeps_later_targets_out_of_training():
    daily = synthetic_daily(n=1700)
    full = forecast.train_final(daily, 1, small_forest)
    early = forecast.train_final(daily, 1, small_forest, cutoff="2024-12-31")
    assert early.last_target_date == pd.Timestamp("2024-12-31")
    assert early.n_train < full.n_train
    changed = daily.copy()
    changed.loc[changed.index > "2024-12-31", "pm25_mean"] = 500.0
    again = forecast.train_final(changed, 1, small_forest, cutoff="2024-12-31")
    table = known_on(daily, "2025-03-01")
    a = forecast.ForecastService({1: early}, {"version": "t"}).forecast(
        table, "2025-03-01"
    )
    b = forecast.ForecastService({1: again}, {"version": "t"}).forecast(
        table, "2025-03-01"
    )
    assert a["forecasts"][1]["forecast"] == b["forecasts"][1]["forecast"]
