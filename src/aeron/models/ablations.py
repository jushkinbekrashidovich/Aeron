"""Model variants for the ablations of task 3.4.4.

Two questions are tested on one booster (LightGBM, forecast feature set):

- RQ3, how much PM2.5 history is needed: the number of daily lags and whether the
  rolling statistics are kept (``lag_window_models``).
- whether correcting the forecast wind for its bias helps PM2.5 forecasts
  (``wind_bias_models``). The correction is a ratio fitted on training days only, so it
  is meaningful only in the real-forecast test view. In the observed view the "forecast"
  already is the observation.

Weather on or off is covered by the ``history`` and ``forecast`` feature sets of
``aeron.models.trees``.
"""

from __future__ import annotations

from collections.abc import Callable

from aeron.models.trees import BOOST_GRID, TreeModel, _lightgbm

ROLLING = (
    "hist_pm_roll7_mean",
    "hist_pm_roll14_mean",
    "hist_pm_roll7_std",
    "hist_pm_roll7_max",
    "hist_pm_delta1",
    "hist_pm_trend7",
)


def lag_filter(max_lags: int, rolling: bool) -> Callable[[list[str]], list[str]]:
    """Keep PM2.5 lags 0 to ``max_lags - 1`` and, if asked, the rolling statistics.

    Same-day statistics (``hist_day_*``) and every non-history column are kept.
    """
    drop_lags = {f"hist_pm_lag{k}" for k in range(max_lags, 30)}

    def keep(columns: list[str]) -> list[str]:
        return [
            c for c in columns if c not in drop_lags and (rolling or c not in ROLLING)
        ]

    return keep


# (label, number of lags, rolling statistics)
LAG_VARIANTS = (
    ("lags1", 1, False),
    ("lags3", 3, False),
    ("lags7", 7, False),
    ("lags7_rolling", 7, True),
)


def lag_window_models(seed: int = 0) -> list[TreeModel]:
    return [
        TreeModel(
            "forecast",
            f"lgbm_{label}",
            _lightgbm,
            BOOST_GRID,
            seed,
            columns_filter=lag_filter(lags, rolling),
        )
        for label, lags, rolling in LAG_VARIANTS
    ]


def wind_bias_models(seed: int = 0) -> list[TreeModel]:
    """LightGBM on the forecast set without and with the wind ratio correction."""
    return [
        TreeModel("forecast", "lgbm_wind_raw", _lightgbm, BOOST_GRID, seed),
        TreeModel(
            "forecast",
            "lgbm_wind_corrected",
            _lightgbm,
            BOOST_GRID,
            seed,
            wind_bias=True,
        ),
    ]
