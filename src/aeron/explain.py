"""Explanations of a fitted tree model (task 4.2).

Two views of which inputs matter:

- ``contributions``: exact TreeSHAP values from LightGBM (``pred_contrib=True``), one
  number per row and input, in ug/m3. For each row they add up, together with
  ``base_value``, to the model's raw prediction (before it is clipped at 0).
- ``permutation_importance``: the rise in mean absolute error on the test rows when one
  input is shuffled, which shows how much the model relies on it for accuracy.

Both describe what the *model* uses. They are associations in the data the model was
trained on and do not show that an input causes PM2.5 to change.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from aeron.features import observed_as_forecast

GROUPS = {
    "hist_": "PM2.5 history",
    "time_": "calendar",
    "wxo_": "weather observed up to today",
    "wxf_": "forecast weather for the target day",
    "wxt_": "weather on the target day (not forecastable)",
}


def group_of(name: str) -> str:
    """Feature group of an input, including its missing-value indicator."""
    base = name.removesuffix("__was_missing")
    for prefix, label in GROUPS.items():
        if base.startswith(prefix):
            return label
    return "other"


def _matrix(model, rows: pd.DataFrame, observed: bool) -> np.ndarray:
    rows = observed_as_forecast(rows) if observed else rows
    return model._matrix(rows, fit=False)


def contributions(model, rows: pd.DataFrame, observed: bool = False) -> pd.DataFrame:
    """TreeSHAP values of a fitted LightGBM ``TreeModel`` on ``rows``.

    Set ``observed`` for the observed-weather view, where the forecast columns hold the
    observed values (the same switch as in ``run_models``).
    """
    x = _matrix(model, rows, observed)
    values = model._model.predict(x, pred_contrib=True)
    out = pd.DataFrame(
        values, columns=[*model._model_columns, "base_value"], index=rows.index
    )
    return out


def mean_abs_contribution(contrib: pd.DataFrame) -> pd.Series:
    return (
        contrib.drop(columns="base_value")
        .abs()
        .mean()
        .sort_values(ascending=False)
        .rename("mean_abs_shap")
    )


def permutation_importance(
    model,
    rows: pd.DataFrame,
    observed: bool = False,
    n_repeats: int = 5,
    seed: int = 0,
) -> pd.Series:
    """Mean rise in absolute error when each input column is shuffled across the rows."""
    x = _matrix(model, rows, observed)
    y = rows["y"].to_numpy(dtype=float)
    rng = np.random.default_rng(seed)

    def mae(matrix: np.ndarray) -> float:
        return float(np.mean(np.abs(model._back(model._model.predict(matrix)) - y)))

    base = mae(x)
    gains = {}
    for j, name in enumerate(model._model_columns):
        deltas = []
        for _ in range(n_repeats):
            shuffled = x.copy()
            shuffled[:, j] = rng.permutation(shuffled[:, j])
            deltas.append(mae(shuffled) - base)
        gains[name] = float(np.mean(deltas))
    return pd.Series(gains, name="permutation_gain").sort_values(ascending=False)


def by_group(values: pd.Series) -> pd.Series:
    """Sum an importance series by feature group."""
    return values.groupby([group_of(n) for n in values.index]).sum()


def explain_blocks(daily: pd.DataFrame, make_model, lead: int, blocks, view: str):
    """Fit ``make_model()`` on every walk-forward block and explain its test rows.

    Uses the same rows, split and views as ``aeron.evaluation.runner.run_models``.
    Returns ``(contributions, permutation, rows)``: SHAP values for all test rows with the
    columns ``block`` and ``season`` added; permutation importance with one row per block;
    and the test rows themselves (feature values, target and origin date).
    """
    from aeron.evaluation.splits import walk_forward
    from aeron.features import build_features
    from aeron.models.baselines import Context

    if view not in ("observed", "forecast"):
        raise ValueError("view must be 'observed' or 'forecast'")
    table = build_features(daily, lead)
    series = daily["pm25_mean"].copy()
    series.index = pd.DatetimeIndex(series.index)
    candidates = table[table["y"].notna()].reset_index(drop=True)
    contribs, perms, rows = [], {}, []
    for split in walk_forward(candidates["target_date"], blocks, lead):
        train = candidates.iloc[split.train]
        test = candidates.iloc[split.test]
        test = test[test["y_origin"].notna()]
        if view == "forecast":
            test = test[test["wxf_temp_mean"].notna()]
        if test.empty:
            continue
        context = Context(
            lead=lead, test_start=pd.Timestamp(split.block.start), daily_mean=series
        )
        model = make_model().fit(train, context)
        observed = view == "observed"
        contrib = contributions(model, test, observed=observed)
        contrib["block"] = split.block.name
        contrib["season"] = split.block.season
        contribs.append(contrib)
        perms[split.block.name] = permutation_importance(model, test, observed=observed)
        shown = observed_as_forecast(test) if observed else test
        rows.append(shown.assign(block=split.block.name, season=split.block.season))
    return (
        pd.concat(contribs),
        pd.DataFrame(perms),
        pd.concat(rows),
    )
