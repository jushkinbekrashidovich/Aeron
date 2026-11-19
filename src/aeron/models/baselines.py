"""Baseline forecasts for the daily mean PM2.5.

Each model has ``fit(train, context)`` and ``predict(test, context)`` and works on
rows of the feature table built by ``aeron.features.build_features`` (one row per
forecast origin). ``train`` only ever contains rows whose target day is on or before
the block's training cutoff, so nothing here can see the test period.

Naive forecasts need no fitting and are the bar a model has to clear:

- ``persistence``     today's daily mean
- ``mean_7d``         mean of the last 7 days
- ``climatology``     mean of training targets within +/- 15 days of the same day of year
- ``seasonal_naive``  the daily mean of the same date one year earlier (day - 365)

Linear models (ridge regression, with a penalty chosen on a validation period) are
fitted with and without weather features. Weather enters only through the feature sets
of ``aeron.features``. Missing predictors are filled by ``TrainOnlyImputer`` (median and
missing indicators fitted on the training rows only), and predictions are never below 0.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.preprocessing import StandardScaler

from aeron.evaluation.splits import train_validation_split
from aeron.features import feature_columns, observed_as_forecast
from aeron.imputation import TrainOnlyImputer

CLIMATOLOGY_WINDOW_DAYS = 15
RIDGE_ALPHAS = (1.0, 10.0, 100.0, 1000.0)
VALIDATION_DAYS = 365


@dataclass
class Context:
    """What a model may use besides the rows: lead time, the first test day and the series so far."""

    lead: int
    test_start: pd.Timestamp
    daily_mean: (
        pd.Series
    )  # daily PM2.5 by local date, for lookups of days before the origin


class Persistence:
    name = "persistence"
    uses_weather = False

    def fit(self, train: pd.DataFrame, context: Context) -> Persistence:
        return self

    def predict(self, test: pd.DataFrame, context: Context) -> np.ndarray:
        return test["y_origin"].to_numpy(dtype=float)


class Mean7Days:
    name = "mean_7d"
    uses_weather = False

    def fit(self, train: pd.DataFrame, context: Context) -> Mean7Days:
        return self

    def predict(self, test: pd.DataFrame, context: Context) -> np.ndarray:
        return test["hist_pm_roll7_mean"].to_numpy(dtype=float)


class Climatology:
    """Mean of training targets within a window around the same day of the year."""

    name = "climatology"
    uses_weather = False

    def __init__(self, window_days: int = CLIMATOLOGY_WINDOW_DAYS) -> None:
        self.window_days = window_days
        self._doy = np.array([])
        self._y = np.array([])

    def fit(self, train: pd.DataFrame, context: Context) -> Climatology:
        known = train[train["y"].notna()]
        self._doy = pd.DatetimeIndex(known["target_date"]).day_of_year.to_numpy()
        self._y = known["y"].to_numpy(dtype=float)
        return self

    def predict(self, test: pd.DataFrame, context: Context) -> np.ndarray:
        doy = pd.DatetimeIndex(test["target_date"]).day_of_year.to_numpy()
        diff = np.abs(doy[:, None] - self._doy[None, :])
        diff = np.minimum(diff, 365 - diff)  # circular distance in days
        inside = diff <= self.window_days
        counts = inside.sum(axis=1)
        sums = (inside * self._y[None, :]).sum(axis=1)
        return np.where(counts > 0, sums / np.maximum(counts, 1), np.nan)


class SeasonalNaive:
    """The daily mean of the same date one year earlier, which is already known at the origin."""

    name = "seasonal_naive"
    uses_weather = False

    def fit(self, train: pd.DataFrame, context: Context) -> SeasonalNaive:
        return self

    def predict(self, test: pd.DataFrame, context: Context) -> np.ndarray:
        last_year = pd.DatetimeIndex(test["target_date"]) - pd.Timedelta(days=365)
        return context.daily_mean.reindex(last_year).to_numpy(dtype=float)


@dataclass
class RidgeModel:
    """Ridge regression on a feature set, with a penalty picked on the last year of training."""

    feature_set: str
    label: str
    alphas: tuple[float, ...] = RIDGE_ALPHAS
    name: str = field(init=False)
    uses_weather: bool = field(init=False)

    def __post_init__(self) -> None:
        self.name = self.label
        self.uses_weather = self.feature_set != "history"
        self._columns: list[str] = []
        self._imputer: TrainOnlyImputer | None = None
        self._scaler = StandardScaler()
        self._model: Ridge | None = None
        self.chosen_alpha: float | None = None

    def _matrix(
        self, rows: pd.DataFrame, fit: bool, cutoff: pd.Timestamp | None = None
    ) -> np.ndarray:
        x = rows[self._columns].astype(float)
        x.index = pd.DatetimeIndex(rows["target_date"])
        if fit:
            self._imputer = TrainOnlyImputer(cutoff).fit(x)
            filled = self._imputer.transform(x)
            return self._scaler.fit_transform(filled)
        return self._scaler.transform(self._imputer.transform(x))

    def fit(self, train: pd.DataFrame, context: Context) -> RidgeModel:
        train = observed_as_forecast(
            train[train["y"].notna()]
        )  # observed weather stands in for the forecast
        self._columns = feature_columns(list(train.columns), self.feature_set)
        x = self._matrix(train, fit=True, cutoff=context.test_start)
        y = train["y"].to_numpy(dtype=float)
        fit_idx, val_idx = train_validation_split(
            train["target_date"], VALIDATION_DAYS, context.lead
        )
        best, best_mae = self.alphas[0], np.inf
        for alpha in self.alphas:
            pred = Ridge(alpha=alpha).fit(x[fit_idx], y[fit_idx]).predict(x[val_idx])
            mae = float(np.mean(np.abs(np.clip(pred, 0, None) - y[val_idx])))
            if mae < best_mae:
                best, best_mae = alpha, mae
        self.chosen_alpha = best
        self._model = Ridge(alpha=best).fit(x, y)
        return self

    def predict(self, test: pd.DataFrame, context: Context) -> np.ndarray:
        return np.clip(self._model.predict(self._matrix(test, fit=False)), 0, None)


def default_models() -> list:
    """The baselines compared in notebook 06."""
    return [
        Persistence(),
        Mean7Days(),
        Climatology(),
        SeasonalNaive(),
        RidgeModel("history", "ridge_history"),
        RidgeModel("forecast", "ridge_forecast_weather"),
        RidgeModel("forecast_no_wind", "ridge_forecast_no_wind"),
    ]
