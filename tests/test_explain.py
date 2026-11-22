import numpy as np
import pandas as pd
import pytest

from aeron import explain
from aeron.models import trees
from tests.test_models_trees import context, split_rows, synthetic_daily

pytest.importorskip("lightgbm")


def fitted():
    daily = synthetic_daily()
    train, test = split_rows(daily)
    ctx = context(daily)
    model = trees.TreeModel(
        "forecast",
        "lgbm",
        trees._lightgbm,
        ({"max_depth": 3, "learning_rate": 0.1},),
    ).fit(train, ctx)
    return model, test, ctx


def test_contributions_add_up_to_the_raw_prediction():
    model, test, _ = fitted()
    contrib = explain.contributions(model, test, observed=False)
    raw = model._model.predict(model._matrix(test, fit=False))
    assert contrib.sum(axis=1).to_numpy() == pytest.approx(raw, abs=1e-6)
    assert "base_value" in contrib.columns


def test_mean_abs_contribution_ranks_columns():
    model, test, _ = fitted()
    ranked = explain.mean_abs_contribution(explain.contributions(model, test))
    assert ranked.is_monotonic_decreasing
    assert "base_value" not in ranked.index


def test_permutation_importance_finds_the_driving_input_and_is_reproducible():
    model, test, _ = fitted()
    a = explain.permutation_importance(model, test, n_repeats=3, seed=1)
    b = explain.permutation_importance(model, test, n_repeats=3, seed=1)
    assert a.equals(b)
    assert a.index[0] != "time_dow"
    assert a.iloc[0] > 0
    assert set(a.index) == set(model._model_columns)


def test_groups():
    assert explain.group_of("wxf_wind_mean") == "forecast weather for the target day"
    assert explain.group_of("hist_pm_lag0__was_missing") == "PM2.5 history"
    assert explain.group_of("zzz") == "other"
    s = pd.Series({"wxf_a": 1.0, "wxf_b": 2.0, "hist_x": 4.0})
    out = explain.by_group(s)
    assert out["forecast weather for the target day"] == 3.0
    assert np.isclose(out.sum(), 7.0)


def test_explain_blocks_returns_aligned_tables():
    from datetime import date

    from aeron.evaluation import splits

    daily = synthetic_daily()
    blocks = splits.seasonal_blocks(2022, date(2024, 1, 15))

    def make():
        return trees.TreeModel(
            "forecast",
            "lgbm",
            trees._lightgbm,
            ({"max_depth": 3, "learning_rate": 0.1},),
        )

    contrib, perm, rows = explain.explain_blocks(daily, make, 1, blocks, "observed")
    assert len(contrib) == len(rows)
    assert set(perm.columns) == set(contrib["block"])
    assert contrib["season"].isin(["winter", "other"]).all()
