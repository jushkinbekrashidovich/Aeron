"""Gradient boosting with archived forecast weather instead of observed weather.

Usage:
    python -m aeron.gbm_forecast_weather

Repeats the gbm_experiment test, restricted to targets from 2024-01-19 onward
(the first day with archived multi-variable forecasts). Models are trained on
ERA5 weather before 2024-01-01, as before. At test time, variant B is scored
twice: once with ERA5 weather at the target hour (a perfect forecast) and once
with the forecast for that hour issued 2, 3 or 4 days earlier for leads of 24,
48 and 72 h (variant C). The difference is the cost of real forecast errors.
All methods are scored on identical rows.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

from aeron.baselines import TEST_END
from aeron.gbm_experiment import LEADS, PARAMS, WEATHER, build, load, metrics

ROOT = Path(__file__).resolve().parents[2]
FC_FILE = ROOT / "data" / "raw" / "openmeteo" / "forecast_previous_runs_hourly.csv"
TRAIN_END = pd.Timestamp("2024-01-01")
FC_START = pd.Timestamp("2024-01-19")


def load_forecast() -> pd.DataFrame:
    fc = pd.read_csv(FC_FILE, parse_dates=["datetime_utc"])
    fc["datetime_utc"] = fc["datetime_utc"].dt.tz_localize(None)
    return fc.set_index("datetime_utc")


def forecast_weather(fc: pd.DataFrame, lead: int) -> pd.DataFrame:
    """Forecast weather for each valid hour, issued lead/24 + 1 days earlier."""
    n = lead // 24 + 1
    out = pd.DataFrame(index=fc.index)
    for name in (
        "temperature_2m",
        "relative_humidity_2m",
        "precipitation",
        "surface_pressure",
        "cloud_cover",
        "wind_speed_10m",
        "wind_gusts_10m",
    ):
        out[name] = fc[f"{name}_previous_day{n}"]
    rad = np.deg2rad(fc[f"wind_direction_10m_previous_day{n}"])
    out["wind_u"] = -out["wind_speed_10m"] * np.sin(rad)
    out["wind_v"] = -out["wind_speed_10m"] * np.cos(rad)
    return out


def main() -> None:
    df = load()
    fc = load_forecast()
    clim_train = df[df.index < TRAIN_END]
    clim = clim_train.groupby([clim_train.index.month, clim_train.index.hour])["pm25"]
    clim = clim.mean()
    rows = []
    for lead in LEADS:
        a = build(df, lead, False)
        b = build(df, lead, True)
        # Variant C: same features as B, with forecast weather at the target hour.
        c = b.copy()
        fw = forecast_weather(fc, lead).reindex(c["target_time"])
        for col in WEATHER:
            c[f"wx_{col}"] = fw[col].to_numpy()
        c["wx_temp_change24"] = c["wx_temperature_2m"] - df["temperature_2m"]

        valid = a["y"].notna() & a["y_origin"].notna() & c["wx_temperature_2m"].notna()
        # Training rows need only ERA5 weather, not forecasts.
        in_train = (
            a["y"].notna() & a["y_origin"].notna() & (a["target_time"] < TRAIN_END)
        )
        in_test = valid & a["target_time"].between(FC_START, TEST_END)
        test_t = a.loc[in_test, "target_time"]
        winter = test_t.dt.month.isin([11, 12, 1, 2]).to_numpy()
        truth = a.loc[in_test, "y"].to_numpy()

        cols_a = [x for x in a.columns if x not in ("y", "y_origin", "target_time")]
        cols_b = [x for x in b.columns if x not in ("y", "y_origin", "target_time")]
        model_a = HistGradientBoostingRegressor(**PARAMS).fit(
            a.loc[in_train, cols_a], a.loc[in_train, "y"]
        )
        model_b = HistGradientBoostingRegressor(**PARAMS).fit(
            b.loc[in_train, cols_b], b.loc[in_train, "y"]
        )
        preds = {
            "persistence": a.loc[in_test, "y_origin"].to_numpy(),
            "climatology": np.array(
                [clim.get((t.month, t.hour), np.nan) for t in test_t]
            ),
            "gbm_A_lags": model_a.predict(a.loc[in_test, cols_a]),
            "gbm_B_ERA5_weather": model_b.predict(b.loc[in_test, cols_b]),
            "gbm_C_forecast_weather": model_b.predict(c.loc[in_test, cols_b]),
        }
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
