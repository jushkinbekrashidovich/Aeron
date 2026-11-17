"""Models aimed at high PM2.5, compared on the rolling-origin winter blocks.

Usage:
    python -m aeron.upper_tail

All models use feature set B from gbm_experiment.py (PM2.5 lags, calendar and
ERA5 weather at the target hour), so the weather input is observed rather than
forecast and results are an upper bound. Winter blocks only (Nov-Feb, winters
2020-21 to 2024-25), expanding window, same parameters as the other experiments
unless noted. Nothing is tuned on the test blocks.

Point forecasts of PM2.5:
  mse        squared-error loss (the earlier model B)
  log        squared error on log(1 + PM2.5), predictions transformed back
  weighted   squared error with sample weights 1 + y / 35 (high values count more)
  q50, q90   quantile loss for the median and the 90th percentile
Exceedance probabilities (classifiers) for PM2.5 >= 55.5 and >= 100 ug/m3.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import (
    HistGradientBoostingClassifier,
    HistGradientBoostingRegressor,
)
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

from aeron.gbm_experiment import LEADS, PARAMS, build, load
from aeron.rolling_eval import BLOCKS, TEST_END

THRESHOLDS = (55.5, 100.0)
BINS = [0, 35.5, 100, 150.5, np.inf]
LABELS = ["<35.5", "35.5-100", "100-150", ">150"]
WEIGHT_SCALE = 35.0


def fit_predict(feats: pd.DataFrame, train: pd.Series, test: pd.Series) -> dict:
    cols = [c for c in feats.columns if c not in ("y", "y_origin", "target_time")]
    x_tr, y_tr = feats.loc[train, cols], feats.loc[train, "y"]
    x_te = feats.loc[test, cols]
    out = {}
    out["mse"] = HistGradientBoostingRegressor(**PARAMS).fit(x_tr, y_tr).predict(x_te)
    m = HistGradientBoostingRegressor(**PARAMS).fit(x_tr, np.log1p(y_tr))
    out["log"] = np.expm1(m.predict(x_te))
    m = HistGradientBoostingRegressor(**PARAMS).fit(
        x_tr, y_tr, sample_weight=1 + y_tr / WEIGHT_SCALE
    )
    out["weighted"] = m.predict(x_te)
    for name, q in (("q50", 0.5), ("q90", 0.9)):
        m = HistGradientBoostingRegressor(loss="quantile", quantile=q, **PARAMS)
        out[name] = m.fit(x_tr, y_tr).predict(x_te)
    for thr in THRESHOLDS:
        clf = HistGradientBoostingClassifier(**PARAMS).fit(x_tr, y_tr >= thr)
        out[f"p{thr:g}"] = clf.predict_proba(x_te)[:, 1]
    return out


def collect(df: pd.DataFrame, lead: int) -> pd.DataFrame:
    feats = build(df, lead, True)
    ok = feats["y"].notna() & feats["y_origin"].notna()
    parts = []
    for name, start, end in BLOCKS:
        if not name.startswith("winter"):
            continue
        start, end = pd.Timestamp(start), min(pd.Timestamp(end), TEST_END)
        train = ok & (feats["target_time"] < start)
        test = ok & feats["target_time"].between(start, end)
        preds = fit_predict(feats, train, test)
        res = pd.DataFrame(
            {
                "block": name,
                "target_time": feats.loc[test, "target_time"].to_numpy(),
                "truth": feats.loc[test, "y"].to_numpy(),
                "persistence": feats.loc[test, "y_origin"].to_numpy(),
                **preds,
            }
        )
        parts.append(res)
    return pd.concat(parts, ignore_index=True)


def detection(truth: np.ndarray, flag: np.ndarray) -> tuple[float, float, float]:
    t = truth
    tp = float((t & flag).sum())
    fp = float((~t & flag).sum())
    fn = float((t & ~flag).sum())
    precision = tp / (tp + fp) if tp + fp else float("nan")
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * tp / (2 * tp + fp + fn) if tp else 0.0
    return precision, recall, f1


def point_table(res: pd.DataFrame) -> pd.DataFrame:
    truth = res["truth"].to_numpy()
    level = pd.cut(res["truth"], BINS, labels=LABELS, right=False)
    rows = []
    for m in ("persistence", "mse", "log", "weighted", "q50", "q90"):
        pred = res[m].to_numpy()
        err = pred - truth
        row = {"method": m, "MAE": np.abs(err).mean(), "RMSE": np.sqrt((err**2).mean())}
        for lab in LABELS[1:]:
            row[f"bias {lab}"] = err[(level == lab).to_numpy()].mean()
        for thr in THRESHOLDS:
            p, r, f = detection(truth >= thr, pred >= thr)
            row[f"P@{thr:g}"], row[f"R@{thr:g}"], row[f"F1@{thr:g}"] = p, r, f
        rows.append(row)
    return pd.DataFrame(rows).set_index("method")


def probability_table(res: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for thr in THRESHOLDS:
        y = (res["truth"] >= thr).to_numpy()
        p = res[f"p{thr:g}"].to_numpy()
        base = y.mean()
        row = {
            "threshold": thr,
            "base_rate": base,
            "AUC": roc_auc_score(y, p),
            "AP": average_precision_score(y, p),
            "Brier": brier_score_loss(y, p),
            "Brier_base": brier_score_loss(y, np.full_like(p, base)),
        }
        for cut in (0.5, 0.3, 0.2):
            _pr, rc, f1 = detection(y, p >= cut)
            row[f"F1@p>={cut}"] = f1
            row[f"R@p>={cut}"] = rc
        rows.append(row)
    return pd.DataFrame(rows).set_index("threshold")


def main() -> None:
    df = load()
    pd.set_option("display.width", 200)
    pd.set_option("display.max_columns", 30)
    for lead in LEADS:
        res = collect(df, lead).dropna(subset=["truth", "persistence", "mse"])
        print(f"\n=== lead {lead} h, winter, n = {len(res)} hours ===")
        print("\nPoint forecasts (bias = prediction minus truth, by observed level):")
        print(point_table(res).round(2).to_string())
        print("\nq90 coverage (share of truth at or below q90 forecast):")
        covered = res["truth"] <= res["q90"]
        level = pd.cut(res["truth"], BINS, labels=LABELS, right=False)
        print(
            f"  all {covered.mean():.2f}; by observed level:",
            {lab: round(float(covered[level == lab].mean()), 2) for lab in LABELS},
        )
        print("\nExceedance probabilities:")
        print(probability_table(res).round(3).to_string())


if __name__ == "__main__":
    main()
