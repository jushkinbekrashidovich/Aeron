"""Baseline PM2.5 forecasts for the US Embassy station (standard library only).

Usage:
    python -m aeron.baselines

Split is chronological: climatology is fitted on data before TEST_START, and
forecast targets lie in [TEST_START, TEST_END]. For an origin time t and lead h,
a method predicts PM2.5 at t + h using only values observed at or before t
(climatology uses only the calendar of the target time and the training period).
Pairs where either the origin value or the target is missing are skipped.
"""

from __future__ import annotations

import csv
import math
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PM_FILE = ROOT / "data" / "raw" / "openaq" / "us_embassy_pm25_hourly.csv"
TEST_START = datetime(2024, 1, 1)
TEST_END = datetime(2025, 2, 25, 23)
LEADS = (24, 48, 72)
WINTER = {11, 12, 1, 2}
HOUR = timedelta(hours=1)


def load_pm() -> dict[datetime, float]:
    series = {}
    with PM_FILE.open() as fh:
        for row in csv.DictReader(fh):
            if row["value"] == "":
                continue
            ts = datetime.strptime(row["datetime_utc"], "%Y-%m-%dT%H:%M:%SZ")
            series[ts] = float(row["value"])
    return series


def climatology(series: dict[datetime, float]) -> dict[tuple[int, int], float]:
    """Mean PM2.5 by (month, hour of day) over the training period."""
    sums: dict[tuple[int, int], list[float]] = defaultdict(list)
    for ts, v in series.items():
        if ts < TEST_START:
            sums[(ts.month, ts.hour)].append(v)
    return {k: sum(v) / len(v) for k, v in sums.items()}


def mean_last_24h(series: dict[datetime, float], t: datetime) -> float | None:
    vals = [series[t - i * HOUR] for i in range(24) if (t - i * HOUR) in series]
    return sum(vals) / len(vals) if len(vals) >= 18 else None


def evaluate(series: dict[datetime, float]) -> dict:
    clim = climatology(series)
    errors: dict = defaultdict(lambda: defaultdict(list))
    for target, truth in series.items():
        if not TEST_START <= target <= TEST_END:
            continue
        season = "winter" if target.month in WINTER else "other"
        for lead in LEADS:
            origin = target - lead * HOUR
            if origin not in series:
                continue
            preds = {
                "persistence": series[origin],
                "mean_last_24h": mean_last_24h(series, origin),
                "climatology": clim.get((target.month, target.hour)),
            }
            for name, pred in preds.items():
                if pred is None:
                    continue
                for group in ("all", season):
                    errors[(name, lead, group)]["err"].append(pred - truth)
    return errors


def main() -> None:
    series = load_pm()
    errors = evaluate(series)
    print(f"Test targets {TEST_START:%Y-%m-%d} to {TEST_END:%Y-%m-%d}")
    print("method,lead_h,group,n,MAE,RMSE,bias")
    for (name, lead, group), d in sorted(errors.items()):
        e = d["err"]
        n = len(e)
        mae = sum(abs(x) for x in e) / n
        rmse = math.sqrt(sum(x * x for x in e) / n)
        bias = sum(e) / n
        print(f"{name},{lead},{group},{n},{mae:.1f},{rmse:.1f},{bias:.1f}")


if __name__ == "__main__":
    main()
