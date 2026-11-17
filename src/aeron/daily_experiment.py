"""Daily-mean PM2.5 forecasts for 1, 2 and 3 days ahead (US Embassy station).

Usage:
    python -m aeron.daily_experiment

Days are local days (Asia/Tashkent, UTC+5). A forecast is issued at the end of
local day O, using data up to the end of O, for the daily mean of day O + k,
k = 1, 2, 3. A daily mean needs at least 18 observed hours.

Feature sets:
  A  PM2.5 history only (daily means of the last 7 days, 7 and 14 day means,
     previous evening mean, previous day maximum) and calendar of the target day.
  W  A plus ERA5 weather aggregated over the target day (observed, so this is a
     perfect weather forecast and an upper bound).
  S  W plus boundary layer height and ventilation (ERA5 only, with a gap from
     2024-01-01 to 2024-06-30).

Baselines: persistence (mean of day O), climatology (training-period mean within
15 days of the same day of year), and always predicting an exceedance.

Evaluation uses the winter blocks of rolling_eval.py (target days in Nov-Feb,
winters 2020-21 to 2024-25, expanding window, target days before the block are
the training set). Model settings are fixed and not tuned on test data.
Intervals: 95% percentile intervals from 1,000 resamples of 7-day blocks.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import (
    HistGradientBoostingClassifier,
    HistGradientBoostingRegressor,
)
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

from aeron.gbm_experiment import load
from aeron.rolling_eval import BLOCKS, TEST_END
from aeron.stagnation_experiment import extra_series

LEADS = (1, 2, 3)
THRESHOLDS = (35.5, 55.5)
UTC_OFFSET = pd.Timedelta(hours=5)
PARAMS = {
    "max_iter": 200,
    "learning_rate": 0.05,
    "max_depth": 4,
    "min_samples_leaf": 20,
    "l2_regularization": 1.0,
    "random_state": 0,
}
BOOT = 1000
rng = np.random.default_rng(0)


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


def daily_frame() -> pd.DataFrame:
    """Daily PM2.5 and weather aggregates indexed by local date."""
    df = load()
    ex = extra_series(df)
    h = pd.DataFrame(index=df.index)
    h["pm25"] = df["pm25"]
    for c in (
        "temperature_2m",
        "relative_humidity_2m",
        "precipitation",
        "surface_pressure",
        "cloud_cover",
        "wind_speed_10m",
        "wind_gusts_10m",
    ):
        h[c] = df[c]
    for c in ("ex_ssr", "ex_vpd", "ex_msl", "ex_snow", "ex_blh", "ex_vent"):
        h[c] = ex[c]
    h.index = h.index + UTC_OFFSET  # local time
    day = h.index.floor("D")
    g = h.groupby(day)
    d = pd.DataFrame(index=g.size().index)
    count = g["pm25"].count()
    d["pm_mean"] = g["pm25"].mean().where(count >= 18)
    d["pm_max"] = g["pm25"].max().where(count >= 18)
    eve = h[h.index.hour >= 18].groupby(h.index[h.index.hour >= 18].floor("D"))["pm25"]
    d["pm_eve"] = eve.mean().where(eve.count() >= 4)
    add_weather(d, g)
    d["b_blh_mean"] = g["ex_blh"].mean()
    d["b_blh_min"] = g["ex_blh"].min()
    d["b_vent_mean"] = g["ex_vent"].mean()
    # Drop incomplete first and last days.
    return d.iloc[1:-1]


def build(d: pd.DataFrame, k: int) -> dict[str, pd.DataFrame]:
    f = pd.DataFrame(index=d.index)
    for j in range(7):
        f[f"pm_lag{j}"] = d["pm_mean"].shift(j)
    f["pm_roll7"] = d["pm_mean"].rolling(7, min_periods=4).mean()
    f["pm_roll14"] = d["pm_mean"].rolling(14, min_periods=8).mean()
    f["pm_eve"] = d["pm_eve"]
    f["pm_max0"] = d["pm_max"]
    target_day = d.index + pd.Timedelta(days=k)
    f["doy_sin"] = np.sin(2 * np.pi * target_day.day_of_year / 365.25)
    f["doy_cos"] = np.cos(2 * np.pi * target_day.day_of_year / 365.25)
    f["month"] = target_day.month
    f["dow"] = target_day.day_of_week
    weather = d[[c for c in d.columns if c.startswith("w_")]].shift(-k)
    blh = d[[c for c in d.columns if c.startswith("b_")]].shift(-k)
    out = {
        "A": f,
        "W": pd.concat([f, weather], axis=1),
        "S": pd.concat([f, weather, blh], axis=1),
    }
    meta = pd.DataFrame(
        {
            "target_day": target_day,
            "y": d["pm_mean"].shift(-k),
            "y_origin": d["pm_mean"],
        },
        index=d.index,
    )
    return out, meta


def climatology(train_days: pd.Series, train_values: pd.Series, target_day) -> float:
    doy = train_days.dt.day_of_year.to_numpy()
    diff = np.abs(doy - target_day.day_of_year)
    diff = np.minimum(diff, 365 - diff)
    sel = diff <= 15
    return float(train_values.to_numpy()[sel].mean()) if sel.any() else np.nan


def collect(d: pd.DataFrame, k: int) -> pd.DataFrame:
    sets, meta = build(d, k)
    ok = meta["y"].notna() & meta["y_origin"].notna()
    parts = []
    for name, start, end in BLOCKS:
        if not name.startswith("winter"):
            continue
        start, end = pd.Timestamp(start), min(pd.Timestamp(end), TEST_END.floor("D"))
        train = ok & (meta["target_day"] < start)
        test = ok & meta["target_day"].between(start, end)
        if test.sum() == 0:
            continue
        res = pd.DataFrame(
            {
                "block": name,
                "target_day": meta.loc[test, "target_day"].to_numpy(),
                "truth": meta.loc[test, "y"].to_numpy(),
                "persistence": meta.loc[test, "y_origin"].to_numpy(),
            }
        )
        res["climatology"] = [
            climatology(meta.loc[train, "target_day"], meta.loc[train, "y"], t)
            for t in meta.loc[test, "target_day"]
        ]
        for s, feats in sets.items():
            x_tr, y_tr, x_te = feats.loc[train], meta.loc[train, "y"], feats.loc[test]
            res[f"{s}_mse"] = (
                HistGradientBoostingRegressor(**PARAMS).fit(x_tr, y_tr).predict(x_te)
            )
            for thr in THRESHOLDS:
                clf = HistGradientBoostingClassifier(**PARAMS).fit(x_tr, y_tr >= thr)
                res[f"{s}_p{thr:g}"] = clf.predict_proba(x_te)[:, 1]
        parts.append(res)
    return pd.concat(parts, ignore_index=True)


def f1(truth: np.ndarray, flag: np.ndarray) -> float:
    tp = float((truth & flag).sum())
    return (
        2 * tp / (2 * tp + (~truth & flag).sum() + (truth & ~flag).sum()) if tp else 0.0
    )


def bootstrap(res: pd.DataFrame, a: str, b: str) -> tuple[float, float, float]:
    err_a = np.abs(res[a] - res["truth"]).to_numpy()
    err_b = np.abs(res[b] - res["truth"]).to_numpy()
    weeks = ((res["target_day"] - pd.Timestamp("2018-01-01")).dt.days // 7).to_numpy()
    _, inverse = np.unique(weeks, return_inverse=True)
    n = inverse.max() + 1
    sums = np.bincount(inverse, err_a - err_b, n)
    counts = np.bincount(inverse, minlength=n).astype(float)
    vals = []
    for _ in range(BOOT):
        pick = rng.integers(0, n, n)
        vals.append(sums[pick].sum() / counts[pick].sum())
    lo, hi = np.percentile(vals, [2.5, 97.5])
    return float(np.mean(err_a - err_b)), float(lo), float(hi)


def report(res: pd.DataFrame, k: int) -> None:
    print(f"\n=== lead {k} day(s), winter, n = {len(res)} days ===")
    rows = []
    for m in ("persistence", "climatology", "A_mse", "W_mse", "S_mse"):
        err = res[m] - res["truth"]
        rows.append(
            {
                "method": m,
                "MAE": err.abs().mean(),
                "RMSE": np.sqrt((err**2).mean()),
                "bias": err.mean(),
            }
        )
    print(pd.DataFrame(rows).set_index("method").round(1).to_string())
    print("MAE differences (negative = first is better), 95% interval:")
    for a, b in (
        ("W_mse", "climatology"),
        ("W_mse", "persistence"),
        ("W_mse", "A_mse"),
        ("S_mse", "W_mse"),
        ("A_mse", "climatology"),
    ):
        diff, lo, hi = bootstrap(res, a, b)
        print(f"  {a} - {b}: {diff:+.1f} [{lo:+.1f}, {hi:+.1f}]")
    for thr in THRESHOLDS:
        y = (res["truth"] >= thr).to_numpy()
        base = y.mean()
        print(
            f"\nDaily mean >= {thr:g}: {int(y.sum())} days, base rate {base:.2f}, "
            f"always-yes F1 {2 * base / (1 + base):.2f}"
        )
        rows = []
        for m in ("persistence", "climatology"):
            rows.append({"method": m, "F1": f1(y, (res[m] >= thr).to_numpy())})
        for s in ("A", "W", "S"):
            p = res[f"{s}_p{thr:g}"].to_numpy()
            skill = 1 - brier_score_loss(y, p) / brier_score_loss(
                y, np.full_like(p, base)
            )
            rows.append(
                {
                    "method": f"{s} classifier",
                    "F1": f1(y, p >= 0.5),
                    "F1@p>=0.3": f1(y, p >= 0.3),
                    "AUC": roc_auc_score(y, p),
                    "AP": average_precision_score(y, p),
                    "BrierSkill": skill,
                }
            )
        print(pd.DataFrame(rows).set_index("method").round(2).to_string())
    print("\nMAE by winter:")
    print(
        res.groupby("block", sort=False)
        .apply(
            lambda g: pd.Series(
                {
                    "days": len(g),
                    "mean": g["truth"].mean(),
                    **{
                        m: (g[m] - g["truth"]).abs().mean()
                        for m in (
                            "persistence",
                            "climatology",
                            "A_mse",
                            "W_mse",
                            "S_mse",
                        )
                    },
                }
            ),
            include_groups=False,
        )
        .round(1)
        .to_string()
    )


def main() -> None:
    d = daily_frame()
    pd.set_option("display.width", 200)
    print(f"Daily frame: {len(d)} days, {d['pm_mean'].notna().sum()} with a daily mean")
    for k in LEADS:
        res = collect(d, k).dropna(subset=["truth", "persistence", "climatology"])
        report(res, k)


if __name__ == "__main__":
    main()
