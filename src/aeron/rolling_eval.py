"""Rolling-origin evaluation by season, with block-bootstrap intervals.

Usage:
    python -m aeron.rolling_eval

Test blocks alternate between winters (Nov-Feb) and the rest of the year
(Mar-Oct), from winter 2020-21 to winter 2024-25. For each block, models are
trained on all targets before the block starts (expanding window) and scored on
targets inside the block. Variant B uses ERA5 weather at the target hour, so it
is an upper bound (see gbm_experiment.py and gbm_forecast_weather.py).

Uncertainty: pooled errors are resampled in 7-day blocks (paired across methods)
to get 95% intervals for MAE and for MAE differences between methods.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

from aeron.gbm_experiment import LEADS, PARAMS, build, load

TEST_END = pd.Timestamp("2025-02-25 23:00")
BLOCKS = []
for year in range(2020, 2025):
    BLOCKS.append(
        (f"winter {year}-{str(year + 1)[2:]}", f"{year}-11-01", f"{year + 1}-02-28")
    )
    if year < 2024:
        BLOCKS.append((f"mar-oct {year + 1}", f"{year + 1}-03-01", f"{year + 1}-10-31"))
BLOCKS.sort(key=lambda b: b[1])
BOOT = 1000
BLOCK_HOURS = 168
rng = np.random.default_rng(0)


def climatology_pred(train_df: pd.DataFrame, target_time: pd.Series) -> np.ndarray:
    clim = train_df.groupby([train_df.index.month, train_df.index.hour])["pm25"].mean()
    return np.array([clim.get((t.month, t.hour), np.nan) for t in target_time])


def run_block(df, lead, start, end, feats):
    a, b = feats
    base_ok = a["y"].notna() & a["y_origin"].notna()
    in_train = base_ok & (a["target_time"] < start)
    in_test = base_ok & a["target_time"].between(start, min(end, TEST_END))
    if in_test.sum() == 0:
        return None
    test_t = a.loc[in_test, "target_time"]
    cols_a = [c for c in a.columns if c not in ("y", "y_origin", "target_time")]
    cols_b = [c for c in b.columns if c not in ("y", "y_origin", "target_time")]
    ma = HistGradientBoostingRegressor(**PARAMS).fit(
        a.loc[in_train, cols_a], a.loc[in_train, "y"]
    )
    mb = HistGradientBoostingRegressor(**PARAMS).fit(
        b.loc[in_train, cols_b], b.loc[in_train, "y"]
    )
    train_df = df[df.index < start]
    out = pd.DataFrame(
        {
            "target_time": test_t.to_numpy(),
            "truth": a.loc[in_test, "y"].to_numpy(),
            "persistence": a.loc[in_test, "y_origin"].to_numpy(),
            "climatology": climatology_pred(train_df, test_t),
            "gbm_A": ma.predict(a.loc[in_test, cols_a]),
            "gbm_B": mb.predict(b.loc[in_test, cols_b]),
        }
    )
    return out


METHODS = ["persistence", "climatology", "gbm_A", "gbm_B"]


def block_bootstrap(res: pd.DataFrame, pairs):
    """95% intervals for MAE per method and MAE differences, 7-day blocks."""
    hours = (res["target_time"] - pd.Timestamp("2018-01-01")) // pd.Timedelta(hours=1)
    ids = (hours // BLOCK_HOURS).to_numpy()
    uniq, inverse = np.unique(ids, return_inverse=True)
    abs_err = {m: np.abs(res[m].to_numpy() - res["truth"].to_numpy()) for m in METHODS}
    n_blocks = len(uniq)
    sums = {m: np.bincount(inverse, abs_err[m], n_blocks) for m in METHODS}
    counts = np.bincount(inverse, minlength=n_blocks).astype(float)
    stats = {m: [] for m in METHODS}
    diffs = {p: [] for p in pairs}
    for _ in range(BOOT):
        pick = rng.integers(0, n_blocks, n_blocks)
        n = counts[pick].sum()
        mae = {m: sums[m][pick].sum() / n for m in METHODS}
        for m in METHODS:
            stats[m].append(mae[m])
        for p in pairs:
            diffs[p].append(mae[p[0]] - mae[p[1]])
    ci = lambda v: tuple(np.percentile(v, [2.5, 97.5]))
    return {m: ci(stats[m]) for m in METHODS}, {p: ci(diffs[p]) for p in pairs}


def pooled_predictions(df: pd.DataFrame, lead: int) -> pd.DataFrame:
    """Out-of-sample predictions of all methods over all rolling test blocks."""
    feats = (build(df, lead, False), build(df, lead, True))
    parts = []
    for name, start, end in BLOCKS:
        res = run_block(df, lead, pd.Timestamp(start), pd.Timestamp(end), feats)
        if res is None:
            continue
        res["block"] = name
        res["group"] = "winter" if name.startswith("winter") else "other"
        parts.append(res)
    return pd.concat(parts, ignore_index=True)


def main() -> None:
    df = load()
    pairs = [("gbm_B", "climatology"), ("gbm_A", "climatology"), ("gbm_B", "gbm_A")]
    for lead in LEADS:
        allres = pooled_predictions(df, lead)
        print(f"\n=== lead {lead} h: MAE by block (ug/m3), n = rows ===")
        table = allres.groupby("block", sort=False).apply(
            lambda g: pd.Series(
                {"n": len(g)}
                | {m: np.mean(np.abs(g[m] - g["truth"])) for m in METHODS}
                | {"mean_truth": g["truth"].mean()}
            ),
            include_groups=False,
        )
        print(table.round(1).to_string())
        for group in ("winter", "other"):
            sub = allres[allres["group"] == group].dropna(subset=METHODS)
            mae_ci, diff_ci = block_bootstrap(sub, pairs)
            print(f"\n{group} pooled, n = {len(sub)}, 95% block-bootstrap intervals")
            for m in METHODS:
                v = np.mean(np.abs(sub[m] - sub["truth"]))
                print(
                    f"  MAE {m:12s} {v:5.1f}  [{mae_ci[m][0]:.1f}, {mae_ci[m][1]:.1f}]"
                )
            for p in pairs:
                v = np.mean(np.abs(sub[p[0]] - sub["truth"])) - np.mean(
                    np.abs(sub[p[1]] - sub["truth"])
                )
                lo, hi = diff_ci[p]
                print(f"  MAE {p[0]} - {p[1]}: {v:+.1f}  [{lo:+.1f}, {hi:+.1f}]")


if __name__ == "__main__":
    main()
