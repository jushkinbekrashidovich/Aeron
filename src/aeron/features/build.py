"""Features for forecasting the daily mean PM2.5 ``lead`` days ahead.

Each row is one forecast origin O, the end of local day O. It holds only what is
known at that moment, and the target, the daily mean of day D = O + lead.

Groups of features
------------------
``hist``  history of PM2.5 up to and including day O (lags, rolling statistics)
``time``  calendar of the target day D (known in advance)
``wxo``   weather observed up to day O (day O and the day before)
``wxf``   archived weather forecast for the target day D, issued lead + 1 days
          before the valid hours, so it existed before the origin
``wxt``   weather that actually happened on the target day D. This is NOT available at
          the origin. It is a perfect-forecast scenario and only for upper-bound runs.

Feature sets (see FEATURE_SETS) combine groups. Headline models use ``forecast``.
Missing values stay missing (see docs/datasets/missing_data_policy.md). Boundary layer
height and snow depth have no archived forecast and are kept out of every set except
the upper bound.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

HISTORY_LAGS = range(7)
WINTER_MONTHS = (11, 12, 1, 2)

# Daily weather aggregates, named as in the processed daily table without the prefix.
FORECASTABLE = [
    "temp_mean",
    "temp_min",
    "temp_max",
    "rh_mean",
    "wind_mean",
    "gust_max",
    "wind_u",
    "wind_v",
    "precip",
    "pres_mean",
    "cloud_mean",
    "ssr_sum",
    "vpd_mean",
    "msl_mean",
    "msl_chg",
    "rain3",
]
OBSERVED_ORIGIN = [
    "temp_mean",
    "rh_mean",
    "wind_mean",
    "precip",
    "rain3",
    "msl_mean",
    "msl_chg",
]
UPPER_BOUND_ONLY = ["blh_mean", "blh_min", "vent_mean"]
WIND_RELATED = ("wind_mean", "gust_max", "wind_u", "wind_v")


def history_features(daily: pd.DataFrame) -> pd.DataFrame:
    """PM2.5 history known at the end of each day (every value looks backwards only)."""
    pm = daily["pm25_mean"]
    out = pd.DataFrame(index=daily.index)
    for lag in HISTORY_LAGS:
        out[f"hist_pm_lag{lag}"] = pm.shift(lag)
    out["hist_pm_roll7_mean"] = pm.rolling(7, min_periods=4).mean()
    out["hist_pm_roll14_mean"] = pm.rolling(14, min_periods=8).mean()
    out["hist_pm_roll7_std"] = pm.rolling(7, min_periods=4).std()
    out["hist_pm_roll7_max"] = pm.rolling(7, min_periods=4).max()
    out["hist_pm_delta1"] = pm - pm.shift(1)
    out["hist_pm_trend7"] = pm - out["hist_pm_roll7_mean"]
    out["hist_day_max"] = daily["pm25_max"]
    out["hist_day_evening_mean"] = daily["pm25_eve_mean"]
    out["hist_day_hours"] = daily["pm25_hours"]
    return out


def time_features(target_days: pd.DatetimeIndex) -> pd.DataFrame:
    """Calendar features of the target day, with cyclical encoding for the day of the year."""
    out = pd.DataFrame(index=target_days)
    angle = 2 * np.pi * target_days.day_of_year / 365.25
    out["time_doy_sin"] = np.sin(angle)
    out["time_doy_cos"] = np.cos(angle)
    out["time_month"] = target_days.month
    out["time_winter"] = target_days.month.isin(WINTER_MONTHS).astype(int)
    out["time_dow"] = target_days.day_of_week
    out["time_weekend"] = (target_days.day_of_week >= 5).astype(int)
    return out


def observed_origin_features(daily: pd.DataFrame) -> pd.DataFrame:
    """Weather observed on the origin day and the day before."""
    out = pd.DataFrame(index=daily.index)
    for name in OBSERVED_ORIGIN:
        series = daily[f"era5_{name}"]
        out[f"wxo_{name}_l0"] = series
        out[f"wxo_{name}_l1"] = series.shift(1)
    return out


def forecast_features(
    daily: pd.DataFrame, lead: int, target_days: pd.DatetimeIndex
) -> pd.DataFrame:
    """Archived forecast for the target day, taken from the row of the target day itself."""
    out = pd.DataFrame(index=daily.index)
    for name in FORECASTABLE:
        out[f"wxf_{name}"] = (
            daily[f"fc_lead{lead}_{name}"].reindex(target_days).to_numpy()
        )
    out["wxf_temp_range"] = out["wxf_temp_max"] - out["wxf_temp_min"]
    return out


def target_day_observed_features(
    daily: pd.DataFrame, target_days: pd.DatetimeIndex
) -> pd.DataFrame:
    """Weather that happened on the target day (not available at the origin)."""
    out = pd.DataFrame(index=daily.index)
    for name in FORECASTABLE + UPPER_BOUND_ONLY:
        out[f"wxt_{name}"] = daily[f"era5_{name}"].reindex(target_days).to_numpy()
    out["wxt_temp_range"] = out["wxt_temp_max"] - out["wxt_temp_min"]
    return out


def build_features(daily: pd.DataFrame, lead: int) -> pd.DataFrame:
    """Feature table with one row per origin day.

    ``daily`` is the processed daily table (index: local date). The result has the
    columns ``origin_date``, ``target_date``, ``y`` (daily mean of the target day) and
    ``y_origin`` (daily mean of the origin day), then every feature. Rows are not
    dropped: rows without a target or with missing features stay and the caller filters.
    """
    daily = daily.copy()
    daily.index = pd.DatetimeIndex(daily.index)
    full = pd.date_range(daily.index.min(), daily.index.max(), freq="D")
    daily = daily.reindex(full)
    target_days = daily.index + pd.Timedelta(days=lead)
    frame = pd.DataFrame(index=daily.index)
    frame["origin_date"] = daily.index
    frame["target_date"] = target_days
    frame["y"] = daily["pm25_mean"].reindex(target_days).to_numpy()
    frame["y_origin"] = daily["pm25_mean"]
    parts = [
        frame,
        history_features(daily),
        time_features(target_days).set_axis(daily.index),
        observed_origin_features(daily),
        forecast_features(daily, lead, target_days),
        target_day_observed_features(daily, target_days),
    ]
    return pd.concat(parts, axis=1)


def observed_as_forecast(frame: pd.DataFrame) -> pd.DataFrame:
    """Copy of the feature table where each forecast column holds the observed value instead.

    Archived forecasts exist for only about 13 months, so models are trained with the
    weather that happened (ERA5) standing in for the forecast, and tested on the real
    forecast columns (methodology, leakage rule 3). Variables with no forecast
    counterpart are untouched.
    """
    out = frame.copy()
    for name in FORECASTABLE + ["temp_range"]:
        out[f"wxf_{name}"] = frame[f"wxt_{name}"]
    return out


def _group(columns: list[str], *prefixes: str) -> list[str]:
    return [c for c in columns if c.startswith(prefixes)]


def feature_columns(frame_columns: list[str], set_name: str) -> list[str]:
    """Column names of a feature set, in table order."""
    cols = list(frame_columns)
    hist, time, wxo = _group(cols, "hist_"), _group(cols, "time_"), _group(cols, "wxo_")
    wxf, wxt = _group(cols, "wxf_"), _group(cols, "wxt_")
    no_wind = lambda names: [
        c
        for c in names
        if not c.removeprefix("wxf_").removeprefix("wxt_") in WIND_RELATED
    ]
    sets = {
        "history": hist + time,
        "history_weather_now": hist + time + wxo,
        "forecast": hist + time + wxo + wxf,
        "forecast_no_wind": hist + time + wxo + no_wind(wxf),
        "observed_upper_bound": hist + time + wxo + wxt,
    }
    if set_name not in sets:
        raise KeyError(f"unknown feature set {set_name!r}; choose from {sorted(sets)}")
    return sets[set_name]


FEATURE_SETS = (
    "history",
    "history_weather_now",
    "forecast",
    "forecast_no_wind",
    "observed_upper_bound",
)
