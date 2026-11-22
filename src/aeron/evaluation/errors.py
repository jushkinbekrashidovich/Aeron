"""Error analysis of daily PM2.5 forecasts (task 4.1).

Every function takes a prediction table like the one ``run_models`` returns: the columns
``target_date``, ``y``, ``season`` and one column per model. Errors are
``prediction - observed`` in ug/m3, so a negative value means the forecast was too low.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

LEVEL_EDGES = (0, 25, 55.5, 100, np.inf)
LEVEL_LABELS = ("<25", "25-55.5", "55.5-100", ">=100")


def error_by_level(
    pred: pd.DataFrame, model: str, edges=LEVEL_EDGES, labels=LEVEL_LABELS
) -> pd.DataFrame:
    """MAE, bias and share of days by the level of the observed daily mean."""
    sub = pred.dropna(subset=["y", model]).copy()
    sub["error"] = sub[model] - sub["y"]
    sub["level"] = pd.cut(sub["y"], list(edges), labels=list(labels), right=False)
    grouped = sub.groupby("level", observed=False)["error"]
    out = pd.DataFrame(
        {
            "days": grouped.size(),
            "mae": grouped.apply(lambda e: e.abs().mean()),
            "bias": grouped.mean(),
        }
    )
    out["share_of_days"] = out["days"] / out["days"].sum()
    out["share_of_abs_error"] = (
        grouped.apply(lambda e: e.abs().sum()) / sub["error"].abs().sum()
    )
    return out


def error_by_month(pred: pd.DataFrame, model: str) -> pd.DataFrame:
    sub = pred.dropna(subset=["y", model]).copy()
    sub["error"] = sub[model] - sub["y"]
    sub["month"] = pd.DatetimeIndex(sub["target_date"]).month
    grouped = sub.groupby("month")["error"]
    return pd.DataFrame(
        {
            "days": grouped.size(),
            "mae": grouped.apply(lambda e: e.abs().mean()),
            "bias": grouped.mean(),
        }
    )


def error_by_weekday(pred: pd.DataFrame, model: str) -> pd.DataFrame:
    sub = pred.dropna(subset=["y", model]).copy()
    sub["error"] = sub[model] - sub["y"]
    sub["weekday"] = pd.DatetimeIndex(sub["target_date"]).day_name()
    grouped = sub.groupby("weekday")["error"]
    out = pd.DataFrame(
        {
            "days": grouped.size(),
            "mae": grouped.apply(lambda e: e.abs().mean()),
            "bias": grouped.mean(),
        }
    )
    order = [
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
    ]
    return out.reindex(order)


def error_autocorrelation(pred: pd.DataFrame, model: str, max_lag: int = 5) -> dict:
    """Correlation of the error with the error ``k`` calendar days earlier (pairs of days only)."""
    sub = pred.dropna(subset=["y", model])
    error = pd.Series(
        (sub[model] - sub["y"]).to_numpy(),
        index=pd.DatetimeIndex(sub["target_date"]),
    ).sort_index()
    out = {}
    for lag in range(1, max_lag + 1):
        shifted = error.copy()
        shifted.index = shifted.index + pd.Timedelta(days=lag)
        both = pd.concat([error, shifted], axis=1, keys=["now", "before"]).dropna()
        out[lag] = float(both["now"].corr(both["before"])) if len(both) > 2 else np.nan
    return out


def find_episodes(
    pred: pd.DataFrame, model: str, threshold: float = 100.0, min_days: int = 2
) -> pd.DataFrame:
    """Runs of at least ``min_days`` consecutive days with an observed daily mean at or above ``threshold``.

    Each row summarises one episode: length, observed peak and mean, mean forecast, and
    the number of its days on which the forecast reached the 55.5 ug/m3 alert level.
    """
    sub = pred.dropna(subset=["y", model]).sort_values("target_date")
    days = pd.DatetimeIndex(sub["target_date"])
    high = (sub["y"] >= threshold).to_numpy()
    run_id = np.cumsum(
        np.r_[True, (np.diff(days.values).astype("timedelta64[D]").astype(int) != 1)]
        | np.r_[True, high[1:] != high[:-1]]
    )
    rows = []
    for _, run in sub.assign(run=run_id)[high].groupby("run"):
        if len(run) < min_days:
            continue
        rows.append(
            {
                "start": run["target_date"].min().date(),
                "end": run["target_date"].max().date(),
                "days": len(run),
                "peak_observed": run["y"].max(),
                "mean_observed": run["y"].mean(),
                "mean_forecast": run[model].mean(),
                "mean_error": (run[model] - run["y"]).mean(),
                "days_alerted": int((run[model] >= 55.5).sum()),
            }
        )
    return pd.DataFrame(rows)


def false_alarm_runs(
    pred: pd.DataFrame, model: str, alert: float = 55.5, min_days: int = 2
) -> pd.DataFrame:
    """Runs of at least ``min_days`` consecutive days with the forecast at or above ``alert`` and the observation below it."""
    sub = pred.dropna(subset=["y", model]).sort_values("target_date")
    days = pd.DatetimeIndex(sub["target_date"])
    false = ((sub[model] >= alert) & (sub["y"] < alert)).to_numpy()
    breaks = np.r_[True, np.diff(days.values).astype("timedelta64[D]").astype(int) != 1]
    run_id = np.cumsum(breaks | np.r_[True, false[1:] != false[:-1]])
    rows = []
    for _, run in sub.assign(run=run_id)[false].groupby("run"):
        if len(run) < min_days:
            continue
        rows.append(
            {
                "start": run["target_date"].min().date(),
                "end": run["target_date"].max().date(),
                "days": len(run),
                "mean_forecast": run[model].mean(),
                "mean_observed": run["y"].mean(),
            }
        )
    return pd.DataFrame(rows)


def tail_performance(
    pred: pd.DataFrame, model: str, threshold: float = 100.0, alert: float = 55.5
) -> dict:
    """How the model does on the days that matter most (observed at or above ``threshold``)."""
    sub = pred.dropna(subset=["y", model])
    high = sub[sub["y"] >= threshold]
    if high.empty:
        return {"days": 0}
    error = high[model] - high["y"]
    return {
        "days": len(high),
        "mean_error": float(error.mean()),
        "mae": float(error.abs().mean()),
        "share_forecast_at_alert": float((high[model] >= alert).mean()),
        "share_forecast_at_threshold": float((high[model] >= threshold).mean()),
    }


def rolling_mae(pred: pd.DataFrame, model: str, window_days: int = 28) -> pd.Series:
    """MAE over a trailing calendar window of ``window_days`` target days."""
    sub = pred.dropna(subset=["y", model])
    loss = pd.Series(
        (sub[model] - sub["y"]).abs().to_numpy(),
        index=pd.DatetimeIndex(sub["target_date"]),
    ).sort_index()
    return loss.rolling(f"{window_days}D", min_periods=max(5, window_days // 4)).mean()
