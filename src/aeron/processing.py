"""Build the processed hourly and daily datasets from raw and cleaned data.

Inputs
------
- ``data/interim/openaq/us_embassy_pm25_flagged.csv`` (from scripts/clean_data.py)
- ``data/raw/openmeteo/`` ERA5 core and extra variables and archived forecasts

Outputs (``data/processed/``)
-----------------------------
- ``hourly_us_embassy.csv``: one row per UTC hour on the PM2.5 grid, with cleaned
  PM2.5, its flags, ERA5 weather (``era5_*``) and archived forecasts issued 2, 3
  and 4 days earlier (``fc_d2_*``, ``fc_d3_*``, ``fc_d4_*``).
- ``daily_us_embassy.csv``: one row per local day (Asia/Tashkent, UTC+5) with the
  daily PM2.5 statistics, ERA5 daily weather (``era5_*``) and daily weather from
  the forecast for lead k days (``fc_lead1_*`` to ``fc_lead3_*``, issued k + 1
  days ahead).
- ``metadata.json`` with the build time, inputs and parameters.

Nothing is imputed (see docs/datasets/missing_data_policy.md). Columns that are
only known with a delay are not created: each row contains observations of its own
hour or day, and the forecast columns hold forecasts that existed before the day.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from aeron.config import ROOT, load_config

PROCESSED = ROOT / "data" / "processed"
PRIMARY = "us_embassy_pm25"
FORECAST_MIN_HOURS = 22  # forecast hours needed for a daily weather aggregate
FLAG_COLUMNS = ["zero", "spike", "spike_extreme", "stuck"]

# Open-Meteo names used inside the daily aggregation.
FORECAST_RENAME = {
    "shortwave_radiation": "ex_ssr",
    "vapour_pressure_deficit": "ex_vpd",
    "pressure_msl": "ex_msl",
}
BASE_WEATHER = [
    "temperature_2m",
    "relative_humidity_2m",
    "precipitation",
    "surface_pressure",
    "cloud_cover",
    "wind_speed_10m",
    "wind_gusts_10m",
]


def add_weather(d: pd.DataFrame, g) -> pd.DataFrame:
    """Add daily weather aggregates (columns w_*) from a groupby of hourly data."""
    d["w_temp_mean"] = g["temperature_2m"].mean()
    d["w_temp_min"] = g["temperature_2m"].min()
    d["w_temp_max"] = g["temperature_2m"].max()
    d["w_rh_mean"] = g["relative_humidity_2m"].mean()
    d["w_wind_mean"] = g["wind_speed_10m"].mean()
    d["w_gust_max"] = g["wind_gusts_10m"].max()
    d["w_precip"] = g["precipitation"].sum()
    d["w_pres_mean"] = g["surface_pressure"].mean()
    d["w_cloud_mean"] = g["cloud_cover"].mean()
    d["w_ssr_sum"] = g["ex_ssr"].sum()
    d["w_vpd_mean"] = g["ex_vpd"].mean()
    d["w_msl_mean"] = g["ex_msl"].mean()
    d["w_msl_chg"] = d["w_msl_mean"].diff()
    d["w_snow"] = g["ex_snow"].max()
    d["w_rain3"] = d["w_precip"].rolling(3, min_periods=3).sum()
    return d


def read_hourly(path: Path) -> pd.DataFrame:
    """Read a raw hourly CSV with a UTC ``datetime_utc`` column, as naive UTC."""
    frame = pd.read_csv(path)
    frame["datetime_utc"] = pd.to_datetime(
        frame["datetime_utc"], utc=True
    ).dt.tz_localize(None)
    return frame.set_index("datetime_utc")


def utc_offset(cfg: dict) -> pd.Timedelta:
    return pd.Timedelta(hours=cfg["time"]["utc_offset_hours"])


def to_utc_string(index: pd.DatetimeIndex) -> pd.Index:
    return index.strftime("%Y-%m-%dT%H:%M:%SZ")


def era5_inputs(core: pd.DataFrame, extra: pd.DataFrame) -> pd.DataFrame:
    """Hourly ERA5 variables under the names ``add_weather`` expects."""
    h = core[BASE_WEATHER].copy()
    h["ex_ssr"] = extra["shortwave_radiation"]
    h["ex_vpd"] = extra["vapour_pressure_deficit"]
    h["ex_msl"] = extra["pressure_msl"]
    h["ex_snow"] = extra["snow_depth"]
    h["ex_blh"] = extra["boundary_layer_height"]
    h["ex_vent"] = extra["boundary_layer_height"] * core["wind_speed_10m"]  # km/h x m
    return h


def forecast_inputs(forecast: pd.DataFrame, days_ahead: int) -> pd.DataFrame:
    """Hourly forecast variables issued ``days_ahead`` days earlier, under ``add_weather`` names."""
    h = pd.DataFrame(index=forecast.index)
    for name in BASE_WEATHER:
        h[name] = forecast[f"{name}_previous_day{days_ahead}"]
    for src, dst in FORECAST_RENAME.items():
        h[dst] = forecast[f"{src}_previous_day{days_ahead}"]
    h["ex_snow"] = np.nan  # no archived forecast of snow depth
    return h


def daily_weather(
    hourly_inputs: pd.DataFrame,
    offset: pd.Timedelta,
    min_hours: int = 0,
    blh: bool = False,
) -> pd.DataFrame:
    """Daily weather aggregates over local days. Days with too few hours are dropped."""
    h = hourly_inputs.copy()
    h.index = h.index + offset
    g = h.groupby(h.index.floor("D"))
    d = pd.DataFrame(index=g.size().index)
    add_weather(d, g)
    if blh:
        d["b_blh_mean"] = g["ex_blh"].mean()
        d["b_blh_min"] = g["ex_blh"].min()
        d["b_vent_mean"] = g["ex_vent"].mean()
    hours = g["temperature_2m"].count()
    return d[hours >= min_hours]


def forecast_weather_daily(
    forecast: pd.DataFrame, lead_days: int, offset: pd.Timedelta
) -> pd.DataFrame:
    """Daily weather from the forecast issued ``lead_days + 1`` days earlier."""
    return daily_weather(
        forecast_inputs(forecast, lead_days + 1), offset, FORECAST_MIN_HOURS
    )


def daily_pm25(pm: pd.Series, offset: pd.Timedelta, min_hours: int) -> pd.DataFrame:
    """Daily PM2.5 statistics over local days; a day needs ``min_hours`` observed hours."""
    local = pm.copy()
    local.index = local.index + offset
    days = local.index.floor("D")
    g = local.groupby(days)
    count = g.count()
    out = pd.DataFrame(index=count.index)
    out["pm25_hours"] = count
    out["pm25_mean"] = g.mean().where(count >= min_hours)
    out["pm25_max"] = g.max().where(count >= min_hours)
    evening = local[local.index.hour >= 18]
    eg = evening.groupby(evening.index.floor("D"))
    out["pm25_eve_mean"] = eg.mean().where(eg.count() >= 4)
    return out


def read_flagged(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    frame["datetime_utc"] = pd.to_datetime(
        frame["datetime_utc"], utc=True
    ).dt.tz_localize(None)
    return frame.set_index("datetime_utc")


def build_hourly(
    flagged: pd.DataFrame,
    core: pd.DataFrame,
    extra: pd.DataFrame,
    forecast: pd.DataFrame,
    cfg: dict,
) -> pd.DataFrame:
    grid = flagged.index
    out = pd.DataFrame(index=grid)
    out["pm25"] = flagged["value_clean"]
    out["pm25_raw"] = flagged["value_raw"]
    for flag in FLAG_COLUMNS:
        out[f"flag_{flag}"] = flagged[flag].astype(int)
    for col in cfg["openmeteo"]["core_variables"]:
        out[f"era5_{col}"] = core[col].reindex(grid)
    for col in cfg["openmeteo"]["extra_variables"]:
        out[f"era5_{col}"] = extra[col].reindex(grid)
    fc = cfg["openmeteo"]["forecast"]
    for n in fc["previous_days"]:
        for var in fc["variables"]:
            out[f"fc_d{n}_{var}"] = forecast[f"{var}_previous_day{n}"].reindex(grid)
    return out


def build_daily(
    hourly: pd.DataFrame,
    core: pd.DataFrame,
    extra: pd.DataFrame,
    forecast: pd.DataFrame,
    cfg: dict,
) -> pd.DataFrame:
    offset = utc_offset(cfg)
    min_hours = cfg["time"]["min_hours_for_daily_mean"]
    d = daily_pm25(hourly["pm25"], offset, min_hours)
    # Keep the span from the first to the last local day with any valid PM2.5 hour.
    # Edge days with few hours stay in the table, and pm25_hours says how many hours back each mean.
    valid = hourly["pm25"].dropna().index
    first_day = (valid.min() + offset).floor("D")
    last_day = (valid.max() + offset).floor("D")
    d = d[(d.index >= first_day) & (d.index <= last_day)]
    era5 = daily_weather(era5_inputs(core, extra), offset, blh=True)
    era5 = era5.rename(columns=lambda c: "era5_" + c.split("_", 1)[1])
    d = d.join(era5, how="left")
    for k in cfg["target"]["lead_days"]:
        fw = forecast_weather_daily(forecast, k, offset).drop(
            columns="w_snow"
        )  # no forecast of snow depth
        fw = fw.rename(columns=lambda c, k=k: f"fc_lead{k}_" + c.split("_", 1)[1])
        d = d.join(fw, how="left")
    d.index.name = "date"
    return d


def write_csv(frame: pd.DataFrame, path: Path, utc: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    out = frame.copy()
    if utc:
        out.index = to_utc_string(out.index)
        out.index.name = "datetime_utc"
    else:
        out.index = out.index.strftime("%Y-%m-%d")
        out.index.name = "date"
    out.to_csv(path)


def build_all(
    raw_dir: Path | None = None,
    interim_dir: Path | None = None,
    out_dir: Path = PROCESSED,
    cfg: dict | None = None,
) -> dict:
    cfg = cfg or load_config()
    raw_dir = raw_dir or ROOT / "data" / "raw"
    interim_dir = interim_dir or ROOT / "data" / "interim"
    flagged_path = interim_dir / "openaq" / f"{PRIMARY}_flagged.csv"
    if not flagged_path.exists():
        raise FileNotFoundError(
            f"{flagged_path} not found: run scripts/clean_data.py first"
        )
    flagged = read_flagged(flagged_path)
    core = read_hourly(raw_dir / "openmeteo" / "era5_tashkent_hourly.csv")
    extra = read_hourly(raw_dir / "openmeteo" / "era5_extra_tashkent_hourly.csv")
    forecast = read_hourly(raw_dir / "openmeteo" / "forecast_previous_runs_hourly.csv")
    hourly = build_hourly(flagged, core, extra, forecast, cfg)
    daily = build_daily(hourly, core, extra, forecast, cfg)
    write_csv(hourly, out_dir / "hourly_us_embassy.csv", utc=True)
    write_csv(daily, out_dir / "daily_us_embassy.csv", utc=False)
    meta = {
        "built_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "station": PRIMARY,
        "utc_offset_hours": cfg["time"]["utc_offset_hours"],
        "min_hours_for_daily_mean": cfg["time"]["min_hours_for_daily_mean"],
        "forecast_min_hours": FORECAST_MIN_HOURS,
        "hourly": {
            "rows": len(hourly),
            "columns": len(hourly.columns),
            "first": hourly.index.min().isoformat(),
            "last": hourly.index.max().isoformat(),
            "pm25_valid": int(hourly["pm25"].notna().sum()),
        },
        "daily": {
            "rows": len(daily),
            "columns": len(daily.columns),
            "first": str(daily.index.min().date()),
            "last": str(daily.index.max().date()),
            "days_with_mean": int(daily["pm25_mean"].notna().sum()),
        },
        "inputs": {
            "flagged": str(flagged_path.relative_to(interim_dir.parent))
            if interim_dir.parent in flagged_path.parents
            else str(flagged_path),
            "era5_core_rows": len(core),
            "era5_extra_rows": len(extra),
            "forecast_rows": len(forecast),
        },
    }
    (out_dir / "metadata.json").write_text(json.dumps(meta, indent=2))
    return meta
