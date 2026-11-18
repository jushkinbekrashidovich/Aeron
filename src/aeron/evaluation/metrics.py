"""Metrics for point forecasts, threshold events, probabilities and uncertainty.

Conventions: errors are prediction minus truth, PM2.5 is in ug/m3, and every
function ignores pairs where truth or prediction is missing, returning the number
of pairs used (``n``) so that results can be read next to their sample size.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score

MAPE_MIN_TRUE = 10.0  # ug/m3: MAPE ignores days with a lower observed value


def _pairs(y, pred) -> tuple[np.ndarray, np.ndarray]:
    y = np.asarray(y, dtype=float)
    pred = np.asarray(pred, dtype=float)
    ok = ~(np.isnan(y) | np.isnan(pred))
    return y[ok], pred[ok]


def point_metrics(y, pred) -> dict:
    """MAE, RMSE, bias and R2 (1 - SSE / SST, against the mean of the observed values)."""
    y, pred = _pairs(y, pred)
    n = len(y)
    if n == 0:
        return {
            "n": 0,
            "mae": math.nan,
            "rmse": math.nan,
            "bias": math.nan,
            "r2": math.nan,
        }
    err = pred - y
    sst = float(((y - y.mean()) ** 2).sum())
    r2 = 1.0 - float((err**2).sum()) / sst if sst > 0 else math.nan
    return {
        "n": n,
        "mae": float(np.abs(err).mean()),
        "rmse": float(math.sqrt((err**2).mean())),
        "bias": float(err.mean()),
        "r2": r2,
    }


def mape(y, pred, min_true: float = MAPE_MIN_TRUE) -> float:
    """Mean absolute percentage error over days with an observed value of at least ``min_true``.

    A percentage error blows up when the observed value is near zero, so smaller
    values are left out. Report ``min_true`` together with the result. The project
    does not use MAPE as a main metric.
    """
    y, pred = _pairs(y, pred)
    keep = y >= min_true
    if not keep.any():
        return math.nan
    return float(np.mean(np.abs(pred[keep] - y[keep]) / y[keep]) * 100)


def skill_score(mae_model: float, mae_reference: float) -> float:
    """1 - MAE of the model over MAE of a reference (positive means better than the reference)."""
    return 1.0 - mae_model / mae_reference if mae_reference else math.nan


def slice_metrics(
    frame: pd.DataFrame, truth: str, preds: list[str], slices: dict[str, pd.Series]
) -> pd.DataFrame:
    """Point metrics for every prediction column within every slice.

    ``slices`` maps a slice name to a boolean mask aligned with ``frame`` (for example
    winter days, or days with an observed value above a threshold). Note that slicing
    on the observed value, as with high-pollution days, selects on the outcome and
    makes errors look worse than they would for a forecaster who did not know the outcome.
    """
    rows = []
    for slice_name, mask in slices.items():
        sub = frame[mask.to_numpy() if hasattr(mask, "to_numpy") else mask]
        for col in preds:
            rows.append(
                {
                    "slice": slice_name,
                    "prediction": col,
                    **point_metrics(sub[truth], sub[col]),
                }
            )
    return pd.DataFrame(rows)


def event_metrics(y, pred, threshold: float) -> dict:
    """Precision, recall and F1 for 'value at or above threshold', with the always-yes F1.

    ``pred`` is a predicted value. An event is predicted when it is at or above the threshold.
    """
    y, pred = _pairs(y, pred)
    truth, flag = y >= threshold, pred >= threshold
    tp = float((truth & flag).sum())
    fp = float((~truth & flag).sum())
    fn = float((truth & ~flag).sum())
    n = len(y)
    base_rate = float(truth.mean()) if n else math.nan
    return {
        "n": n,
        "events": int(truth.sum()),
        "base_rate": base_rate,
        "precision": tp / (tp + fp) if tp + fp else math.nan,
        "recall": tp / (tp + fn) if tp + fn else math.nan,
        "f1": 2 * tp / (2 * tp + fp + fn) if tp else 0.0,
        "always_yes_f1": 2 * base_rate / (1 + base_rate) if n else math.nan,
    }


def probability_metrics(y, prob, threshold: float, bins: int = 10) -> dict:
    """AUC, average precision, Brier score and skill, and expected calibration error."""
    y, prob = _pairs(y, prob)
    event = (y >= threshold).astype(float)
    n = len(y)
    if n == 0 or event.min() == event.max():
        return {
            "n": n,
            "auc": math.nan,
            "ap": math.nan,
            "brier": math.nan,
            "brier_skill": math.nan,
            "ece": math.nan,
        }
    base = event.mean()
    brier = float(np.mean((prob - event) ** 2))
    brier_ref = float(np.mean((base - event) ** 2))
    return {
        "n": n,
        "auc": float(roc_auc_score(event, prob)),
        "ap": float(average_precision_score(event, prob)),
        "brier": brier,
        "brier_skill": 1.0 - brier / brier_ref,
        "ece": expected_calibration_error(event, prob, bins),
    }


def expected_calibration_error(event, prob, bins: int = 10) -> float:
    """Mean absolute gap between predicted probability and observed frequency, equal-count bins."""
    event, prob = np.asarray(event, dtype=float), np.asarray(prob, dtype=float)
    order = np.argsort(prob, kind="stable")
    total = 0.0
    for idx in np.array_split(order, bins):
        if len(idx):
            total += len(idx) * abs(prob[idx].mean() - event[idx].mean())
    return total / len(event)


def reliability_table(event, prob, bins: int = 5) -> pd.DataFrame:
    """Mean predicted probability, observed frequency and count per equal-count bin."""
    event, prob = np.asarray(event, dtype=float), np.asarray(prob, dtype=float)
    rows = []
    for idx in np.array_split(np.argsort(prob, kind="stable"), bins):
        rows.append(
            {
                "mean_predicted": prob[idx].mean(),
                "observed": event[idx].mean(),
                "n": len(idx),
            }
        )
    return pd.DataFrame(rows)


def quantile_coverage(y, quantile_pred) -> dict:
    """Share of observed values at or below an upper-quantile forecast."""
    y, q = _pairs(y, quantile_pred)
    return {"n": len(y), "coverage": float((y <= q).mean()) if len(y) else math.nan}


def block_ids(days: pd.Series, block_days: int = 14) -> np.ndarray:
    """Block number of each row: consecutive calendar blocks of ``block_days`` days."""
    d = pd.to_datetime(days).reset_index(drop=True)
    return ((d - d.min()).dt.days // block_days).to_numpy()


def paired_block_bootstrap(
    days: pd.Series,
    loss_a,
    loss_b,
    block_days: int = 14,
    n_resamples: int = 5000,
    level: float = 0.95,
    seed: int = 0,
) -> dict:
    """Mean difference in loss (a - b) with a block bootstrap interval.

    ``loss_a`` and ``loss_b`` are per-row losses of two methods on the same rows (for
    example absolute errors). Rows are grouped into consecutive blocks of ``block_days``
    calendar days and whole blocks are resampled together, so dependence between
    neighbouring days is kept and the comparison stays paired. Negative differences mean
    method a has the lower loss.
    """
    a, b = np.asarray(loss_a, dtype=float), np.asarray(loss_b, dtype=float)
    keep = ~(np.isnan(a) | np.isnan(b))
    ids = block_ids(pd.Series(pd.to_datetime(days).to_numpy()[keep]), block_days)
    diff = (a - b)[keep]
    _, inverse = np.unique(ids, return_inverse=True)
    n_blocks = inverse.max() + 1
    sums = np.bincount(inverse, weights=diff, minlength=n_blocks)
    counts = np.bincount(inverse, minlength=n_blocks).astype(float)
    rng = np.random.default_rng(seed)
    picks = rng.integers(0, n_blocks, size=(n_resamples, n_blocks))
    resampled = sums[picks].sum(axis=1) / counts[picks].sum(axis=1)
    lo, hi = np.percentile(resampled, [(1 - level) / 2 * 100, (1 + level) / 2 * 100])
    return {
        "n": int(keep.sum()),
        "blocks": int(n_blocks),
        "diff": float(diff.mean()),
        "lo": float(lo),
        "hi": float(hi),
    }
