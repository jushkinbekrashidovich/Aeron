"""Run models over the walk-forward blocks and collect their predictions.

For every block the models are fitted on rows whose target day is on or before the
block's training cutoff and predict the block's rows. Two test views exist:

- ``"observed"``: models that use weather get the weather that happened on the target
  day in the forecast columns. This is a perfect-forecast scenario (an upper bound) and
  it covers the whole record.
- ``"forecast"``: models get the archived forecast. Only rows that have one are scored
  (from 2024), and all models are scored on exactly those rows.

All models in a run are scored on identical rows (a target and today's value exist).
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from aeron.evaluation.splits import Block, walk_forward
from aeron.features import build_features, observed_as_forecast
from aeron.models.baselines import Context


def run_models(
    daily: pd.DataFrame,
    models: list,
    lead: int,
    blocks: list[Block],
    view: str = "observed",
    min_train_days: int = 365,
) -> pd.DataFrame:
    """Predictions of every model for every test row, one row per origin and block."""
    if view not in ("observed", "forecast"):
        raise ValueError("view must be 'observed' or 'forecast'")
    table = build_features(daily, lead)
    scored = table["y"].notna() & table["y_origin"].notna()
    if view == "forecast":
        scored &= table["wxf_temp_mean"].notna()
    daily_mean = daily["pm25_mean"].copy()
    daily_mean.index = pd.DatetimeIndex(daily_mean.index)
    parts = []
    # Splits come from all rows with a target (training uses them); scoring uses the stricter mask.
    candidates = table[table["y"].notna()].reset_index(drop=True)
    for split in walk_forward(
        candidates["target_date"], blocks, lead, min_train_days=min_train_days
    ):
        train = candidates.iloc[split.train]
        test = candidates.iloc[split.test]
        test = test[test["y_origin"].notna()]
        if view == "forecast":
            test = test[test["wxf_temp_mean"].notna()]
        elif view == "observed":
            test = observed_as_forecast(test)
        if test.empty:
            continue
        context = Context(
            lead=lead, test_start=pd.Timestamp(split.block.start), daily_mean=daily_mean
        )
        out = test[["origin_date", "target_date", "y"]].copy()
        out["block"] = split.block.name
        out["season"] = split.block.season
        out["lead"] = lead
        for model in models:
            model.fit(train, context)
            out[model.name] = model.predict(test, context)
        parts.append(out)
    if not parts:
        return pd.DataFrame()
    result = pd.concat(parts, ignore_index=True)
    assert scored.sum() >= len(result)  # every scored row came from the feature table
    return result


def common_rows(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """Keep only rows where every listed prediction exists, so models are compared on the same rows."""
    return frame.dropna(subset=["y", *columns]).reset_index(drop=True)


def last_date(daily: pd.DataFrame) -> date:
    return pd.DatetimeIndex(daily.index).max().date()


def nan_share(frame: pd.DataFrame, columns: list[str]) -> dict[str, float]:
    return {c: float(np.mean(frame[c].isna())) for c in columns}
