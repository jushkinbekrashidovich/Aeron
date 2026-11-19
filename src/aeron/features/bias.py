"""Bias correction of forecast weather using only forecasts from before a cutoff.

Archived wind forecasts are biased low at this location (about 2.5 km/h, a third of
the mean). A correction factor is estimated on days up to ``cutoff`` where both the
forecast and the observed (ERA5) value exist, and applied to all days. Because the
factor is fitted on days before the cutoff, which is a block's train cutoff, nothing
from the test period is used.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def fit_ratio(
    forecast: pd.Series, observed: pd.Series, cutoff: pd.Timestamp, min_days: int = 60
) -> float | None:
    """Ratio of mean observed to mean forecast over days on or before ``cutoff``.

    Returns None if fewer than ``min_days`` days have both values, so a caller never
    corrects with a factor learned from too little data.
    """
    both = pd.concat([forecast, observed], axis=1, keys=["f", "o"]).dropna()
    both = both[both.index <= pd.Timestamp(cutoff)]
    if len(both) < min_days or both["f"].mean() <= 0:
        return None
    return float(both["o"].mean() / both["f"].mean())


def correct_wind(speed_forecast: pd.Series, ratio: float | None) -> pd.Series:
    """Scale a forecast wind speed series by the fitted ratio (unchanged if there is none)."""
    return speed_forecast if ratio is None else speed_forecast * ratio


def correct_wind_vector(
    u: pd.Series, v: pd.Series, ratio: float | None
) -> tuple[pd.Series, pd.Series]:
    """Scale both components, which changes the speed and keeps the direction."""
    return correct_wind(u, ratio), correct_wind(v, ratio)


def bias_report(
    forecast: pd.Series,
    observed: pd.Series,
    ratio: float | None,
    days: pd.DatetimeIndex,
) -> dict:
    """Bias and MAE of the forecast before and after correction on the given days."""
    both = (
        pd.concat([forecast, observed], axis=1, keys=["f", "o"]).reindex(days).dropna()
    )
    corrected = correct_wind(both["f"], ratio)
    return {
        "n": len(both),
        "bias_before": float((both["f"] - both["o"]).mean()) if len(both) else np.nan,
        "bias_after": float((corrected - both["o"]).mean()) if len(both) else np.nan,
        "mae_before": float((both["f"] - both["o"]).abs().mean())
        if len(both)
        else np.nan,
        "mae_after": float((corrected - both["o"]).abs().mean())
        if len(both)
        else np.nan,
    }
