"""Prediction intervals and exceedance probabilities for the daily PM2.5 forecast (task 4.3).

Method (decided with the project owner): split-conformal intervals around the point
forecast, plus Platt-scaled probabilities of exceeding an alert level.

For every walk-forward block the training rows are split like the tuning split in
``train_validation_split``: the last 365 target days are the calibration year and the
fitting part stops ``lead`` days before it. A copy of the model is fitted on the fitting
part only and forecasts the calibration year, so the calibration errors are honest
out-of-sample errors. The model used for the test days is refitted on all training rows.

From the calibration errors ``y - forecast``:

- ``plain`` intervals add fixed quantiles of the error to the forecast;
- ``scaled`` intervals use quantiles of ``(y - forecast) / max(forecast, floor)``, so
  the interval is wider on polluted days (the errors grow with the level, see the error
  analysis). Both are asymmetric, because the errors are skewed.
- the probability of exceeding a threshold comes from (a) logistic regression of the
  event on the forecast (Platt scaling) and (b) the share of calibration errors that
  would put the observation at or above the threshold ("conformal probability").

Limits: coverage is guaranteed on average only if calibration and test days are
exchangeable. Days in a spell are not, and the calibration year uses observed weather
where the real-forecast test uses archived forecasts, so coverage can fall short.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

from aeron.evaluation.splits import train_validation_split, walk_forward
from aeron.features import build_features, observed_as_forecast
from aeron.models.baselines import Context

LEVELS = (0.8, 0.9)
THRESHOLDS = (55.5, 35.5)
FLOOR = 15.0
CALIBRATION_DAYS = 365
# The calibration model tunes itself on its own last year, so it needs more than a year of rows.
MIN_FIT_DAYS = 500


def _quantile(values: np.ndarray, q: float) -> float:
    """Empirical quantile with the finite-sample rank (n + 1) used in conformal prediction."""
    n = len(values)
    rank = min(max(int(np.ceil((n + 1) * q)), 1), n)
    return float(np.sort(values)[rank - 1])


def _scale(forecast: np.ndarray, floor: float) -> np.ndarray:
    return np.maximum(forecast, floor)


class IntervalCalibrator:
    """Learns interval widths and exceedance probabilities from calibration errors."""

    def __init__(
        self,
        levels=LEVELS,
        thresholds=THRESHOLDS,
        floor: float = FLOOR,
    ) -> None:
        self.levels = tuple(levels)
        self.thresholds = tuple(thresholds)
        self.floor = floor

    def fit(self, forecast, observed) -> IntervalCalibrator:
        f = np.clip(np.asarray(forecast, dtype=float), 0, None)
        y = np.asarray(observed, dtype=float)
        keep = ~(np.isnan(f) | np.isnan(y))
        f, y = f[keep], y[keep]
        if len(f) < 30:
            raise ValueError("too few calibration days")
        self._f, self._y = f, y
        self._plain = y - f
        self._scaled = (y - f) / _scale(f, self.floor)
        self.quantiles = {}
        for level in self.levels:
            lo_q, hi_q = (1 - level) / 2, 1 - (1 - level) / 2
            self.quantiles[level] = {
                "plain": (_quantile(self._plain, lo_q), _quantile(self._plain, hi_q)),
                "scaled": (
                    _quantile(self._scaled, lo_q),
                    _quantile(self._scaled, hi_q),
                ),
            }
        self.platt = {}
        self.base_rate = {}
        for thr in self.thresholds:
            event = y >= thr
            self.base_rate[thr] = float(event.mean())
            if event.min() == event.max():
                self.platt[thr] = None
            else:
                self.platt[thr] = LogisticRegression(C=1e4).fit(
                    f[:, None] / 100.0, event
                )
        return self

    def intervals(self, forecast) -> pd.DataFrame:
        f = np.clip(np.asarray(forecast, dtype=float), 0, None)
        out = {}
        for level, q in self.quantiles.items():
            tag = round(level * 100)
            lo, hi = q["plain"]
            out[f"lo{tag}_plain"] = np.clip(f + lo, 0, None)
            out[f"hi{tag}_plain"] = f + hi
            lo, hi = q["scaled"]
            scale = _scale(f, self.floor)
            out[f"lo{tag}_scaled"] = np.clip(f + lo * scale, 0, None)
            out[f"hi{tag}_scaled"] = f + hi * scale
        return pd.DataFrame(out)

    def probabilities(self, forecast) -> pd.DataFrame:
        f = np.clip(np.asarray(forecast, dtype=float), 0, None)
        out = {}
        for thr in self.thresholds:
            tag = f"{thr:g}"
            model = self.platt[thr]
            out[f"p{tag}_platt"] = (
                model.predict_proba(f[:, None] / 100.0)[:, 1]
                if model is not None
                else np.full(len(f), self.base_rate[thr])
            )
            needed = (thr - f) / _scale(
                f, self.floor
            )  # scaled error needed to reach it
            out[f"p{tag}_conformal"] = (self._scaled[None, :] >= needed[:, None]).mean(
                axis=1
            )
            out[f"p{tag}_base"] = np.full(len(f), self.base_rate[thr])
        return pd.DataFrame(out)


def run_intervals(
    daily: pd.DataFrame,
    make_model,
    lead: int,
    blocks,
    views=("observed", "forecast"),
    min_train_days: int = 365,
    calibration_days: int = CALIBRATION_DAYS,
    min_fit_days: int = MIN_FIT_DAYS,
    levels=LEVELS,
    thresholds=THRESHOLDS,
) -> dict[str, pd.DataFrame]:
    """Point forecasts, intervals and probabilities for every test day of every block.

    Returns one table per view (``observed`` or ``forecast``, as in ``run_models``) with
    the columns of ``run_models`` (``origin_date``, ``target_date``, ``y``, ``block``,
    ``season``, ``lead``), ``pred``, the interval columns and the probability columns.
    Blocks with fewer than ``min_fit_days`` fitting rows (the earliest ones) are skipped.
    """
    table = build_features(daily, lead)
    series = daily["pm25_mean"].copy()
    series.index = pd.DatetimeIndex(series.index)
    candidates = table[table["y"].notna()].reset_index(drop=True)
    parts: dict[str, list[pd.DataFrame]] = {v: [] for v in views}
    for split in walk_forward(
        candidates["target_date"], blocks, lead, min_train_days=min_train_days
    ):
        train = candidates.iloc[split.train]
        train = train[train["y"].notna()]
        context = Context(
            lead=lead, test_start=pd.Timestamp(split.block.start), daily_mean=series
        )
        fit_idx, cal_idx = train_validation_split(
            train["target_date"], calibration_days, lead
        )
        if len(fit_idx) < min_fit_days:
            continue  # too little history left to fit and calibrate separately
        calibration_model = make_model().fit(train.iloc[fit_idx], context)
        cal_rows = observed_as_forecast(train.iloc[cal_idx])
        calibrator = IntervalCalibrator(levels, thresholds).fit(
            calibration_model.predict(cal_rows, context), cal_rows["y"]
        )
        final_model = make_model().fit(train, context)
        test_all = candidates.iloc[split.test]
        test_all = test_all[test_all["y_origin"].notna()]
        for view in views:
            test = test_all
            if view == "forecast":
                test = test[test["wxf_temp_mean"].notna()]
            else:
                test = observed_as_forecast(test)
            if test.empty:
                continue
            pred = final_model.predict(test, context)
            out = test[["origin_date", "target_date", "y"]].reset_index(drop=True)
            out["block"] = split.block.name
            out["season"] = split.block.season
            out["lead"] = lead
            out["pred"] = pred
            out = pd.concat(
                [out, calibrator.intervals(pred), calibrator.probabilities(pred)],
                axis=1,
            )
            parts[view].append(out)
    return {v: pd.concat(p, ignore_index=True) for v, p in parts.items() if p}


def coverage(frame: pd.DataFrame, lo: str, hi: str) -> float:
    ok = frame.dropna(subset=["y", lo, hi])
    return float(((ok["y"] >= ok[lo]) & (ok["y"] <= ok[hi])).mean())


def coverage_interval(
    frame: pd.DataFrame,
    lo: str,
    hi: str,
    block_days: int = 14,
    n_resamples: int = 5000,
    seed: int = 0,
) -> dict:
    """Coverage with a block bootstrap 95% interval (blocks of consecutive calendar days)."""
    from aeron.evaluation.metrics import block_ids

    ok = frame.dropna(subset=["y", lo, hi])
    hit = ((ok["y"] >= ok[lo]) & (ok["y"] <= ok[hi])).to_numpy(dtype=float)
    ids = block_ids(pd.Series(pd.to_datetime(ok["target_date"]).to_numpy()), block_days)
    _, inverse = np.unique(ids, return_inverse=True)
    n_blocks = inverse.max() + 1
    sums = np.bincount(inverse, weights=hit, minlength=n_blocks)
    counts = np.bincount(inverse, minlength=n_blocks).astype(float)
    rng = np.random.default_rng(seed)
    picks = rng.integers(0, n_blocks, size=(n_resamples, n_blocks))
    sample = sums[picks].sum(axis=1) / counts[picks].sum(axis=1)
    lo_q, hi_q = np.percentile(sample, [2.5, 97.5])
    return {
        "n": len(ok),
        "coverage": float(hit.mean()),
        "lo": float(lo_q),
        "hi": float(hi_q),
    }


def miss_clustering(frame: pd.DataFrame, lo: str, hi: str) -> dict:
    """Chance of a miss on a day, and on a day right after a miss (consecutive days only)."""
    ok = frame.dropna(subset=["y", lo, hi]).sort_values("target_date")
    miss = ~((ok["y"] >= ok[lo]) & (ok["y"] <= ok[hi]))
    days = pd.DatetimeIndex(ok["target_date"])
    consecutive = np.r_[
        False, np.diff(days.values).astype("timedelta64[D]").astype(int) == 1
    ]
    prev_miss = np.r_[False, miss.to_numpy()[:-1]]
    after = consecutive & prev_miss
    return {
        "miss_rate": float(miss.mean()),
        "miss_rate_after_miss": float(miss.to_numpy()[after].mean())
        if after.any()
        else float("nan"),
        "days_after_miss": int(after.sum()),
    }


def mean_width(frame: pd.DataFrame, lo: str, hi: str) -> float:
    ok = frame.dropna(subset=[lo, hi])
    return float((ok[hi] - ok[lo]).mean())
