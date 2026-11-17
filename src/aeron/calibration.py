"""Calibration of exceedance probabilities and the 90th-percentile forecast.

Usage:
    python -m aeron.calibration

Feature set: S_noBLH from stagnation_experiment.py (PM2.5 lags, calendar, ERA5
weather at the target hour and variables that also exist as archived forecasts).
Weather is observed, so results are an upper bound.

Protocol, for each test winter (2021-22 to 2024-25; the first winter has too
little earlier data):
  - the base models are trained on targets before CAL_START = start - 365 days;
  - calibration uses winter rows (Nov-Feb) in [CAL_START, start), i.e. the
    previous winter;
  - test rows are the winter block itself.
Raw and calibrated forecasts come from the same base model, so differences are
due to calibration only. These base models do not see the most recent winter,
so absolute scores are slightly worse than in the other notes.

Methods: isotonic and Platt (logistic) calibration of probabilities; additive
and multiplicative conformal shifts of the 90th-percentile forecast.
Intervals: 1,000 resamples of 7-day blocks of the pooled test rows.
"""

from __future__ import annotations

import itertools
import math

import numpy as np
import pandas as pd
from scipy.special import logit
from sklearn.ensemble import (
    HistGradientBoostingClassifier,
    HistGradientBoostingRegressor,
)
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss

from aeron.gbm_experiment import LEADS, PARAMS, load
from aeron.rolling_eval import BLOCKS, TEST_END
from aeron.stagnation_experiment import feature_sets

THRESHOLDS = (55.5, 100.0)
TEST_WINTERS = [
    b for b in BLOCKS if b[0].startswith("winter") and b[0] != "winter 2020-21"
]
WINTER_MONTHS = [11, 12, 1, 2]
QUANTILE = 0.9
FLOOR = 5.0  # lower bound on the forecast when forming ratio scores
BOOT = 1000
BLOCK_HOURS = 168
rng = np.random.default_rng(0)


def conformal_level(n: int) -> float:
    return min(1.0, math.ceil((n + 1) * QUANTILE) / n)


def fit_models(feats: pd.DataFrame, train: pd.Series) -> dict:
    cols = [c for c in feats.columns if c not in ("y", "y_origin", "target_time")]
    x_tr, y_tr = feats.loc[train, cols], feats.loc[train, "y"]
    models = {
        "q90": HistGradientBoostingRegressor(
            loss="quantile", quantile=QUANTILE, **PARAMS
        ).fit(x_tr, y_tr)
    }
    for thr in THRESHOLDS:
        models[f"p{thr:g}"] = HistGradientBoostingClassifier(**PARAMS).fit(
            x_tr, y_tr >= thr
        )
    return models, cols


def predict(models: dict, cols: list, x: pd.DataFrame) -> dict:
    out = {"q90": models["q90"].predict(x[cols])}
    for thr in THRESHOLDS:
        out[f"p{thr:g}"] = models[f"p{thr:g}"].predict_proba(x[cols])[:, 1]
    return out


def collect(df: pd.DataFrame, lead: int) -> pd.DataFrame:
    feats = feature_sets(df, lead)["S_noBLH"]
    ok = feats["y"].notna() & feats["y_origin"].notna()
    in_winter = feats["target_time"].dt.month.isin(WINTER_MONTHS)
    parts = []
    for name, start, end in TEST_WINTERS:
        start = pd.Timestamp(start)
        end = min(pd.Timestamp(end), TEST_END)
        cal_start = start - pd.Timedelta(days=365)
        train = ok & (feats["target_time"] < cal_start)
        cal = (
            ok
            & in_winter
            & feats["target_time"].between(cal_start, start - pd.Timedelta(hours=1))
        )
        test = ok & feats["target_time"].between(start, end)
        models, cols = fit_models(feats, train)
        p_cal = predict(models, cols, feats.loc[cal])
        p_te = predict(models, cols, feats.loc[test])
        y_cal = feats.loc[cal, "y"].to_numpy()
        res = pd.DataFrame(
            {
                "block": name,
                "target_time": feats.loc[test, "target_time"].to_numpy(),
                "truth": feats.loc[test, "y"].to_numpy(),
            }
        )
        # Quantile forecast: raw and two conformal shifts.
        q_cal, q_te = p_cal["q90"], p_te["q90"]
        level = conformal_level(len(y_cal))
        add = np.quantile(y_cal - q_cal, level, method="higher")
        mult = np.quantile(y_cal / np.maximum(q_cal, FLOOR), level, method="higher")
        res["q_raw"] = q_te
        res["q_add"] = np.maximum(q_te + add, 0)
        res["q_mult"] = np.maximum(q_te, FLOOR) * mult
        # Probabilities: raw, isotonic, Platt.
        for thr in THRESHOLDS:
            key = f"p{thr:g}"
            y_bin = y_cal >= thr
            res[f"{key}_raw"] = p_te[key]
            iso = IsotonicRegression(y_min=0, y_max=1, out_of_bounds="clip")
            res[f"{key}_iso"] = iso.fit(p_cal[key], y_bin).predict(p_te[key])
            clip = lambda p: logit(np.clip(p, 1e-4, 1 - 1e-4)).reshape(-1, 1)
            platt = LogisticRegression(C=1e6).fit(clip(p_cal[key]), y_bin)
            res[f"{key}_platt"] = platt.predict_proba(clip(p_te[key]))[:, 1]
        res["cal_rows"] = len(y_cal)
        parts.append(res)
    return pd.concat(parts, ignore_index=True)


def ece(y: np.ndarray, p: np.ndarray, bins: int = 10) -> float:
    """Expected calibration error with equal-count bins."""
    order = np.argsort(p)
    total = 0.0
    for idx in np.array_split(order, bins):
        total += len(idx) * abs(p[idx].mean() - y[idx].mean())
    return total / len(y)


def block_ids(res: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    hours = (res["target_time"] - pd.Timestamp("2018-01-01")) // pd.Timedelta(hours=1)
    return np.unique((hours // BLOCK_HOURS).to_numpy(), return_inverse=True)


def boot_ci(res: pd.DataFrame, stat) -> tuple[float, float]:
    """95% interval of stat(sub-sample indices weights) under block resampling."""
    _, inverse = block_ids(res)
    n_blocks = inverse.max() + 1
    vals = []
    for _ in range(BOOT):
        pick = rng.integers(0, n_blocks, n_blocks)
        counts = np.bincount(pick, minlength=n_blocks)
        weights = counts[inverse].astype(float)
        vals.append(stat(weights))
    return tuple(np.percentile(vals, [2.5, 97.5]))


def probability_report(res: pd.DataFrame, thr: float) -> None:
    key = f"p{thr:g}"
    y = (res["truth"] >= thr).to_numpy()
    print(f"\nThreshold {thr:g} ug/m3, base rate {y.mean():.3f}")
    rows = []
    for m in ("raw", "iso", "platt"):
        p = np.clip(res[f"{key}_{m}"].to_numpy(), 1e-4, 1 - 1e-4)
        rows.append(
            {
                "method": m,
                "Brier": brier_score_loss(y, p),
                "log loss": log_loss(y, p),
                "ECE": ece(y, p),
                "mean p": p.mean(),
            }
        )
    print(pd.DataFrame(rows).set_index("method").round(4).to_string())
    for m in ("iso", "platt"):
        a = (res[f"{key}_{m}"].to_numpy() - y) ** 2
        b = (res[f"{key}_raw"].to_numpy() - y) ** 2

        def stat(w, a=a, b=b):
            return (w * (a - b)).sum() / w.sum()

        lo, hi = boot_ci(res, stat)
        print(
            f"  Brier {m} - raw: {np.mean(a) - np.mean(b):+.4f}  [{lo:+.4f}, {hi:+.4f}]"
        )
    # Reliability table for the raw and isotonic forecasts.
    print("  Reliability, raw (bin of predicted p: mean p / observed rate / n):")
    p = res[f"{key}_raw"].to_numpy()
    for idx in np.array_split(np.argsort(p), 5):
        print(f"    {p[idx].mean():.2f} / {y[idx].mean():.2f} / {len(idx)}")
    print("  Reliability, isotonic:")
    p = res[f"{key}_iso"].to_numpy()
    for idx in np.array_split(np.argsort(p), 5):
        print(f"    {p[idx].mean():.2f} / {y[idx].mean():.2f} / {len(idx)}")


def quantile_report(res: pd.DataFrame) -> None:
    truth = res["truth"].to_numpy()
    print(f"\n90th-percentile forecast (target coverage {QUANTILE:.2f})")
    for m in ("raw", "add", "mult"):
        q = res[f"q_{m}"].to_numpy()
        covered = (truth <= q).astype(float)

        def stat(w, c=covered):
            return (w * c).sum() / w.sum()

        lo, hi = boot_ci(res, stat)
        by_pred = []
        edges = [-np.inf, 35.5, 100, 200, np.inf]
        for a, b in itertools.pairwise(edges):
            mask = (q >= a) & (q < b)
            by_pred.append(
                f"{covered[mask].mean():.2f} (n={int(mask.sum())})"
                if mask.any()
                else "-"
            )
        print(
            f"  {m:5s} coverage {covered.mean():.3f} [{lo:.3f}, {hi:.3f}]; "
            f"by forecast level <35.5, 35.5-100, 100-200, >200: {', '.join(by_pred)}; "
            f"mean forecast {q.mean():.1f}"
        )
        flag = q >= 100
        t = truth >= 100
        tp = float((t & flag).sum())
        prec = tp / flag.sum() if flag.sum() else float("nan")
        rec = tp / t.sum()
        print(
            f"        alert at forecast >= 100: precision {prec:.2f}, recall {rec:.2f}, alerts {int(flag.sum())}"
        )


def main() -> None:
    df = load()
    pd.set_option("display.width", 160)
    for lead in LEADS:
        res = collect(df, lead).dropna(subset=["truth"])
        print(
            f"\n=== lead {lead} h, test winters 2021-22 to 2024-25, n = {len(res)} ==="
        )
        print(
            "calibration rows per winter:",
            res.groupby("block")["cal_rows"].first().to_dict(),
        )
        for thr in THRESHOLDS:
            probability_report(res, thr)
        quantile_report(res)


if __name__ == "__main__":
    main()
