import numpy as np
import pandas as pd

from aeron.evaluation import splits
from aeron.evaluation.runner import run_models
from aeron.features import build_features
from aeron.models import trees
from tests.test_models_baselines import context, synthetic_daily

SMALL_GRID = ({"max_depth": 4, "min_samples_leaf": 5},)


def small_forest(feature_set="forecast", label="rf"):
    def make(params, seed):
        return trees.RandomForestRegressor(
            n_estimators=20, random_state=seed, n_jobs=1, **params
        )

    return trees.TreeModel(feature_set, label, make, SMALL_GRID)


def split_rows(daily, lead=1, test_start="2023-11-01"):
    table = build_features(daily, lead).dropna(subset=["y", "y_origin"])
    start = pd.Timestamp(test_start)
    train = table[table["target_date"] <= start - pd.Timedelta(days=lead)]
    test = table[table["target_date"] >= start].head(30)
    return train, test


def test_forest_predicts_finite_non_negative_values():
    daily = synthetic_daily()
    train, test = split_rows(daily)
    ctx = context(daily)
    model = small_forest().fit(train, ctx)
    pred = model.predict(test, ctx)
    assert len(pred) == len(test)
    assert np.isfinite(pred).all() and (pred >= 0).all()
    assert model.chosen == SMALL_GRID[0]


def test_forest_is_reproducible_with_the_same_seed():
    daily = synthetic_daily()
    train, test = split_rows(daily)
    ctx = context(daily)
    a = small_forest().fit(train, ctx).predict(test, ctx)
    b = small_forest().fit(train, ctx).predict(test, ctx)
    assert np.array_equal(a, b)


def test_forest_does_not_read_the_future():
    """Changing everything after the training cutoff must not change the fitted model."""
    daily = synthetic_daily()
    train, test = split_rows(daily)
    ctx = context(daily)
    base = small_forest().fit(train, ctx).predict(test, ctx)
    changed = daily.copy()
    after = changed.index >= pd.Timestamp("2023-11-01")
    changed.loc[after, "pm25_mean"] = 500.0
    train2, _ = split_rows(changed)
    again = small_forest().fit(train2, ctx).predict(test, ctx)
    assert np.array_equal(base, again)


def test_history_forest_has_no_weather_columns():
    daily = synthetic_daily()
    train, _ = split_rows(daily)
    model = small_forest("history", "rf_history").fit(train, context(daily))
    assert not any(c.startswith(("wx", "era5")) for c in model._columns)
    assert not model.uses_weather


def test_log_target_predictions_are_back_transformed():
    daily = synthetic_daily()
    train, test = split_rows(daily)
    ctx = context(daily)
    model = small_forest()
    model.log_target = True
    pred = model.fit(train, ctx).predict(test, ctx)
    assert pred.max() < 1000 and (pred >= 0).all()


def test_runs_through_the_walk_forward_runner():
    daily = synthetic_daily()
    blocks = splits.seasonal_blocks(2022, pd.Timestamp("2024-01-15").date())
    out = run_models(daily, [small_forest()], 1, blocks, "observed")
    assert not out.empty and out["rf"].notna().all()


def test_boosted_models_fit_and_predict():
    daily = synthetic_daily()
    train, test = split_rows(daily)
    ctx = context(daily)
    grid = ({"max_depth": 3, "learning_rate": 0.1},)
    for make in (trees._xgboost, trees._lightgbm):
        model = trees.TreeModel("forecast", "boost", make, grid)
        pred = model.fit(train, ctx).predict(test, ctx)
        assert len(pred) == len(test)
        assert np.isfinite(pred).all() and (pred >= 0).all()
        assert not model.importances().empty


def test_boosted_model_lists_have_distinct_names():
    names = [m.name for m in trees.boosted_models()]
    assert len(names) == len(set(names)) == 6
