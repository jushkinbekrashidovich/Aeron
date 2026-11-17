from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from aeron import config, validation
from aeron.validation import Column, FileSpec

TODAY = datetime(2025, 1, 1, tzinfo=UTC)
SPEC = FileSpec(
    {"temp": Column(-60, 60, unit="C"), "rh": Column(0, 100, max_missing=0.1)},
    regular_hourly=True,
)


def write(tmp_path: Path, frame: pd.DataFrame) -> Path:
    path = tmp_path / "x.csv"
    frame.to_csv(path, index=False)
    return path


def good_frame(n=24):
    times = pd.date_range("2024-01-01", periods=n, freq="h").strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    return pd.DataFrame({"datetime_utc": times, "temp": range(n), "rh": [50.0] * n})


def codes(report, level=None):
    return {i.code for i in report.issues if level is None or i.level == level}


def test_good_file_is_ok(tmp_path):
    report = validation.validate_file(write(tmp_path, good_frame()), SPEC, TODAY)
    assert report.status == "OK"
    assert report.rows == 24


def test_missing_file_is_an_error(tmp_path):
    report = validation.validate_file(tmp_path / "nope.csv", SPEC, TODAY)
    assert report.status == "ERROR" and "missing_file" in codes(report)


def test_wrong_or_reordered_columns(tmp_path):
    frame = good_frame()[["datetime_utc", "rh", "temp"]]
    report = validation.validate_file(write(tmp_path, frame), SPEC, TODAY)
    assert "columns" in codes(report, "error")
    report = validation.validate_file(
        write(tmp_path, good_frame().drop(columns="rh")), SPEC, TODAY
    )
    assert "columns" in codes(report, "error")


def test_duplicate_and_unordered_timestamps(tmp_path):
    frame = good_frame()
    frame.loc[5, "datetime_utc"] = frame.loc[4, "datetime_utc"]
    report = validation.validate_file(write(tmp_path, frame), SPEC, TODAY)
    assert {"duplicate_timestamps", "unordered_timestamps"} <= codes(report, "error")


def test_off_hour_and_future_timestamps(tmp_path):
    frame = good_frame()
    frame.loc[3, "datetime_utc"] = "2024-01-01T03:30:00Z"
    frame.loc[23, "datetime_utc"] = "2026-01-01T00:00:00Z"
    report = validation.validate_file(write(tmp_path, frame), SPEC, TODAY)
    assert {"off_hour", "future_timestamps"} <= codes(report, "error")


def test_bad_time_format(tmp_path):
    frame = good_frame()
    frame["datetime_utc"] = frame["datetime_utc"].str.replace("Z", "")
    report = validation.validate_file(write(tmp_path, frame), SPEC, TODAY)
    assert "time_format" in codes(report, "error")


def test_irregular_grid_is_error_only_when_required(tmp_path):
    frame = good_frame().drop(index=[5, 6]).reset_index(drop=True)
    report = validation.validate_file(write(tmp_path, frame), SPEC, TODAY)
    assert "irregular_steps" in codes(report, "error")
    gappy = FileSpec(SPEC.columns, regular_hourly=False)
    report = validation.validate_file(write(tmp_path, frame), gappy, TODAY)
    assert report.status == "OK" and "gaps" in codes(report, "info")


def test_range_violation_is_error(tmp_path):
    frame = good_frame()
    frame.loc[2, "rh"] = 130.0
    frame.loc[3, "temp"] = -99
    report = validation.validate_file(write(tmp_path, frame), SPEC, TODAY)
    ranges = [i for i in report.issues if i.code == "range"]
    assert len(ranges) == 2 and all(i.count == 1 for i in ranges)


def test_missing_share_threshold(tmp_path):
    frame = good_frame(20)
    frame.loc[0, "rh"] = None  # 5% of 20, allowed 10%
    report = validation.validate_file(write(tmp_path, frame), SPEC, TODAY)
    assert report.status == "OK" and "missing" in codes(report, "info")
    frame.loc[1:3, "rh"] = None  # 20%
    report = validation.validate_file(write(tmp_path, frame), SPEC, TODAY)
    assert "missing" in codes(report, "error")
    frame = good_frame(20)
    frame.loc[0, "temp"] = None  # temp allows no missing values
    report = validation.validate_file(write(tmp_path, frame), SPEC, TODAY)
    assert "missing" in codes(report, "error")


def test_non_numeric_entries(tmp_path):
    frame = good_frame()
    frame["temp"] = frame["temp"].astype(object)
    frame.loc[4, "temp"] = "abc"
    report = validation.validate_file(write(tmp_path, frame), SPEC, TODAY)
    assert "non_numeric" in codes(report, "error")


def test_empty_file(tmp_path):
    path = tmp_path / "x.csv"
    path.write_text("datetime_utc,temp,rh\n")
    assert "empty" in codes(validation.validate_file(path, SPEC, TODAY), "error")


def openaq_frame(values):
    times = pd.date_range("2024-01-01", periods=len(values), freq="h").strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    return pd.DataFrame(
        {
            "datetime_utc": times,
            "value": values,
            "percent_complete": 100.0,
            "observed": 1,
            "expected": 1,
        }
    )


def test_openaq_high_values_zero_and_empty(tmp_path):
    spec = FileSpec(validation.openaq_columns(validation.PM25), False, check_stuck=True)
    frame = openaq_frame([10.0, 0.0, 600.0, None, 20.0] + [30.0 + i for i in range(20)])
    report = validation.validate_file(write(tmp_path, frame), spec, TODAY)
    assert "high_values" in codes(report, "warn") and report.status == "WARN"
    assert {"zeros", "missing"} <= codes(report, "info")


def test_openaq_stuck_sensor_and_negative_value(tmp_path):
    spec = FileSpec(validation.openaq_columns(validation.PM25), False, check_stuck=True)
    report = validation.validate_file(
        write(tmp_path, openaq_frame([42.0] * 30)), spec, TODAY
    )
    assert "stuck" in codes(report, "warn")
    report = validation.validate_file(
        write(tmp_path, openaq_frame([5.0, -3.0, 6.0])), spec, TODAY
    )
    assert "range" in codes(report, "error")


def test_openaq_observed_cannot_exceed_expected(tmp_path):
    spec = FileSpec(validation.openaq_columns(validation.PM25), False)
    frame = openaq_frame([5.0, 6.0])
    frame.loc[0, "observed"] = 3
    assert "coverage" in codes(
        validation.validate_file(write(tmp_path, frame), spec, TODAY), "error"
    )


def test_specs_follow_the_config():
    cfg = config.load_config()
    specs = validation.build_specs(cfg)
    forecast = specs["openmeteo/forecast_previous_runs_hourly.csv"]
    expected = len(cfg["openmeteo"]["forecast"]["previous_days"]) * len(
        cfg["openmeteo"]["forecast"]["variables"]
    )
    assert len(forecast.columns) == expected
    assert (
        list(specs["openmeteo/era5_tashkent_hourly.csv"].columns)
        == cfg["openmeteo"]["core_variables"]
    )
    for series in config.openaq_series(cfg):
        assert f"openaq/{series.name}_hourly.csv" in specs
    assert (
        "wind_speed_10m" in validation.LIMITS
        and validation.LIMITS["wind_speed_10m"].unit == "km/h"
    )


def test_format_reports_groups_columns_with_same_missing_count(tmp_path):
    spec = FileSpec(
        {"a": Column(0, 10, 0.5), "b": Column(0, 10, 0.5), "c": Column(0, 10, 0.5)},
        True,
    )
    frame = good_frame(10).drop(columns=["temp", "rh"])
    for name in "abc":
        frame[name] = 1.0
        frame.loc[2, name] = None
    report = validation.validate_file(write(tmp_path, frame), spec, TODAY)
    missing = [i for i in report.issues if i.code == "missing"]
    assert len(missing) == 1 and "3 columns" in missing[0].message
    assert "WARN" not in validation.format_reports([report])
