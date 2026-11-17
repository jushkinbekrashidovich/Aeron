"""Do stagnation inputs help with high PM2.5? Rolling winter blocks.

Usage:
    python -m aeron.stagnation_experiment

Feature sets (all include the PM2.5 lags, calendar and ERA5 weather of set B in
gbm_experiment.py, taken at the target hour):
  B         the earlier set
  S_noBLH   B plus shortwave radiation, vapour pressure deficit, mean sea-level
            pressure and its 24 h change, snow depth, 72 h rain total, 24 h
            mean wind. All of these exist as archived forecasts.
  S         S_noBLH plus boundary layer height (BLH), its 24 h mean and minimum,
            and ventilation (BLH x wind speed). ERA5 only: BLH is not available
            as an archived forecast, and ERA5 BLH is missing 2024-01-01 to
            2024-06-30.

All weather is observed (ERA5) at or before the target hour, so results are an
upper bound. Results are reported on all test rows and on rows where BLH is
present, so the 2024 gap does not distort the comparison. Same winter blocks,
expanding window and fixed model parameters as the other experiments.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import (
    HistGradientBoostingClassifier,
    HistGradientBoostingRegressor,
)
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

from aeron.gbm_experiment import LEADS, PARAMS, ROOT, build, load
from aeron.rolling_eval import BLOCKS, TEST_END
from aeron.upper_tail import BINS, LABELS, detection

EXTRA_FILE = ROOT / "data" / "raw" / "openmeteo" / "era5_extra_tashkent_hourly.csv"
NON_BLH = [
    "ex_ssr",
    "ex_vpd",
    "ex_msl",
    "ex_msl_chg24",
    "ex_snow",
    "ex_rain72",
    "ex_ws_mean24",
]
BLH = ["ex_blh", "ex_blh_mean24", "ex_blh_min24", "ex_vent", "ex_vent_mean24"]


def extra_series(df: pd.DataFrame) -> pd.DataFrame:
    """Stagnation variables indexed by valid time."""
    raw = pd.read_csv(EXTRA_FILE, parse_dates=["datetime_utc"])
    raw["datetime_utc"] = raw["datetime_utc"].dt.tz_localize(None)
    raw = raw.set_index("datetime_utc").reindex(df.index)
    ex = pd.DataFrame(index=df.index)
    ex["ex_ssr"] = raw["shortwave_radiation"]
    ex["ex_vpd"] = raw["vapour_pressure_deficit"]
    ex["ex_msl"] = raw["pressure_msl"]
    ex["ex_msl_chg24"] = raw["pressure_msl"] - raw["pressure_msl"].shift(24)
    ex["ex_snow"] = raw["snow_depth"]
    ex["ex_rain72"] = df["precipitation"].rolling(72, min_periods=60).sum()
    ex["ex_ws_mean24"] = df["wind_speed_10m"].rolling(24, min_periods=18).mean()
    blh = raw["boundary_layer_height"]
    ex["ex_blh"] = blh
    ex["ex_blh_mean24"] = blh.rolling(24, min_periods=18).mean()
    ex["ex_blh_min24"] = blh.rolling(24, min_periods=18).min()
    vent = blh * df["wind_speed_10m"]
    ex["ex_vent"] = vent
    ex["ex_vent_mean24"] = vent.rolling(24, min_periods=18).mean()
    return ex


def feature_sets(df: pd.DataFrame, lead: int) -> dict[str, pd.DataFrame]:
    b = build(df, lead, True)
    ex = extra_series(df).shift(-lead)  # value at the target hour, on the origin row
    s_no = pd.concat([b, ex[NON_BLH]], axis=1)
    s = pd.concat([b, ex[NON_BLH + BLH]], axis=1)
    return {"B": b, "S_noBLH": s_no, "S": s}


def fit_block(feats: pd.DataFrame, train: pd.Series, test: pd.Series) -> dict:
    cols = [c for c in feats.columns if c not in ("y", "y_origin", "target_time")]
    x_tr, y_tr, x_te = (
        feats.loc[train, cols],
        feats.loc[train, "y"],
        feats.loc[test, cols],
    )
    out = {"mse": HistGradientBoostingRegressor(**PARAMS).fit(x_tr, y_tr).predict(x_te)}
    q = HistGradientBoostingRegressor(loss="quantile", quantile=0.9, **PARAMS)
    out["q90"] = q.fit(x_tr, y_tr).predict(x_te)
    for thr in (55.5, 100.0):
        clf = HistGradientBoostingClassifier(**PARAMS).fit(x_tr, y_tr >= thr)
        out[f"p{thr:g}"] = clf.predict_proba(x_te)[:, 1]
    return out


def collect(df: pd.DataFrame, lead: int) -> pd.DataFrame:
    sets = feature_sets(df, lead)
    base = sets["B"]
    ok = base["y"].notna() & base["y_origin"].notna()
    parts = []
    for name, start, end in BLOCKS:
        if not name.startswith("winter"):
            continue
        start, end = pd.Timestamp(start), min(pd.Timestamp(end), TEST_END)
        train = ok & (base["target_time"] < start)
        test = ok & base["target_time"].between(start, end)
        res = pd.DataFrame(
            {
                "block": name,
                "target_time": base.loc[test, "target_time"].to_numpy(),
                "truth": base.loc[test, "y"].to_numpy(),
                "persistence": base.loc[test, "y_origin"].to_numpy(),
                "blh_present": sets["S"].loc[test, "ex_blh"].notna().to_numpy(),
            }
        )
        for set_name, feats in sets.items():
            for model, pred in fit_block(feats, train, test).items():
                res[f"{set_name}_{model}"] = pred
        parts.append(res)
    return pd.concat(parts, ignore_index=True)


def summarize(res: pd.DataFrame) -> pd.DataFrame:
    truth = res["truth"].to_numpy()
    level = pd.cut(res["truth"], BINS, labels=LABELS, right=False)
    rows = []
    for s in ("B", "S_noBLH", "S"):
        err = res[f"{s}_mse"].to_numpy() - truth
        row = {"set": s, "MAE": np.abs(err).mean(), "RMSE": np.sqrt((err**2).mean())}
        for lab in ("100-150", ">150"):
            row[f"bias {lab}"] = err[(level == lab).to_numpy()].mean()
        _p, rec, f1 = detection(truth >= 100, res[f"{s}_q90"].to_numpy() >= 100)
        row["q90 R@100"], row["q90 F1@100"] = rec, f1
        covered = res["truth"] <= res[f"{s}_q90"]
        row["q90 cov >150"] = float(covered[level == ">150"].mean())
        for thr in (55.5, 100.0):
            y = truth >= thr
            p = res[f"{s}_p{thr:g}"].to_numpy()
            skill = 1 - brier_score_loss(y, p) / brier_score_loss(
                y, np.full_like(p, y.mean())
            )
            row[f"AUC@{thr:g}"] = roc_auc_score(y, p)
            row[f"AP@{thr:g}"] = average_precision_score(y, p)
            row[f"BrierSkill@{thr:g}"] = skill
        rows.append(row)
    return pd.DataFrame(rows).set_index("set")


def main() -> None:
    df = load()
    pd.set_option("display.width", 220)
    pd.set_option("display.max_columns", 30)
    for lead in LEADS:
        res = collect(df, lead).dropna(subset=["truth", "persistence"])
        print(f"\n=== lead {lead} h, winter ===")
        print(f"\nAll test rows (n = {len(res)}):")
        print(summarize(res).round(3).to_string())
        sub = res[res["blh_present"]]
        print(f"\nRows with BLH present (n = {len(sub)}):")
        print(summarize(sub).round(3).to_string())


if __name__ == "__main__":
    main()
