import json

import numpy as np
import pandas as pd

from aeron import cleaning


def hourly(values, start="2024-01-01"):
    index = pd.date_range(start, periods=len(values), freq="h")
    return pd.Series(values, index=index, dtype=float)


def frame(values):
    s = hourly(values)
    return pd.DataFrame({"value_raw": s, "row_present": True})


def spikes(values):
    return list(np.flatnonzero(cleaning.find_spikes(hourly(values)).to_numpy()))


BASE = [20.0, 22.0, 19.0, 21.0]


def test_isolated_spike_is_flagged():
    assert spikes(BASE + [900.0] + BASE) == [4]


def test_two_hour_spike_is_flagged_but_three_hours_is_not():
    assert spikes(BASE + [900.0, 880.0] + BASE) == [4, 5]
    assert spikes(BASE + [900.0, 880.0, 870.0] + BASE) == []


def test_smooth_episode_is_not_a_spike():
    # Gradual rise and decay: neighbours are not 8 times lower on both sides.
    assert spikes([20, 40, 120, 350, 340, 200, 90, 40, 25]) == []


def test_spike_needs_neighbours_on_both_sides():
    assert spikes([900.0] + BASE) == []  # at the start
    assert spikes(BASE + [900.0]) == []  # at the end
    assert (
        spikes([np.nan, np.nan, np.nan, 900.0] + BASE) == []
    )  # no valid readings before


def test_spike_below_minimum_is_ignored():
    assert spikes(BASE + [250.0] + BASE) == []


def test_missing_hour_breaks_a_run():
    # 900, gap, 880 are separate single-hour runs, each judged on its own.
    assert spikes(BASE + [900.0, np.nan, 880.0] + BASE) == [4, 6]


def test_extreme_spike_removed_moderate_kept():
    values = BASE + [900.0] + BASE + [450.0] + BASE
    out = cleaning.flag_pm25(frame(values))
    assert out["spike"].sum() == 2 and out["spike_extreme"].sum() == 1
    assert np.isnan(out["value_clean"].iloc[4])
    assert out["value_clean"].iloc[9] == 450.0
    assert out["value_raw"].iloc[4] == 900.0  # raw is never altered


def test_negative_and_above_limit_are_removed():
    out = cleaning.flag_pm25(frame([10.0, -1.0, 2500.0, 12.0]))
    assert out["negative"].tolist() == [False, True, False, False]
    assert out["above_max"].tolist() == [False, False, True, False]
    assert out["value_clean"].isna().tolist() == [False, True, True, False]


def test_zero_is_flagged_but_kept():
    out = cleaning.flag_pm25(frame([5.0, 0.0, 6.0]))
    assert out["zero"].tolist() == [False, True, False]
    assert out["value_clean"].iloc[1] == 0.0


def test_stuck_needs_24_identical_consecutive_hours():
    out = cleaning.flag_pm25(frame([30.0] * 24 + [31.0]))
    assert out["stuck"].sum() == 24 and out["value_clean"].iloc[:24].isna().all()
    assert not cleaning.flag_pm25(frame([30.0] * 23 + [31.0]))["stuck"].any()
    broken = [30.0] * 12 + [np.nan] + [30.0] * 12
    assert not cleaning.flag_pm25(frame(broken))["stuck"].any()


def write_raw(path, values, start="2024-01-01T00:00:00Z", skip=()):
    times = pd.date_range(start, periods=len(values), freq="h")
    rows = [
        (t.strftime("%Y-%m-%dT%H:%M:%SZ"), "" if np.isnan(v) else v, 100.0, 1, 1)
        for i, (t, v) in enumerate(zip(times, values, strict=True))
        if i not in skip
    ]
    pd.DataFrame(
        rows,
        columns=["datetime_utc", "value", "percent_complete", "observed", "expected"],
    ).to_csv(path, index=False)


def test_load_series_marks_absent_hours(tmp_path):
    path = tmp_path / "s_hourly.csv"
    write_raw(path, [1.0, 2.0, 3.0, np.nan, 5.0], skip={2})
    series = cleaning.load_series(path)
    assert len(series) == 5
    assert series["row_present"].tolist() == [True, True, False, True, True]
    assert series["value_raw"].isna().tolist() == [False, False, True, True, False]


def test_summary_and_log_are_consistent(tmp_path):
    values = [20.0] * 4 + [900.0] + [21.0] * 4 + [450.0] + [19.0] * 4 + [np.nan, 0.0]
    path = tmp_path / "s_hourly.csv"
    write_raw(path, values, skip={1})
    flagged = cleaning.flag_pm25(cleaning.load_series(path))
    s = cleaning.summarise(flagged)
    assert s["spike"] == 2 and s["spike_extreme"] == 1 and s["zero"] == 1
    assert s["valid_clean"] == s["valid_raw"] - 1
    assert s["absent_hours"] == 1
    assert s["missing"] == 2  # one absent hour and one empty value
    log = {
        "created_utc": "t",
        "rules": [r.__dict__ for r in cleaning.RULES],
        "parameters": {"a": 1},
        "series": {"s": s | {"spikes": cleaning.spike_hours(flagged)}},
    }
    text = cleaning.render_log(log)
    assert "`spike_extreme`" in text and "(900, removed)" in text and "(450)" in text


def test_clean_all_writes_flag_files_and_log(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    write_raw(raw / "a_pm25_hourly.csv", [20.0, 21.0, 22.0, 900.0, 20.0, 21.0, 19.0])
    write_raw(raw / "a_humidity_hourly.csv", [50.0] * 7)
    cfg = {
        "openaq": {
            "series": [
                {
                    "name": "a_pm25",
                    "location_id": 1,
                    "sensor_id": 1,
                    "parameter": "pm25",
                    "start": "2024-01-01",
                    "quality": "reference",
                    "primary": True,
                },
                {
                    "name": "a_humidity",
                    "location_id": 1,
                    "sensor_id": 2,
                    "parameter": "relativehumidity",
                    "start": "2024-01-01",
                    "quality": "reference",
                    "primary": False,
                },
            ]
        }
    }
    out = tmp_path / "interim"
    log = cleaning.clean_all(raw, out, cfg)
    assert list(log["series"]) == ["a_pm25"]  # humidity is not a PM2.5 series
    flagged = pd.read_csv(out / "a_pm25_flagged.csv")
    assert {"value_raw", "value_clean", *cleaning.FLAG_COLUMNS, "row_present"} <= set(
        flagged.columns
    )
    assert flagged.loc[3, "spike_extreme"] == 1 and np.isnan(
        flagged.loc[3, "value_clean"]
    )
    saved = json.loads((out / "cleaning_log.json").read_text())
    assert saved["series"]["a_pm25"]["spike_extreme"] == 1
    assert saved["parameters"]["spike_extreme_min"] == cleaning.SPIKE_EXTREME_MIN
