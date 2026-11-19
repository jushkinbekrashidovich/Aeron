"""Summaries of model predictions for reports and experiment tracking."""

from __future__ import annotations

import pandas as pd

from aeron.evaluation import metrics

GROUPS = ("winter", "other", "all")
EVENT_THRESHOLD = 55.5  # ug/m3, daily mean


def _subset(pred: pd.DataFrame, group: str) -> pd.DataFrame:
    return pred if group == "all" else pred[pred["season"] == group]


def summarize(
    pred: pd.DataFrame, models: list[str], threshold: float = EVENT_THRESHOLD
) -> pd.DataFrame:
    """Point and event metrics of every model for winter, other months and all rows.

    ``pred`` has the columns ``y``, ``season`` and one column per model. Rows with a
    missing prediction are skipped for that model (``n`` shows how many were used).
    """
    rows = []
    for group in GROUPS:
        sub = _subset(pred, group)
        for model in models:
            point = metrics.point_metrics(sub["y"], sub[model])
            event = metrics.event_metrics(sub["y"], sub[model], threshold)
            rows.append(
                {
                    "group": group,
                    "model": model,
                    **point,
                    "events": event["events"],
                    "base_rate": event["base_rate"],
                    "precision": event["precision"],
                    "recall": event["recall"],
                    "f1": event["f1"],
                    "always_yes_f1": event["always_yes_f1"],
                }
            )
    return pd.DataFrame(rows)


def per_block_mae(pred: pd.DataFrame, models: list[str]) -> pd.DataFrame:
    """MAE of every model in every test block (blocks in time order)."""
    order = pred.groupby("block", sort=False)["target_date"].min().sort_values().index
    table = {}
    for model in models:
        table[model] = {
            block: metrics.point_metrics(g["y"], g[model])["mae"]
            for block, g in pred.groupby("block")
        }
    out = pd.DataFrame(table).reindex(order)
    out.insert(0, "days", pred.groupby("block")["y"].count().reindex(order))
    return out


def paired_difference(
    pred: pd.DataFrame,
    model_a: str,
    model_b: str,
    group: str = "winter",
    block_days: int = 14,
) -> dict:
    """Mean absolute error of a minus that of b, with a block bootstrap interval (negative: a is better)."""
    sub = _subset(pred, group).dropna(subset=["y", model_a, model_b])
    loss_a = (sub[model_a] - sub["y"]).abs()
    loss_b = (sub[model_b] - sub["y"]).abs()
    return metrics.paired_block_bootstrap(
        sub["target_date"], loss_a, loss_b, block_days=block_days
    )
