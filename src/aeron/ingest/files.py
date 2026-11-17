"""Helpers for resumable, idempotent downloads to data/raw/."""

from __future__ import annotations

import csv
import os
from datetime import date, timedelta
from pathlib import Path

# A period whose end is within this many days of today may still receive late
# or revised data, so it is downloaded again on every run.
REFRESH_DAYS = 45


def is_final(period_end: date, today: date, refresh_days: int = REFRESH_DAYS) -> bool:
    """True when the period is old enough to be trusted and skipped on reruns.

    ``period_end`` is the first day after the period.
    """
    return period_end <= today - timedelta(days=refresh_days)


def write_rows(path: Path, header: list[str], rows: list[list]) -> None:
    """Write a CSV atomically, so an interrupted run never leaves a partial file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        writer.writerows(rows)
    os.replace(tmp, path)


def read_rows(path: Path) -> tuple[list[str], list[list[str]]]:
    with path.open(newline="") as fh:
        reader = csv.reader(fh)
        header = next(reader)
        return header, list(reader)


def month_ranges(start: date, today: date) -> list[tuple[date, date]]:
    """Calendar months from ``start``'s month through ``today``'s month.

    Each item is (first day of the month, first day of the next month).
    """
    months = []
    year, month = start.year, start.month
    while (year, month) <= (today.year, today.month):
        nxt = (year + 1, 1) if month == 12 else (year, month + 1)
        months.append((date(year, month, 1), date(*nxt, 1)))
        year, month = nxt
    return months
