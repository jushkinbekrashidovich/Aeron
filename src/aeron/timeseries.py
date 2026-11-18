"""Small time-series tools that work on series with gaps.

The daily PM2.5 series has 119 separate runs of consecutive days, and the longest
is 158 days. Classical autocorrelation functions assume an unbroken series, so
these functions use only pairs of days that both exist. No gap is filled.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def pairwise_acf(series: pd.Series, nlags: int) -> np.ndarray:
    """Autocorrelation at lags 1..nlags from pairs of days that are both observed.

    ``series`` must be on a regular daily (or hourly) grid with NaN for missing days.
    """
    return np.array([series.corr(series.shift(k)) for k in range(1, nlags + 1)])


def pacf_from_acf(acf: np.ndarray) -> np.ndarray:
    """Partial autocorrelation at lags 1..len(acf) from autocorrelations (Durbin-Levinson)."""
    n = len(acf)
    pacf = np.zeros(n)
    phi_prev = np.zeros(n)
    for k in range(n):
        if k == 0:
            phi_kk = acf[0]
            phi_now = np.array([phi_kk])
        else:
            num = acf[k] - np.dot(phi_prev[:k], acf[:k][::-1])
            den = 1.0 - np.dot(phi_prev[:k], acf[:k])
            phi_kk = num / den
            phi_now = np.concatenate(
                [phi_prev[:k] - phi_kk * phi_prev[:k][::-1], [phi_kk]]
            )
        pacf[k] = phi_kk
        phi_prev[: k + 1] = phi_now
    return pacf


def effective_sample_size(n: int, acf: np.ndarray, floor: float = 0.05) -> float:
    """n / (1 + 2 * sum of autocorrelations), summing until the first lag at or below ``floor``.

    A rough guide to how many independent observations n autocorrelated days are worth.
    """
    total = 0.0
    for value in acf:
        if value <= floor:
            break
        total += value
    return n / (1.0 + 2.0 * total)


def runs_of_observed(series: pd.Series) -> pd.Series:
    """Lengths of the runs of consecutive observed values, longest first."""
    observed = series.notna().astype(int)
    run_id = (observed.diff() != 0).cumsum()
    runs = observed.groupby(run_id).agg(["first", "size"])
    return runs[runs["first"] == 1]["size"].sort_values(ascending=False)


def seasonal_climatology(series: pd.Series, window: int = 31) -> pd.Series:
    """Day-of-year mean, smoothed circularly over ``window`` days, indexed 1..366."""
    by_day = series.groupby(series.index.day_of_year).mean().reindex(range(1, 367))
    half = window // 2
    padded = pd.concat([by_day.iloc[-half:], by_day, by_day.iloc[:half]])
    smooth = (
        padded.rolling(window, center=True, min_periods=half).mean().iloc[half:-half]
    )
    smooth.index = range(1, 367)
    return smooth
