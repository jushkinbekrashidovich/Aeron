import math

import numpy as np
import pandas as pd
import pytest

from aeron import hypotheses as hy

N_FAST = 400


def days(start, n):
    return pd.date_range(start, periods=n, freq="D")


def winter_frame(n_years=6, seed=0, effect=None):
    """Winter daily table (Nov to Feb of several winters) with weather columns."""
    rng = np.random.default_rng(seed)
    index = pd.DatetimeIndex(
        np.concatenate([days(f"{2018 + k}-11-01", 120) for k in range(n_years)])
    )
    n = len(index)
    wind = rng.normal(8, 3, n)
    blh = rng.normal(400, 120, n)
    temp = rng.normal(0, 5, n)
    msl = rng.normal(1020, 6, n)
    noise = rng.normal(0, 8, n)
    pm = 60 - 3 * (wind - 8) - 0.03 * (blh - 400) + noise
    frame = pd.DataFrame(
        {
            "pm25_mean": np.clip(pm, 3, None),
            "era5_wind_mean": wind,
            "era5_blh_mean": blh,
            "era5_vent_mean": wind * blh,
            "era5_temp_mean": temp,
            "era5_msl_mean": msl,
        },
        index=index,
    )
    return frame


# ---------------------------------------------------------------- blocks and bootstrap
def test_blocks_never_cross_a_gap():
    d = days("2020-01-01", 20).delete([7, 8])  # gap after day index 6
    blocks = hy.make_blocks(d, 5)
    for b in blocks:
        step = np.diff(d[b].values).astype("timedelta64[D]").astype(int)
        assert (step == 1).all()
        assert len(b) <= 5
    assert all(len(b) == 5 for b in blocks)


def test_short_runs_are_kept_as_one_block():
    d = days("2020-01-01", 3).append(days("2020-02-01", 30))
    blocks = hy.make_blocks(d, 14)
    assert any(len(b) == 3 for b in blocks)


def test_draw_has_about_the_original_size_and_marks_block_starts():
    d = days("2020-01-01", 100)
    blocks = hy.make_blocks(d, 14)
    rng = np.random.default_rng(0)
    idx, starts = hy.draw(blocks, 100, 14, rng)
    assert 90 <= len(idx) <= 112
    assert starts[0] and starts.sum() == math.ceil(100 / 14)


def test_bootstrap_is_reproducible_and_interval_contains_the_mean():
    d = days("2020-01-01", 200)
    x = np.random.default_rng(1).normal(10, 2, 200)
    a = hy.bootstrap(lambda i, s: x[i].mean(), d, 14, 300, seed=0)
    b = hy.bootstrap(lambda i, s: x[i].mean(), d, 14, 300, seed=0)
    assert np.array_equal(a, b)
    lo, hi = hy.interval(a, 0.95)
    assert lo < x.mean() < hi
    assert hy.LEVEL_ADJUSTED == pytest.approx(1 - 0.05 / 7)


def test_block_bootstrap_interval_is_wider_for_autocorrelated_data():
    rng = np.random.default_rng(2)
    n = 400
    e = rng.normal(size=n)
    ar = np.zeros(n)
    for t in range(1, n):
        ar[t] = 0.9 * ar[t - 1] + e[t]
    d = days("2020-01-01", n)
    wide = hy.interval(hy.bootstrap(lambda i, s: ar[i].mean(), d, 14, 400), 0.95)
    iid = hy.interval(hy.bootstrap(lambda i, s: ar[i].mean(), d, 1, 400), 0.95)
    assert (wide[1] - wide[0]) > 1.5 * (iid[1] - iid[0])


# ---------------------------------------------------------------- decision rules
def test_difference_rules():
    assert hy.decide_difference(8, 3, 12, 5) == "supported"
    assert hy.decide_difference(3, 1, 5, 5) == "present but small"
    assert hy.decide_difference(2, -1, 5, 5).startswith("not supported")
    assert hy.decide_difference(-8, -12, -3, 5).startswith("contradicted")


def test_negative_correlation_rules():
    assert hy.decide_negative_correlation(-0.6, -0.7, -0.5) == "supported"
    assert hy.decide_negative_correlation(-0.3, -0.45, -0.2) == "present but weak"
    assert hy.decide_negative_correlation(-0.1, -0.3, 0.1).startswith("not supported")
    assert hy.decide_negative_correlation(0.4, 0.3, 0.5).startswith("contradicted")


def test_equivalence_rules():
    assert hy.decide_equivalence(1.0, 0.93, 1.07).startswith("supported")
    assert hy.decide_equivalence(1.3, 1.15, 1.45).startswith("contradicted")
    assert hy.decide_equivalence(1.05, 0.88, 1.2) == "inconclusive"


def test_reduction_rules():
    assert hy.decide_reduction(0.3, 0.2, 0.4) == "supported"
    assert hy.decide_reduction(0.05, 0.01, 0.1) == "present but small"
    assert hy.decide_reduction(0.05, -0.1, 0.2).startswith("not supported")


# ---------------------------------------------------------------- tests on synthetic data with known answers
def test_h1_detects_a_clear_shift_and_not_a_null():
    f = winter_frame(n_years=7, seed=3)
    years = hy.winter_year(f.index)
    shifted = f.copy()
    shifted.loc[np.isin(years, hy.LATER_WINTERS), "pm25_mean"] += 15
    r = hy.h1_winters_differ(shifted, n_resamples=N_FAST)
    assert r["decision"] == "supported"
    assert r["estimate"] == pytest.approx(15, abs=3)
    null = hy.h1_winters_differ(f, n_resamples=N_FAST)
    assert null["decision"].startswith("not supported")


def test_h1_leaves_out_the_first_winter():
    f = winter_frame(n_years=7, seed=4)
    r = hy.h1_winters_differ(f, n_resamples=100)
    years = hy.winter_year(f.index)
    expected = np.isin(years, hy.EARLIER_WINTERS + hy.LATER_WINTERS).sum()
    assert r["n"] == expected


def test_h2_finds_strong_negative_correlation_with_wind_and_none_with_noise():
    f = winter_frame(seed=5)
    r = hy.h2_correlation(f, "era5_wind_mean", "H2a", n_resamples=N_FAST)
    assert r["decision"] == "supported" and r["estimate"] < -0.5
    f["noise"] = np.random.default_rng(6).normal(size=len(f))
    null = hy.h2_correlation(f, "noise", "null", n_resamples=N_FAST)
    assert null["decision"].startswith("not supported")


def test_h2_uses_only_winter_days_and_pairwise_deletion():
    f = winter_frame(seed=7)
    f.loc[f.index[:50], "era5_blh_mean"] = np.nan
    summer = pd.DataFrame({c: 1.0 for c in f.columns}, index=days("2019-06-01", 30))
    r = hy.h2_correlation(pd.concat([f, summer]), "era5_blh_mean", "b", n_resamples=100)
    assert r["n"] == len(f) - 50


def test_h2_lagged_predictor_matches_a_manual_shift():
    f = winter_frame(seed=8)
    lag1 = hy.h2_correlation(f, "era5_wind_mean", "lag", n_resamples=100, lag=1)
    manual = f.copy()
    manual["x"] = manual["era5_wind_mean"].shift(1, freq="D").reindex(manual.index)
    manual = manual.dropna(subset=["x"])
    assert lag1["estimate"] == pytest.approx(
        hy.spearman(manual["x"].to_numpy(), manual["pm25_mean"].to_numpy())
    )


def test_h4_equivalence_when_there_is_no_weekend_effect_and_contradiction_when_large():
    rng = np.random.default_rng(9)
    idx = pd.DatetimeIndex(
        np.concatenate([days(f"{2019 + k}-11-01", 120) for k in range(6)])
    )
    base = pd.DataFrame({"pm25_mean": 50 + rng.normal(0, 3, len(idx))}, index=idx)
    r = hy.h4_weekend_ratio(base, n_resamples=N_FAST)
    assert r["decision"].startswith("supported")
    big = base.copy()
    big.loc[big.index.day_of_week >= 5, "pm25_mean"] *= 1.4
    r2 = hy.h4_weekend_ratio(big, n_resamples=N_FAST)
    assert r2["decision"].startswith("contradicted")
    assert r2["estimate"] == pytest.approx(1.4, abs=0.05)


def test_h5_weather_that_drives_persistence_reduces_autocorrelation():
    rng = np.random.default_rng(10)
    idx = pd.DatetimeIndex(
        np.concatenate([days(f"{2019 + k}-11-01", 120) for k in range(6)])
    )
    n = len(idx)
    wind = np.zeros(n)
    for t in range(1, n):
        wind[t] = 0.9 * wind[t - 1] + rng.normal()
    frame = pd.DataFrame(
        {
            "pm25_mean": np.exp(3.5 - 0.5 * wind + rng.normal(0, 0.15, n)),
            "era5_wind_mean": wind,
            "era5_blh_mean": rng.normal(size=n),
            "era5_temp_mean": rng.normal(size=n),
            "era5_msl_mean": rng.normal(size=n),
        },
        index=idx,
    )
    r = hy.h5_persistence(frame, n_resamples=N_FAST)
    assert r["acf_log_pm25"] > 0.7 and abs(r["acf_residual"]) < 0.2
    assert r["decision"] == "supported"


def test_h5_does_not_pair_days_across_block_starts():
    values = np.array([1.0, 2.0, 3.0, 10.0, 11.0, 12.0])
    starts = np.array([True, False, False, True, False, False])
    with_break = hy._lag1_correlation(values, starts)
    no_break = hy._lag1_correlation(values, np.array([True] + [False] * 5))
    assert with_break != pytest.approx(no_break)


def test_sectors_follow_the_frozen_definition():
    d = np.array(
        [
            0,
            10,
            350,
            22.4,
            22.5,
            45,
            67.4,
            67.5,
            90,
            112.4,
            112.5,
            180,
            292.5,
            315,
            337.4,
            337.5,
        ]
    )
    s = hy.sector_of(d)
    assert list(s) == [
        "N",
        "N",
        "N",
        "N",
        "NE",
        "NE",
        "NE",
        "E",
        "E",
        "E",
        "",
        "",
        "NW",
        "NW",
        "NW",
        "N",
    ]


def test_h3_uses_only_winter_hours_in_the_speed_range():
    rng = np.random.default_rng(11)
    t = pd.date_range("2019-11-01", periods=24 * 400, freq="h", tz="UTC")
    n = len(t)
    wind = rng.uniform(0, 14, n)
    direction = rng.choice([45, 90, 0, 315, 180], n)
    base = 40 + rng.normal(0, 5, n)
    base[np.isin(direction, [45, 90])] += 25  # east and north-east are dirtier
    hourly = pd.DataFrame(
        {
            "datetime_utc": t,
            "pm25": base,
            "era5_wind_speed_10m": wind,
            "era5_wind_direction_10m": direction,
        }
    )
    r = hy.h3_direction(hourly, n_resamples=N_FAST)
    assert r["estimate"] == pytest.approx(25, abs=2)
    assert r["decision"] == "supported"
    prepared = hy.h3_prepare(hourly)
    assert prepared["local_time"].dt.month.isin(hy.WINTER_MONTHS).all()
    reg = hy.h3_regression(hourly, n_resamples=60)
    assert reg["ratio"] > 1.3
