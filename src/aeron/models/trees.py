"""Tree-ensemble forecasts of the daily mean PM2.5.

Same interface and rules as ``aeron.models.baselines``: ``fit(train, context)`` sees only
rows whose target day is on or before the block's training cutoff, observed weather
stands in for the archived forecast during training (``observed_as_forecast``), missing
predictors are filled by ``TrainOnlyImputer``, and hyper-parameters are chosen on the
last training year with a gap equal to the lead (``train_validation_split``).

The final model is refitted on all training rows with the chosen setting. Predictions
are never below 0. Tree models cannot extrapolate beyond the training range, so very
high days are usually underpredicted; that shows up in the bias and event metrics.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor

from aeron.evaluation.splits import train_validation_split
from aeron.features import feature_columns, observed_as_forecast
from aeron.imputation import TrainOnlyImputer
from aeron.models.baselines import Context

VALIDATION_DAYS = 365
RF_GRID = tuple(
    {"max_depth": depth, "min_samples_leaf": leaf}
    for depth in (6, 12)
    for leaf in (5, 20)
)


@dataclass
class TreeModel:
    """A tree ensemble on a feature set, with settings picked on the last training year."""

    feature_set: str
    label: str
    make: Callable[[dict, int], object]
    grid: Sequence[dict]
    seed: int = 0
    log_target: bool = False
    name: str = field(init=False)
    uses_weather: bool = field(init=False)

    def __post_init__(self) -> None:
        self.name = self.label
        self.uses_weather = self.feature_set != "history"
        self._columns: list[str] = []
        self._imputer: TrainOnlyImputer | None = None
        self._model = None
        self.chosen: dict | None = None

    def _matrix(
        self, rows: pd.DataFrame, fit: bool, cutoff: pd.Timestamp | None = None
    ) -> np.ndarray:
        x = rows[self._columns].astype(float)
        x.index = pd.DatetimeIndex(rows["target_date"])
        if fit:
            self._imputer = TrainOnlyImputer(cutoff).fit(x)
        return self._imputer.transform(x).to_numpy(dtype=float)

    def _target(self, y: np.ndarray) -> np.ndarray:
        return np.log1p(y) if self.log_target else y

    def _back(self, pred: np.ndarray) -> np.ndarray:
        pred = np.expm1(pred) if self.log_target else pred
        return np.clip(pred, 0, None)

    def fit(self, train: pd.DataFrame, context: Context) -> TreeModel:
        train = observed_as_forecast(train[train["y"].notna()])
        self._columns = feature_columns(list(train.columns), self.feature_set)
        x = self._matrix(train, fit=True, cutoff=context.test_start)
        y = train["y"].to_numpy(dtype=float)
        fit_idx, val_idx = train_validation_split(
            train["target_date"], VALIDATION_DAYS, context.lead
        )
        best, best_mae = self.grid[0], np.inf
        for params in self.grid:
            model = self.make(params, self.seed)
            model.fit(x[fit_idx], self._target(y[fit_idx]))
            pred = self._back(model.predict(x[val_idx]))
            mae = float(np.mean(np.abs(pred - y[val_idx])))
            if mae < best_mae:
                best, best_mae = params, mae
        self.chosen = dict(best)
        self._model = self.make(best, self.seed)
        self._model.fit(x, self._target(y))
        return self

    def predict(self, test: pd.DataFrame, context: Context) -> np.ndarray:
        return self._back(self._model.predict(self._matrix(test, fit=False)))

    def importances(self) -> pd.Series:
        values = getattr(self._model, "feature_importances_", None)
        if values is None:
            return pd.Series(dtype=float)
        return pd.Series(values, index=self._columns).sort_values(ascending=False)


def _random_forest(params: dict, seed: int) -> RandomForestRegressor:
    return RandomForestRegressor(
        n_estimators=300,
        max_features=0.5,
        n_jobs=-1,
        random_state=seed,
        **params,
    )


def random_forest(feature_set: str, label: str, seed: int = 0) -> TreeModel:
    return TreeModel(feature_set, label, _random_forest, RF_GRID, seed)


def random_forest_models() -> list[TreeModel]:
    """Random forests on the same feature sets as the ridge baselines."""
    return [
        random_forest("history", "rf_history"),
        random_forest("forecast", "rf_forecast_weather"),
        random_forest("forecast_no_wind", "rf_forecast_no_wind"),
    ]
