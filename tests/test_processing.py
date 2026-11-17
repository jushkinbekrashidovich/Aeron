import json

import numpy as np
import pandas as pd
import pytest

from aeron import processing
from aeron.config import load_config

OFFSET = pd.Timedelta(hours=5)


def hourly_series(values, start="2024-02-01 00:00"):
    index = pd.date_range(start, periods=len(values), freq="h")
    return pd.Series(values, index=index, dtype=float)


# --------------------------------------------------------------------------
# Daily PM2.5
# --------------------------------------------------------------------------
def test_local_day_starts_at_19_utc():
    pm = hourly_series([10.0] * 48, start="2024-02-01 00:00")
    daily = processing.daily_pm25(pm, OFFSET, 18)
    # 00:00 to 18:59 UTC on 1 Feb is local 1 Feb 05:00 to 23:59 (19 hours); 19:00 UTC starts 2 Feb.
    assert daily.loc["2024-02-01", "pm25_hours"] == 19
    assert daily.loc["2024-02-02", "pm25_hours"] == 24


def test_daily_mean_needs_enough_observed_hours():
    values = [20.0] * 24 + [30.0] * 24
    pm = hourly_series(values, start="2024-02-01 19:00")  # exactly two local days
    pm.iloc[:7] = np.nan  # day one keeps 17 hours
    pm.iloc[24:30] = np.nan  # day two keeps 18 hours
    daily = processing.daily_pm25(pm, OFFSET, 18)
    assert daily.loc["2024-02-02", "pm25_hours"] == 17 and np.isnan(
        daily.loc["2024-02-02", "pm25_mean"]
    )
    assert (
        daily.loc["2024-02-03", "pm25_hours"] == 18
        and daily.loc["2024-02-03", "pm25_mean"] == 30.0
    )
    assert daily.loc["2024-02-03", "pm25_max"] == 30.0


def test_evening_mean_uses_local_evening_hours():
    # Local 18:00 to 23:00 is 13:00 to 18:00 UTC.
    pm = hourly_series([0.0] * 24, start="2024-02-01 19:00")
    pm.loc["2024-02-02 13:00":"2024-02-02 18:00"] = 60.0
    daily = processing.daily_pm25(pm, OFFSET, 18)
    assert daily.loc["2024-02-02", "pm25_eve_mean"] == 60.0


def test_evening_mean_needs_four_hours():
    pm = hourly_series([5.0] * 24, start="2024-02-01 19:00")
    pm.loc["2024-02-02 13:00":"2024-02-02 16:00"] = np.nan  # leaves 2 evening hours
    daily = processing.daily_pm25(pm, OFFSET, 18)
    assert np.isnan(daily.loc["2024-02-02", "pm25_eve_mean"])


# --------------------------------------------------------------------------
# Daily weather and forecasts
# --------------------------------------------------------------------------
def weather_frame(hours, **overrides):
    index = pd.date_range(
        "2024-02-01 19:00", periods=hours, freq="h"
    )  # starts a local day
    h = pd.DataFrame(index=index)
    for name in processing.BASE_WEATHER:
        h[name] = 1.0
    h["temperature_2m"] = np.arange(hours, dtype=float)
    for name in ("ex_ssr", "ex_vpd", "ex_msl", "ex_snow", "ex_blh", "ex_vent"):
        h[name] = 1.0
    for k, v in overrides.items():
        h[k] = v
    return h


def test_daily_weather_aggregates_over_the_local_day():
    h = weather_frame(48, precipitation=0.5)
    d = processing.daily_weather(h, OFFSET)
    assert list(d.index) == [pd.Timestamp("2024-02-02"), pd.Timestamp("2024-02-03")]
    assert d.loc["2024-02-02", "w_temp_mean"] == pytest.approx(11.5)  # hours 0..23
    assert (
        d.loc["2024-02-02", "w_temp_min"] == 0
        and d.loc["2024-02-02", "w_temp_max"] == 23
    )
    assert d.loc["2024-02-03", "w_temp_mean"] == pytest.approx(
        35.5
    )  # hours 24..47 only
    assert d.loc["2024-02-02", "w_precip"] == pytest.approx(
        12.0
    )  # 24 x 0.5, not a rolling value


def test_daily_weather_drops_days_with_too_few_hours():
    d = processing.daily_weather(weather_frame(30), OFFSET, min_hours=22)
    assert list(d.index) == [pd.Timestamp("2024-02-02")]  # second day has 6 hours


def test_forecast_lead_uses_forecast_issued_lead_plus_one_days_earlier():
    index = pd.date_range("2024-02-01 19:00", periods=24, freq="h")
    forecast = pd.DataFrame(index=index)
    for n, base in ((2, 100.0), (3, 200.0), (4, 300.0)):
        for name in processing.BASE_WEATHER:
            forecast[f"{name}_previous_day{n}"] = base
        for name in ("shortwave_radiation", "vapour_pressure_deficit", "pressure_msl"):
            forecast[f"{name}_previous_day{n}"] = base
    lead1 = processing.forecast_weather_daily(forecast, 1, OFFSET)
    lead3 = processing.forecast_weather_daily(forecast, 3, OFFSET)
    assert lead1.loc["2024-02-02", "w_temp_mean"] == 100.0  # issued 2 days before
    assert lead3.loc["2024-02-02", "w_temp_mean"] == 300.0  # issued 4 days before
    assert lead1["w_snow"].isna().all()  # there is no forecast of snow depth


# --------------------------------------------------------------------------
# Whole build
# --------------------------------------------------------------------------
def write_hourly(path, index, columns, value):
    frame = pd.DataFrame({"datetime_utc": index.strftime("%Y-%m-%dT%H:%M:%SZ")})
    for position, name in enumerate(columns):
        frame[name] = value + position
    frame.to_csv(path, index=False)


@pytest.fixture
def workspace(tmp_path):
    cfg = load_config()
    raw = tmp_path / "raw" / "openmeteo"
    raw.mkdir(parents=True)
    interim = tmp_path / "interim" / "openaq"
    interim.mkdir(parents=True)
    weather_index = pd.date_range("2024-01-25", "2024-02-20 23:00", freq="h")
    om = cfg["openmeteo"]
    write_hourly(
        raw / "era5_tashkent_hourly.csv", weather_index, om["core_variables"], 10.0
    )
    write_hourly(
        raw / "era5_extra_tashkent_hourly.csv",
        weather_index,
        om["extra_variables"],
        10.0,
    )
    fc_cols = [
        f"{v}_previous_day{n}"
        for n in om["forecast"]["previous_days"]
        for v in om["forecast"]["variables"]
    ]
    fc_index = pd.date_range("2024-02-05", "2024-02-15 23:00", freq="h")
    write_hourly(raw / "forecast_previous_runs_hourly.csv", fc_index, fc_cols, 50.0)
    grid = pd.date_range(
        "2024-02-01 21:00", "2024-02-10 11:00", freq="h"
    )  # starts and ends mid-day
    values = np.arange(len(grid), dtype=float)
    flagged = pd.DataFrame(
        {
            "datetime_utc": grid.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "value_raw": values,
            "row_present": 1,
            "missing": 0,
            "negative": 0,
            "above_max": 0,
            "zero": 0,
            "spike": 0,
            "spike_extreme": 0,
            "stuck": 0,
            "value_clean": values,
        }
    )
    flagged.loc[5, "value_clean"] = np.nan
    flagged.loc[5, "spike_extreme"] = 1
    flagged.to_csv(interim / "us_embassy_pm25_flagged.csv", index=False)
    return tmp_path, cfg


def build(workspace_):
    tmp_path, cfg = workspace_
    out = tmp_path / "processed"
    meta = processing.build_all(tmp_path / "raw", tmp_path / "interim", out, cfg)
    hourly = pd.read_csv(out / "hourly_us_embassy.csv", index_col=0)
    daily = pd.read_csv(out / "daily_us_embassy.csv", index_col=0)
    return meta, hourly, daily, out


def test_hourly_table_columns_and_alignment(workspace):
    meta, hourly, _, out = build(workspace)
    assert (
        hourly.index[0] == "2024-02-01T21:00:00Z"
        and hourly.index[-1] == "2024-02-10T11:00:00Z"
    )
    assert hourly["pm25_raw"].iloc[5] == 5.0 and np.isnan(hourly["pm25"].iloc[5])
    assert hourly["flag_spike_extreme"].iloc[5] == 1
    assert "era5_boundary_layer_height" in hourly and "fc_d2_temperature_2m" in hourly
    assert hourly.loc["2024-02-01T21:00:00Z", "era5_temperature_2m"] == 10.0
    assert (
        hourly.loc["2024-02-04T00:00:00Z", "fc_d2_temperature_2m"]
        != hourly.loc["2024-02-04T00:00:00Z", "fc_d2_temperature_2m"]
    )  # before the forecast archive
    assert hourly.loc["2024-02-06T00:00:00Z", "fc_d2_temperature_2m"] == 50.0
    assert meta["hourly"]["rows"] == len(hourly) and (out / "metadata.json").exists()


def test_daily_table_spans_first_to_last_valid_day(workspace):
    _, _, daily, _ = build(workspace)
    # 2024-02-01 21:00 UTC is 02-02 02:00 local; the grid ends 2024-02-10 11:00 UTC = 16:00 local.
    assert daily.index[0] == "2024-02-02" and daily.index[-1] == "2024-02-10"
    assert daily.loc["2024-02-02", "pm25_hours"] == 21  # edge day, flagged by the count
    assert daily.loc["2024-02-02", "pm25_mean"] == pytest.approx(
        np.mean([i for i in range(22) if i != 5])
    )
    assert np.isnan(daily.loc["2024-02-10", "pm25_mean"])  # only 16 hours that day
    # Local 2024-02-05 is 2024-02-04 19:00 UTC to 02-05 18:59, hours 70 to 93 after the grid start.
    assert daily.loc["2024-02-05", "pm25_mean"] == pytest.approx(
        np.mean(np.arange(70, 94))
    )


def test_daily_weather_columns_and_forecast_leads(workspace):
    _, _, daily, _ = build(workspace)
    assert "era5_temp_mean" in daily and "era5_blh_mean" in daily
    assert not [c for c in daily.columns if c.endswith("_snow") and c.startswith("fc_")]
    assert {"fc_lead1_temp_mean", "fc_lead2_temp_mean", "fc_lead3_temp_mean"} <= set(
        daily.columns
    )
    assert daily.loc["2024-02-06", "fc_lead1_temp_mean"] == 50.0
    assert np.isnan(daily.loc["2024-02-02", "fc_lead1_temp_mean"])  # before the archive
    assert daily.loc["2024-02-06", "era5_temp_mean"] == 10.0


def test_missing_flagged_file_has_clear_error(tmp_path):
    with pytest.raises(FileNotFoundError, match="clean_data.py"):
        processing.build_all(
            tmp_path / "raw", tmp_path / "interim", tmp_path / "out", load_config()
        )


def test_metadata_is_json(workspace):
    meta, *_ = build(workspace)
    json.dumps(meta)
    assert meta["min_hours_for_daily_mean"] == 18
