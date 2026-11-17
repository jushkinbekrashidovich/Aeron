"""First gradient boosting experiment for 24, 48 and 72 h PM2.5 forecasts.

Usage:
    python -m aeron.gbm_experiment

One model per lead time (direct forecasting). Target: hourly PM2.5 at the US
Embassy station at time t + h. Features are built from information available at
the forecast origin t, plus (variant B only) ERA5 weather at the target time.

Variant B uses reanalysis weather for the target hour, i.e. a perfect weather
forecast. It is an upper bound on what weather inputs can add, not an estimate
of operational skill. Real forecast weather is only available from 2024-01-19.

Split is chronological, same as baselines.py: train on targets before TEST_START,
test on targets in [TEST_START, TEST_END]. Hyperparameters are fixed in advance
and were not tuned on the test period. All methods are scored on the same rows,
those where both the origin value and the target value are observed.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

from aeron.baselines import TEST_END, TEST_START

ROOT = Path(__file__).resolve().parents[2]
PM_FILE = ROOT / "data" / "raw" / "openaq" / "us_embassy_pm25_hourly.csv"
WX_FILE = ROOT / "data" / "raw" / "openmeteo" / "era5_tashkent_hourly.csv"
LEADS = (24, 48, 72)
WEATHER = [
    "temperature_2m",
    "relative_humidity_2m",
    "precipitation",
    "surface_pressure",
    "cloud_cover",
    "wind_speed_10m",
    "wind_gusts_10m",
    "wind_u",
    "wind_v",
]
PARAMS = {
    "max_iter": 300,
    "learning_rate": 0.05,
    "max_depth": 6,
    "min_samples_leaf": 50,
    "l2_regularization": 1.0,
    "random_state": 0,
}


def load() -> pd.DataFrame:
    pm = pd.read_csv(PM_FILE, parse_dates=["datetime_utc"])
    pm["datetime_utc"] = pm["datetime_utc"].dt.tz_localize(None)  # naive UTC
    pm = pm.dropna(subset=["value"]).set_index("datetime_utc")["value"]
    wx = pd.read_csv(WX_FILE, parse_dates=["datetime_utc"])
    wx["datetime_utc"] = wx["datetime_utc"].dt.tz_localize(None)
    wx = wx.set_index("datetime_utc")
    # Wind direction is circular, so use components.
    rad = np.deg2rad(wx["wind_direction_10m"])
    wx["wind_u"] = -wx["wind_speed_10m"] * np.sin(rad)
    wx["wind_v"] = -wx["wind_speed_10m"] * np.cos(rad)
    index = pd.date_range(wx.index.min(), wx.index.max(), freq="h")
    df = wx.reindex(index)
    df["pm25"] = pm.reindex(index)
    return df


def origin_features(df: pd.DataFrame) -> pd.DataFrame:
    """Features known at origin time t (PM2.5 history only)."""
    y = df["pm25"]
    f = pd.DataFrame(index=df.index)
    for lag in (0, 1, 2, 3, 6, 12, 24, 48, 72, 168):
        f[f"pm_lag{lag}"] = y.shift(lag)
    roll = y.rolling(24, min_periods=18)
    f["pm_mean24"] = roll.mean()
    f["pm_max24"] = roll.max()
    f["pm_std24"] = roll.std()
    f["pm_mean168"] = y.rolling(168, min_periods=120).mean()
    return f


def build(df: pd.DataFrame, lead: int, with_weather: bool) -> pd.DataFrame:
    f = origin_features(df)
    target_time = df.index + pd.Timedelta(hours=lead)
    f["target_time"] = target_time
    f["hour_sin"] = np.sin(2 * np.pi * target_time.hour / 24)
    f["hour_cos"] = np.cos(2 * np.pi * target_time.hour / 24)
    f["month"] = target_time.month
    f["dow"] = target_time.day_of_week
    if with_weather:
        wx_target = df[WEATHER].shift(-lead)
        for col in WEATHER:
            f[f"wx_{col}"] = wx_target[col]
        f["wx_temp_change24"] = wx_target["temperature_2m"] - df["temperature_2m"]
    f["y"] = df["pm25"].shift(-lead)
    f["y_origin"] = df["pm25"]
    return f


def metrics(err: np.ndarray) -> tuple[float, float]:
    return float(np.mean(np.abs(err))), math.sqrt(float(np.mean(err**2)))


def main() -> None:
    df = load()
    clim_train = df[df.index < TEST_START]
    clim = clim_train.groupby([clim_train.index.month, clim_train.index.hour])["pm25"]
    clim = clim.mean()
    rows = []
    for lead in LEADS:
        data = {
            "A_lags": build(df, lead, False),
            "B_lags+ERA5": build(df, lead, True),
        }
        base = data["A_lags"]
        valid = base["y"].notna() & base["y_origin"].notna()
        in_train = valid & (base["target_time"] < TEST_START)
        in_test = valid & base["target_time"].between(TEST_START, TEST_END)
        test_t = base.loc[in_test, "target_time"]
        winter = test_t.dt.month.isin([11, 12, 1, 2]).to_numpy()
        truth = base.loc[in_test, "y"].to_numpy()

        preds = {
            "persistence": base.loc[in_test, "y_origin"].to_numpy(),
            "climatology": np.array(
                [clim.get((t.month, t.hour), np.nan) for t in test_t]
            ),
        }
        for name, feats in data.items():
            cols = [
                c for c in feats.columns if c not in ("y", "y_origin", "target_time")
            ]
            model = HistGradientBoostingRegressor(**PARAMS)
            model.fit(feats.loc[in_train, cols], feats.loc[in_train, "y"])
            preds[f"gbm_{name}"] = model.predict(feats.loc[in_test, cols])

        for name, p in preds.items():
            for group, mask in (
                ("all", np.ones_like(winter)),
                ("winter", winter),
                ("other", ~winter),
            ):
                ok = mask & ~np.isnan(p)
                mae, rmse = metrics(p[ok] - truth[ok])
                rows.append((name, lead, group, int(ok.sum()), mae, rmse))
    out = pd.DataFrame(rows, columns=["method", "lead_h", "group", "n", "MAE", "RMSE"])
    pd.set_option("display.width", 120)
    print(out.round(1).to_string(index=False))


if __name__ == "__main__":
    main()
