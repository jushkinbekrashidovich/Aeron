"""Error analysis by pollution level, using the rolling-origin predictions.

Usage:
    python -m aeron.error_analysis

Uses the out-of-sample predictions from rolling_eval.py (winter blocks only,
rows where all methods have a prediction). GBM B uses observed ERA5 weather at
the target hour, so it is an upper bound.

Outputs, for each lead time:
  1. MAE and bias (prediction minus truth) by observed PM2.5 level.
  2. Hourly exceedance detection: precision, recall and F1 for PM2.5 above a
     threshold, with the same threshold applied to truth and prediction.
  3. The same for daily means (days with at least 18 observed target hours).
Levels follow the US EPA PM2.5 breakpoints: 12.0, 35.4 and 55.4 ug/m3.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from aeron.gbm_experiment import LEADS, load
from aeron.rolling_eval import METHODS, pooled_predictions

BINS = [0, 12.1, 35.5, 55.5, 100, 150.5, np.inf]
LABELS = ["<12", "12-35", "35.5-55", "55.5-100", "100-150", ">150"]
HOURLY_THRESHOLDS = (55.5, 100.0)
DAILY_THRESHOLDS = (35.5, 55.5)


def by_level(res: pd.DataFrame) -> pd.DataFrame:
    res = res.assign(level=pd.cut(res["truth"], BINS, labels=LABELS, right=False))
    rows = []
    for level, g in res.groupby("level", observed=True):
        row = {"level": level, "n": len(g), "mean_truth": g["truth"].mean()}
        for m in METHODS:
            err = g[m] - g["truth"]
            row[f"{m}_MAE"] = err.abs().mean()
            row[f"{m}_bias"] = err.mean()
        rows.append(row)
    return pd.DataFrame(rows).set_index("level")


def detection(truth: pd.Series, pred: pd.Series, threshold: float) -> dict:
    t = truth >= threshold
    p = pred >= threshold
    tp = int((t & p).sum())
    fp = int((~t & p).sum())
    fn = int((t & ~p).sum())
    precision = tp / (tp + fp) if tp + fp else float("nan")
    recall = tp / (tp + fn) if tp + fn else float("nan")
    f1 = (
        2 * precision * recall / (precision + recall)
        if tp and not math.isnan(precision) and not math.isnan(recall)
        else 0.0
    )
    return {
        "events": int(t.sum()),
        "base_rate": float(t.mean()),  # precision of always predicting an event
        "precision": precision,
        "recall": recall,
        "F1": f1,
    }


def detection_table(res: pd.DataFrame, thresholds) -> pd.DataFrame:
    rows = []
    for thr in thresholds:
        for m in METHODS:
            d = detection(res["truth"], res[m], thr)
            rows.append({"threshold": thr, "method": m, **d})
    return pd.DataFrame(rows)


def daily(res: pd.DataFrame) -> pd.DataFrame:
    day = res["target_time"].dt.floor("D")
    g = res.groupby(day)
    out = g[["truth", *METHODS]].mean()
    out["hours"] = g.size()
    return out[out["hours"] >= 18].drop(columns="hours")


def main() -> None:
    df = load()
    pd.set_option("display.width", 160)
    for lead in LEADS:
        allres = pooled_predictions(df, lead)
        res = allres[allres["group"] == "winter"].dropna(subset=METHODS)
        print(f"\n=== lead {lead} h, winter, n = {len(res)} hours ===")
        print("\nMAE and bias by observed level (ug/m3):")
        table = by_level(res)
        cols = ["n", "mean_truth"] + [
            f"{m}_{k}" for m in METHODS for k in ("MAE", "bias")
        ]
        print(table[cols].round(1).to_string())
        print("\nHourly exceedance detection:")
        print(detection_table(res, HOURLY_THRESHOLDS).round(2).to_string(index=False))
        d = daily(res)
        print(f"\nDaily means, n = {len(d)} days. Exceedance detection:")
        print(detection_table(d, DAILY_THRESHOLDS).round(2).to_string(index=False))
        daily_mae = {m: float(np.mean(np.abs(d[m] - d["truth"]))) for m in METHODS}
        print("Daily-mean MAE:", {k: round(v, 1) for k, v in daily_mae.items()})


if __name__ == "__main__":
    main()
