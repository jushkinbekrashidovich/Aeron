"""Hypothesis tests H1 to H5 (task 2.4), as specified in docs/research/hypotheses.md.

That document was frozen on 2026-11-22 before any of these tests was computed. Common
design, all taken from it:

- Winter means November to February. A day counts if its daily mean has at least 18
  observed hours. Days or hours with a missing variable are dropped from the test that
  needs them (pairwise deletion).
- Every interval is a moving-block bootstrap: blocks of ``block_days`` consecutive
  calendar days, never crossing a gap in the data, resampled until the sample is as large
  as the original, 5,000 resamples, seed 0. Sensitivity runs use 7 and 28 days.
- The primary family has 7 tests (H1, H2a, H2b, H2c, H3, H4, H5). Decisions use
  Bonferroni-adjusted 99.29% intervals (1 - 0.05 / 7). Each result also carries an
  unadjusted 95% interval.
- A hypothesis counts as supported only if the interval excludes the null value and the
  estimate passes the practical threshold written for it.

Every function returns plain dictionaries so a notebook can tabulate them. All of them
describe associations in observed data from one station and none tests a cause.
"""

from __future__ import annotations

import math
from collections.abc import Callable

import numpy as np
import pandas as pd
from scipy.stats import rankdata

BLOCK_DAYS = 14
N_RESAMPLES = 5000
SEED = 0
N_PRIMARY = 7
LEVEL_ADJUSTED = 1 - 0.05 / N_PRIMARY  # 0.99286
LEVEL_RAW = 0.95
WINTER_MONTHS = (11, 12, 1, 2)
UTC_OFFSET_HOURS = 5

# Practical thresholds (frozen).
H1_MIN_DIFFERENCE = 5.0  # ug/m3
H2_RHO = -0.30
H3_MIN_DIFFERENCE = 10.0  # ug/m3
H4_MARGIN = 0.10
H5_MIN_REDUCTION = 0.10

EARLIER_WINTERS = (2019, 2020, 2021)  # winters 2019-20, 2020-21, 2021-22
LATER_WINTERS = (2022, 2023, 2024)  # winters 2022-23, 2023-24, 2024-25


# --------------------------------------------------------------------------
# Winters and blocks
# --------------------------------------------------------------------------
def winter_year(index: pd.DatetimeIndex) -> np.ndarray:
    """Year in which the winter started (December 2019 and February 2020 are winter 2019)."""
    index = pd.DatetimeIndex(index)
    return np.where(index.month >= 11, index.year, index.year - 1)


def is_winter(index: pd.DatetimeIndex) -> np.ndarray:
    return np.isin(pd.DatetimeIndex(index).month, WINTER_MONTHS)


def make_blocks(
    days: pd.DatetimeIndex, block_days: int = BLOCK_DAYS
) -> list[np.ndarray]:
    """Candidate blocks of ``block_days`` consecutive calendar days, as positions into ``days``.

    ``days`` is sorted and unique. A block never crosses a missing day. A run of
    consecutive days shorter than ``block_days`` forms one block of its own, so no data is
    dropped.
    """
    days = pd.DatetimeIndex(days)
    if len(days) == 0:
        return []
    step = np.diff(days.values).astype("timedelta64[D]").astype(int)
    breaks = np.flatnonzero(step != 1) + 1
    runs = np.split(np.arange(len(days)), breaks)
    blocks: list[np.ndarray] = []
    for run in runs:
        if len(run) <= block_days:
            blocks.append(run)
        else:
            blocks.extend(
                run[s : s + block_days] for s in range(len(run) - block_days + 1)
            )
    return blocks


def run_starts(days: pd.DatetimeIndex) -> np.ndarray:
    """True at the first day of each unbroken run of consecutive days."""
    days = pd.DatetimeIndex(days)
    if len(days) == 0:
        return np.zeros(0, dtype=bool)
    step = np.diff(days.values).astype("timedelta64[D]").astype(int)
    return np.r_[True, step != 1]


def draw(
    blocks: list[np.ndarray], n_units: int, block_days: int, rng: np.random.Generator
) -> tuple[np.ndarray, np.ndarray]:
    """One bootstrap sample: positions of the resampled units and a flag for each block start."""
    k = max(1, math.ceil(n_units / block_days))
    picks = rng.integers(0, len(blocks), size=k)
    parts = [blocks[i] for i in picks]
    idx = np.concatenate(parts)
    starts = np.zeros(len(idx), dtype=bool)
    starts[np.cumsum([0] + [len(p) for p in parts[:-1]])] = True
    return idx, starts


def bootstrap(
    stat: Callable[[np.ndarray, np.ndarray], float | np.ndarray],
    days: pd.DatetimeIndex,
    block_days: int = BLOCK_DAYS,
    n_resamples: int = N_RESAMPLES,
    seed: int = SEED,
) -> np.ndarray:
    """Values of ``stat(idx, starts)`` over moving-block resamples of the units on ``days``."""
    blocks = make_blocks(days, block_days)
    if not blocks:
        raise ValueError("no data to resample")
    rng = np.random.default_rng(seed)
    n = len(days)
    out = [stat(*draw(blocks, n, block_days, rng)) for _ in range(n_resamples)]
    return np.asarray(out, dtype=float)


def interval(samples: np.ndarray, level: float) -> tuple[float, float]:
    """Percentile interval of the finite bootstrap values."""
    ok = samples[np.isfinite(samples)]
    if len(ok) < 100:
        return (math.nan, math.nan)
    lo, hi = np.percentile(ok, [(1 - level) / 2 * 100, (1 + level) / 2 * 100])
    return float(lo), float(hi)


def _result(name: str, estimate: float, samples: np.ndarray, n: int, **extra) -> dict:
    lo_a, hi_a = interval(samples, LEVEL_ADJUSTED)
    lo_r, hi_r = interval(samples, LEVEL_RAW)
    return {
        "test": name,
        "estimate": float(estimate),
        "lo_adj": lo_a,
        "hi_adj": hi_a,
        "lo_raw": lo_r,
        "hi_raw": hi_r,
        "n": int(n),
        **extra,
    }


# --------------------------------------------------------------------------
# Decision rules (frozen in hypotheses.md)
# --------------------------------------------------------------------------
def decide_difference(estimate: float, lo: float, hi: float, minimum: float) -> str:
    """H1 and H3: positive difference, supported if the interval excludes 0 and it is large enough."""
    if not (math.isfinite(lo) and math.isfinite(hi)):
        return "no result"
    if lo > 0:
        return "supported" if estimate >= minimum else "present but small"
    if hi < 0:
        return "contradicted (difference has the opposite sign)"
    return "not supported (interval includes 0)"


def decide_negative_correlation(
    rho: float, lo: float, hi: float, threshold: float = H2_RHO
) -> str:
    """H2: supported if the upper end of the interval is below the threshold (-0.30)."""
    if not (math.isfinite(lo) and math.isfinite(hi)):
        return "no result"
    if hi < threshold:
        return "supported"
    if hi < 0:
        return "present but weak"
    if lo > 0:
        return "contradicted (correlation is positive)"
    return "not supported (interval reaches 0)"


def decide_equivalence(
    ratio: float, lo: float, hi: float, margin: float = H4_MARGIN
) -> str:
    """H4: no meaningful difference if the whole interval lies inside 1 +- margin."""
    if not (math.isfinite(lo) and math.isfinite(hi)):
        return "no result"
    if lo >= 1 - margin and hi <= 1 + margin:
        return "supported (no meaningful difference)"
    if hi < 1 - margin or lo > 1 + margin:
        return "contradicted (difference larger than the margin)"
    return "inconclusive"


def decide_reduction(
    estimate: float, lo: float, hi: float, minimum: float = H5_MIN_REDUCTION
) -> str:
    """H5: reduction of the lag-1 autocorrelation, supported if the interval excludes 0 and it is at least 0.10."""
    if not (math.isfinite(lo) and math.isfinite(hi)):
        return "no result"
    if lo > 0:
        return "supported" if estimate >= minimum else "present but small"
    if hi < 0:
        return "contradicted (autocorrelation grew)"
    return "not supported (interval includes 0)"


# --------------------------------------------------------------------------
# Statistics
# --------------------------------------------------------------------------
def spearman(x: np.ndarray, y: np.ndarray) -> float:
    if len(x) < 3:
        return math.nan
    rx, ry = rankdata(x), rankdata(y)
    sx, sy = rx.std(), ry.std()
    if sx == 0 or sy == 0:
        return math.nan
    return float(np.mean((rx - rx.mean()) * (ry - ry.mean())) / (sx * sy))


def _winter_daily(
    daily: pd.DataFrame, columns: list[str], all_year: bool = False
) -> pd.DataFrame:
    """Days with a daily mean and every listed column (pairwise deletion); winter days unless ``all_year``."""
    frame = daily[["pm25_mean", *columns]].copy()
    frame.index = pd.DatetimeIndex(frame.index)
    frame = frame.dropna()
    return frame if all_year else frame[is_winter(frame.index)]


# --------------------------------------------------------------------------
# H1. Winters differ
# --------------------------------------------------------------------------
def h1_winters_differ(
    daily: pd.DataFrame, block_days: int = BLOCK_DAYS, n_resamples: int = N_RESAMPLES
) -> dict:
    """Later winters (2022-23 to 2024-25) minus earlier winters (2019-20 to 2021-22), mean daily PM2.5."""
    frame = _winter_daily(daily, [])
    years = winter_year(frame.index)
    groups = {}
    for label, wanted in (("earlier", EARLIER_WINTERS), ("later", LATER_WINTERS)):
        part = frame[np.isin(years, wanted)]
        groups[label] = (part.index, part["pm25_mean"].to_numpy(float))
    samples = {}
    for offset, (label, (days, values)) in enumerate(groups.items()):
        samples[label] = bootstrap(
            lambda idx, st, v=values: v[idx].mean(),
            days,
            block_days,
            n_resamples,
            SEED + offset,
        )
    diff_samples = samples["later"] - samples["earlier"]
    estimate = groups["later"][1].mean() - groups["earlier"][1].mean()
    res = _result(
        "H1 winters differ (later minus earlier, mean daily PM2.5, ug/m3)",
        estimate,
        diff_samples,
        len(groups["earlier"][1]) + len(groups["later"][1]),
        n_earlier=len(groups["earlier"][1]),
        n_later=len(groups["later"][1]),
        mean_earlier=float(groups["earlier"][1].mean()),
        mean_later=float(groups["later"][1].mean()),
    )
    res["decision"] = decide_difference(
        estimate, res["lo_adj"], res["hi_adj"], H1_MIN_DIFFERENCE
    )
    return res


def h1_per_winter(
    daily: pd.DataFrame, block_days: int = BLOCK_DAYS, n_resamples: int = N_RESAMPLES
) -> pd.DataFrame:
    """Secondary: mean and median per winter with unadjusted 95% intervals (all winters, including 2018-19)."""
    frame = _winter_daily(daily, [])
    years = winter_year(frame.index)
    rows = []
    for year in sorted(set(years)):
        part = frame[years == year]
        values = part["pm25_mean"].to_numpy(float)
        days = part.index
        both = bootstrap(
            lambda idx, st, v=values: np.array([v[idx].mean(), np.median(v[idx])]),
            days,
            block_days,
            n_resamples,
            SEED + int(year),
        )
        rows.append(
            {
                "winter": f"{year}-{(year + 1) % 100:02d}",
                "days": len(values),
                "mean": values.mean(),
                "mean_lo": interval(both[:, 0], LEVEL_RAW)[0],
                "mean_hi": interval(both[:, 0], LEVEL_RAW)[1],
                "median": float(np.median(values)),
                "median_lo": interval(both[:, 1], LEVEL_RAW)[0],
                "median_hi": interval(both[:, 1], LEVEL_RAW)[1],
            }
        )
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------
# H2. Weather and stagnation proxies
# --------------------------------------------------------------------------
def h2_correlation(
    daily: pd.DataFrame,
    predictor: str,
    name: str,
    block_days: int = BLOCK_DAYS,
    n_resamples: int = N_RESAMPLES,
    winter_only: bool = True,
    lag: int = 0,
) -> dict:
    """Spearman correlation of winter daily PM2.5 with a same-day (or lagged) predictor."""
    frame = daily[["pm25_mean", predictor]].copy()
    frame.index = pd.DatetimeIndex(frame.index)
    if lag:
        frame[predictor] = frame[predictor].shift(lag, freq="D").reindex(frame.index)
    frame = frame.dropna()
    if winter_only:
        frame = frame[is_winter(frame.index)]
    y = frame["pm25_mean"].to_numpy(float)
    x = frame[predictor].to_numpy(float)
    samples = bootstrap(
        lambda idx, st: spearman(x[idx], y[idx]), frame.index, block_days, n_resamples
    )
    rho = spearman(x, y)
    res = _result(
        name,
        rho,
        samples,
        len(frame),
        predictor=predictor,
        lag=lag,
        season="winter" if winter_only else "all year",
    )
    res["decision"] = decide_negative_correlation(rho, res["lo_adj"], res["hi_adj"])
    return res


def h2_fifths(
    daily: pd.DataFrame,
    predictor: str,
    block_days: int = BLOCK_DAYS,
    n_resamples: int = N_RESAMPLES,
) -> dict:
    """Secondary: median PM2.5 in the lowest fifth of the predictor minus that in the highest fifth."""
    frame = _winter_daily(daily, [predictor])
    y = frame["pm25_mean"].to_numpy(float)
    x = frame[predictor].to_numpy(float)

    def stat(idx: np.ndarray, starts: np.ndarray) -> float:
        xs, ys = x[idx], y[idx]
        lo_cut, hi_cut = np.quantile(xs, [0.2, 0.8])
        low, high = ys[xs <= lo_cut], ys[xs >= hi_cut]
        return (
            float(np.median(low) - np.median(high))
            if len(low) and len(high)
            else math.nan
        )

    samples = bootstrap(stat, frame.index, block_days, n_resamples)
    estimate = stat(np.arange(len(y)), np.zeros(len(y), bool))
    return _result(
        f"median PM2.5, lowest fifth of {predictor} minus highest fifth",
        estimate,
        samples,
        len(frame),
    )


# --------------------------------------------------------------------------
# H3. Wind direction at similar wind speed (hourly data)
# --------------------------------------------------------------------------
SECTORS = {
    "N": (337.5, 22.5),
    "NE": (22.5, 67.5),
    "E": (67.5, 112.5),
    "NW": (292.5, 337.5),
}


def sector_of(direction: np.ndarray) -> np.ndarray:
    """Label 'N', 'NE', 'E', 'NW' for the 45-degree sectors of the test, '' for any other direction."""
    d = np.mod(np.asarray(direction, float), 360)
    out = np.full(d.shape, "", dtype=object)
    out[(d >= 337.5) | (d < 22.5)] = "N"
    out[(d >= 22.5) & (d < 67.5)] = "NE"
    out[(d >= 67.5) & (d < 112.5)] = "E"
    out[(d >= 292.5) & (d < 337.5)] = "NW"
    return out


def h3_prepare(hourly: pd.DataFrame) -> pd.DataFrame:
    """Winter hours with PM2.5, wind between 3 (excluded) and 10 km/h (included), and a sector of the test.

    ``group`` is 'A' for E and NE and 'B' for N and NW. Local time is UTC+5.
    """
    h = hourly[
        ["datetime_utc", "pm25", "era5_wind_speed_10m", "era5_wind_direction_10m"]
    ].copy()
    local = pd.DatetimeIndex(pd.to_datetime(h["datetime_utc"], utc=True)).tz_localize(
        None
    ) + pd.Timedelta(hours=UTC_OFFSET_HOURS)
    h["local_time"] = local
    h["date"] = local.normalize()
    h = h[is_winter(local) & h["pm25"].notna()].copy()
    return h


def h3_direction(
    hourly: pd.DataFrame, block_days: int = BLOCK_DAYS, n_resamples: int = N_RESAMPLES
) -> dict:
    """Mean PM2.5 of hours with wind from E or NE minus that with wind from N or NW, wind 3 to 10 km/h."""
    h = h3_prepare(hourly)
    days_all = pd.DatetimeIndex(
        sorted(h["date"].unique())
    )  # days with any valid PM2.5 are the resampling units
    eligible = h[
        (h["era5_wind_speed_10m"] > 3) & (h["era5_wind_speed_10m"] <= 10)
    ].copy()
    eligible["sector"] = sector_of(eligible["era5_wind_direction_10m"].to_numpy())
    eligible = eligible[eligible["sector"] != ""]
    eligible["group"] = np.where(eligible["sector"].isin(["E", "NE"]), "A", "B")
    pos = pd.Series(np.arange(len(days_all)), index=days_all)
    sums = np.zeros((len(days_all), 4))
    for (date, group), g in eligible.groupby(["date", "group"]):
        col = 0 if group == "A" else 2
        sums[pos[date], col] = g["pm25"].sum()
        sums[pos[date], col + 1] = len(g)

    def stat(idx: np.ndarray, starts: np.ndarray) -> float:
        s = sums[idx].sum(axis=0)
        return float(s[0] / s[1] - s[2] / s[3]) if s[1] > 0 and s[3] > 0 else math.nan

    samples = bootstrap(stat, days_all, block_days, n_resamples)
    estimate = stat(np.arange(len(days_all)), np.zeros(len(days_all), bool))
    res = _result(
        "H3 wind direction (E+NE minus N+NW, mean hourly PM2.5, ug/m3)",
        estimate,
        samples,
        len(eligible),
        hours_A=int((eligible["group"] == "A").sum()),
        hours_B=int((eligible["group"] == "B").sum()),
        mean_A=float(eligible.loc[eligible["group"] == "A", "pm25"].mean()),
        mean_B=float(eligible.loc[eligible["group"] == "B", "pm25"].mean()),
        days=len(days_all),
    )
    res["decision"] = decide_difference(
        estimate, res["lo_adj"], res["hi_adj"], H3_MIN_DIFFERENCE
    )
    return res


def h3_regression(
    hourly: pd.DataFrame, block_days: int = BLOCK_DAYS, n_resamples: int = N_RESAMPLES
) -> dict:
    """Secondary: OLS of log PM2.5 on wind-speed bin, direction group and hour of day (eligible winter hours).

    The 'winter indicator' named in the plan is constant, because only winter hours are
    used, so it is left out. Hours with PM2.5 of 0 are dropped (the logarithm is undefined).
    The coefficient is the difference in log PM2.5 between the E+NE group and the N+NW
    group, so exp(coefficient) is a ratio.
    """
    h = h3_prepare(hourly)
    days_all = pd.DatetimeIndex(sorted(h["date"].unique()))
    e = h[
        (h["era5_wind_speed_10m"] > 3)
        & (h["era5_wind_speed_10m"] <= 10)
        & (h["pm25"] > 0)
    ].copy()
    e["sector"] = sector_of(e["era5_wind_direction_10m"].to_numpy())
    e = e[e["sector"] != ""]
    group_a = e["sector"].isin(["E", "NE"]).to_numpy(float)
    speed_bin = pd.cut(
        e["era5_wind_speed_10m"], [3, 5, 7, 10], labels=["3-5", "5-7", "7-10"]
    )
    hours = pd.DatetimeIndex(e["local_time"]).hour
    cols = [np.ones(len(e)), group_a]
    cols += [(speed_bin == b).to_numpy(float) for b in ("5-7", "7-10")]
    cols += [(hours == k).astype(float) for k in range(1, 24)]
    X = np.column_stack(cols)
    y = np.log(e["pm25"].to_numpy(float))
    pos = pd.Series(np.arange(len(days_all)), index=days_all)
    day_pos = pos.reindex(pd.DatetimeIndex(e["date"])).to_numpy()
    rows_by_day = [np.flatnonzero(day_pos == i) for i in range(len(days_all))]

    def coefficient(rows: np.ndarray) -> float:
        beta = np.linalg.lstsq(X[rows], y[rows], rcond=None)[0]
        return float(beta[1])

    def stat(idx: np.ndarray, starts: np.ndarray) -> float:
        rows = np.concatenate([rows_by_day[i] for i in idx])
        return coefficient(rows) if len(rows) else math.nan

    samples = bootstrap(stat, days_all, block_days, n_resamples)
    estimate = coefficient(np.arange(len(y)))
    res = _result(
        "H3 secondary: log PM2.5 coefficient of E+NE versus N+NW",
        estimate,
        samples,
        len(e),
    )
    res["ratio"] = math.exp(estimate)
    res["ratio_lo_raw"] = math.exp(res["lo_raw"])
    res["ratio_hi_raw"] = math.exp(res["hi_raw"])
    return res


# --------------------------------------------------------------------------
# H4. Weekday and weekend
# --------------------------------------------------------------------------
def h4_weekend_ratio(
    daily: pd.DataFrame,
    block_days: int = BLOCK_DAYS,
    n_resamples: int = N_RESAMPLES,
    winter_only: bool = True,
    year: int | None = None,
    name: str | None = None,
) -> dict:
    """Mean daily PM2.5 on Saturdays and Sundays divided by that on Monday to Friday.

    ``year`` restricts the test to one winter (the year in which it started).
    """
    frame = _winter_daily(daily, [], all_year=not winter_only)
    if year is not None:
        frame = frame[winter_year(frame.index) == year]
    y = frame["pm25_mean"].to_numpy(float)
    weekend = (frame.index.day_of_week >= 5).astype(float)
    packed = np.column_stack([y * weekend, weekend, y * (1 - weekend), 1 - weekend])

    def stat(idx: np.ndarray, starts: np.ndarray) -> float:
        s = packed[idx].sum(axis=0)
        return (
            float((s[0] / s[1]) / (s[2] / s[3])) if s[1] > 0 and s[3] > 0 else math.nan
        )

    samples = bootstrap(stat, frame.index, block_days, n_resamples)
    estimate = stat(np.arange(len(y)), np.zeros(len(y), bool))
    res = _result(
        name or "H4 weekend over weekday ratio of mean daily PM2.5",
        estimate,
        samples,
        len(frame),
        weekend_days=int(weekend.sum()),
        weekday_days=int((1 - weekend).sum()),
    )
    res["decision"] = decide_equivalence(estimate, res["lo_adj"], res["hi_adj"])
    return res


# --------------------------------------------------------------------------
# H5. Persistence and weather
# --------------------------------------------------------------------------
H5_PREDICTORS = ["era5_wind_mean", "era5_blh_mean", "era5_temp_mean", "era5_msl_mean"]


def _lag1_correlation(values: np.ndarray, starts: np.ndarray) -> float:
    """Correlation between each value and the one before it, never pairing across block starts."""
    now, before = values[1:], values[:-1]
    keep = ~starts[1:]
    if keep.sum() < 3:
        return math.nan
    a, b = now[keep], before[keep]
    if a.std() == 0 or b.std() == 0:
        return math.nan
    return float(np.corrcoef(a, b)[0, 1])


def h5_persistence(
    daily: pd.DataFrame, block_days: int = BLOCK_DAYS, n_resamples: int = N_RESAMPLES
) -> dict:
    """Drop in the lag-1 autocorrelation of log daily PM2.5 after removing the linear effect of same-day weather."""
    frame = _winter_daily(daily, H5_PREDICTORS)
    frame = frame[frame["pm25_mean"] > 0]
    y = np.log(frame["pm25_mean"].to_numpy(float))
    X = np.column_stack([np.ones(len(frame)), frame[H5_PREDICTORS].to_numpy(float)])
    days = frame.index

    def stat(idx: np.ndarray, starts: np.ndarray) -> np.ndarray:
        ys, Xs = y[idx], X[idx]
        beta = np.linalg.lstsq(Xs, ys, rcond=None)[0]  # refitted in every resample
        resid = ys - Xs @ beta
        before, after = _lag1_correlation(ys, starts), _lag1_correlation(resid, starts)
        return np.array([before, after, before - after])

    samples = bootstrap(stat, days, block_days, n_resamples)
    original = stat(np.arange(len(y)), run_starts(days))
    res = _result(
        "H5 drop in lag-1 autocorrelation of log PM2.5 after removing same-day weather",
        original[2],
        samples[:, 2],
        len(frame),
        acf_log_pm25=float(original[0]),
        acf_residual=float(original[1]),
    )
    res["decision"] = decide_reduction(original[2], res["lo_adj"], res["hi_adj"])
    return res


# --------------------------------------------------------------------------
# The primary family
# --------------------------------------------------------------------------
def primary_family(
    daily: pd.DataFrame,
    hourly: pd.DataFrame,
    block_days: int = BLOCK_DAYS,
    n_resamples: int = N_RESAMPLES,
) -> pd.DataFrame:
    """The seven primary tests (H1, H2a, H2b, H2c, H3, H4, H5) for one block length."""
    results = [
        ("H1", h1_winters_differ(daily, block_days, n_resamples)),
        (
            "H2a",
            h2_correlation(
                daily,
                "era5_wind_mean",
                "H2a Spearman: PM2.5 and mean wind speed",
                block_days,
                n_resamples,
            ),
        ),
        (
            "H2b",
            h2_correlation(
                daily,
                "era5_blh_mean",
                "H2b Spearman: PM2.5 and mean boundary layer height",
                block_days,
                n_resamples,
            ),
        ),
        (
            "H2c",
            h2_correlation(
                daily,
                "era5_vent_mean",
                "H2c Spearman: PM2.5 and ventilation index",
                block_days,
                n_resamples,
            ),
        ),
        ("H3", h3_direction(hourly, block_days, n_resamples)),
        ("H4", h4_weekend_ratio(daily, block_days, n_resamples)),
        ("H5", h5_persistence(daily, block_days, n_resamples)),
    ]
    rows = []
    for label, r in results:
        rows.append({"id": label, "block_days": block_days, **r})
    return pd.DataFrame(rows)
