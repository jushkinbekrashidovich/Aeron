"""Daily-mean forecasts with archived forecast weather instead of observed weather.

Usage:
    python -m aeron.daily_forecast_weather

Repeats the daily experiment (daily_experiment.py) for the winters 2023-24 and
2024-25, restricted to target days from 2024-01-20, the first local day fully
covered by archived forecasts. Models use feature set W without the snow
variable (no archived forecast of it) and are trained on ERA5 weather before
each block, as in the other notes. At test time the model is scored twice on
identical days: with ERA5 weather for the target day (W_obs, a perfect forecast)
and with the archived forecast for that day (W_fc).

A forecast issued at the end of local day O for day O + k uses the Open-Meteo
forecast made k + 1 days before each valid hour (previous_day{k+1}), so it was
available at least about a day before the origin. Days with fewer than 22
forecast hours are dropped.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import (
    HistGradientBoostingClassifier,
    HistGradientBoostingRegressor,
)
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

from aeron.daily_experiment import (
    BLOCKS,
    LEADS,
    PARAMS,
    TEST_END,
    THRESHOLDS,
    UTC_OFFSET,
    bootstrap,
    build,
    climatology,
    daily_frame,
    f1,
)
from aeron.processing import forecast_weather_daily, read_hourly

ROOT = Path(__file__).resolve().parents[2]
FC_FILE = ROOT / "data" / "raw" / "openmeteo" / "forecast_previous_runs_hourly.csv"
FIRST_DAY = pd.Timestamp("2024-01-20")
NAMES = {
    "temperature_2m": "temperature_2m",
    "relative_humidity_2m": "relative_humidity_2m",
    "precipitation": "precipitation",
    "surface_pressure": "surface_pressure",
    "cloud_cover": "cloud_cover",
    "wind_speed_10m": "wind_speed_10m",
    "wind_gusts_10m": "wind_gusts_10m",
    "shortwave_radiation": "ex_ssr",
    "vapour_pressure_deficit": "ex_vpd",
    "pressure_msl": "ex_msl",
}


def forecast_daily(k: int) -> pd.DataFrame:
    """Daily weather aggregates from forecasts issued k + 1 days earlier."""
    return forecast_weather_daily(read_hourly(FC_FILE), k, UTC_OFFSET)


def collect(d: pd.DataFrame, k: int) -> pd.DataFrame:
    sets, meta = build(d, k)
    fw = forecast_daily(k)
    wcols = [c for c in sets["W"].columns if c.startswith("w_") and c != "w_snow"]
    a_cols = list(sets["A"].columns)
    nowind = [c for c in wcols if c not in ("w_wind_mean", "w_gust_max")]
    w_obs = sets["W"][a_cols + wcols]
    w_fc = w_obs.copy()
    target_day = meta["target_day"]
    for c in wcols:
        w_fc[c] = fw[c].reindex(target_day).to_numpy()
    wn_obs = w_obs[a_cols + nowind]
    wn_fc = w_fc[a_cols + nowind]
    has_fc = w_fc[wcols].notna().all(axis=1)
    ok = meta["y"].notna() & meta["y_origin"].notna()
    parts = []
    for name, start, end in BLOCKS:
        if not name.startswith("winter"):
            continue
        start, end = pd.Timestamp(start), min(pd.Timestamp(end), TEST_END.floor("D"))
        train = ok & (target_day < start)
        test = ok & has_fc & target_day.between(max(start, FIRST_DAY), end)
        if test.sum() == 0:
            continue
        res = pd.DataFrame(
            {
                "block": name,
                "target_day": target_day[test].to_numpy(),
                "truth": meta.loc[test, "y"].to_numpy(),
                "persistence": meta.loc[test, "y_origin"].to_numpy(),
            }
        )
        res["climatology"] = [
            climatology(target_day[train], meta.loc[train, "y"], t)
            for t in target_day[test]
        ]
        y_tr = meta.loc[train, "y"]
        fits = {
            "A": (sets["A"], sets["A"]),
            "W_obs": (w_obs, w_obs),
            "W_fc": (w_obs, w_fc),
            "Wn_obs": (wn_obs, wn_obs),
            "Wn_fc": (wn_obs, wn_fc),
        }
        trained = {}
        for s, (train_x, test_x) in fits.items():
            key = "Wn" if s.startswith("Wn") else ("W" if s.startswith("W") else "A")
            if key not in trained:
                reg = HistGradientBoostingRegressor(**PARAMS).fit(
                    train_x.loc[train], y_tr
                )
                clfs = {
                    thr: HistGradientBoostingClassifier(**PARAMS).fit(
                        train_x.loc[train], y_tr >= thr
                    )
                    for thr in THRESHOLDS
                }
                trained[key] = (reg, clfs)
            reg, clfs = trained[key]
            res[f"{s}_mse"] = reg.predict(test_x.loc[test])
            for thr in THRESHOLDS:
                res[f"{s}_p{thr:g}"] = clfs[thr].predict_proba(test_x.loc[test])[:, 1]
        parts.append(res)
    return pd.concat(parts, ignore_index=True)


def report(res: pd.DataFrame, k: int) -> None:
    print(f"\n=== lead {k} day(s), winter, forecast-weather days, n = {len(res)} ===")
    print(
        "days by winter:",
        res.groupby("block")["truth"].count().to_dict(),
        "mean",
        round(res["truth"].mean(), 1),
    )
    rows = []
    for m in (
        "persistence",
        "climatology",
        "A_mse",
        "W_obs_mse",
        "W_fc_mse",
        "Wn_obs_mse",
        "Wn_fc_mse",
    ):
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
        ("W_fc_mse", "climatology"),
        ("W_fc_mse", "persistence"),
        ("W_fc_mse", "A_mse"),
        ("W_fc_mse", "W_obs_mse"),
        ("Wn_fc_mse", "climatology"),
        ("Wn_fc_mse", "W_fc_mse"),
        ("Wn_fc_mse", "Wn_obs_mse"),
    ):
        diff, lo, hi = bootstrap(res, a, b)
        print(f"  {a} - {b}: {diff:+.1f} [{lo:+.1f}, {hi:+.1f}]")
    for thr in THRESHOLDS:
        y = (res["truth"] >= thr).to_numpy()
        base = y.mean()
        print(
            f"\nDaily mean >= {thr:g}: {int(y.sum())} days, base rate {base:.2f}, always-yes F1 {2 * base / (1 + base):.2f}"
        )
        rows = [
            {
                "method": "persistence",
                "F1": f1(y, (res["persistence"] >= thr).to_numpy()),
            },
            {
                "method": "climatology",
                "F1": f1(y, (res["climatology"] >= thr).to_numpy()),
            },
        ]
        for s in ("A", "W_obs", "W_fc", "Wn_obs", "Wn_fc"):
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


def diagnostics(d: pd.DataFrame, k: int) -> None:
    """Daily forecast weather against ERA5 on days from FIRST_DAY."""
    fw = forecast_daily(k)
    days = fw.index[(fw.index >= FIRST_DAY) & (fw.index <= "2025-02-25")]
    rows = []
    for c in [c for c in fw.columns if c.startswith("w_") and c != "w_snow"]:
        obs, fc = d[c].reindex(days), fw.loc[days, c]
        ok = obs.notna() & fc.notna()
        rows.append(
            {
                "variable": c,
                "obs mean": obs[ok].mean(),
                "bias (fc - obs)": (fc[ok] - obs[ok]).mean(),
                "MAE": (fc[ok] - obs[ok]).abs().mean(),
                "corr": np.corrcoef(fc[ok], obs[ok])[0, 1],
            }
        )
    print(
        f"\nForecast daily weather against ERA5, issued {k + 1} days ahead, {len(days)} days:"
    )
    print(pd.DataFrame(rows).set_index("variable").round(2).to_string())


def main() -> None:
    d = daily_frame()
    pd.set_option("display.width", 200)
    diagnostics(d, 1)
    diagnostics(d, 3)
    for k in LEADS:
        res = collect(d, k).dropna(subset=["truth", "persistence", "climatology"])
        report(res, k)


if __name__ == "__main__":
    main()
