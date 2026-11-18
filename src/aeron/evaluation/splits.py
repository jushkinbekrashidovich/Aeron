"""Chronological, leak-free splits for daily forecasts.

A forecast is issued at the end of local day O for the target day D = O + lead.
A model that is used at O can only have been trained on rows whose target is known
at O, that is rows with target day <= O. For a test block starting on day S the
first origin is S - lead, so training rows must have target day <= S - lead.
That gap of ``lead`` days is the walk-forward gap. Without it, the last training
targets would lie after the first test origins.

Blocks follow docs/research/methodology.md: winters (November to February) and the
rest of the year (March to October), in time order, with an expanding training window.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np
import pandas as pd


class LeakageError(AssertionError):
    """Raised when training data would not have been available at forecast time."""


@dataclass(frozen=True)
class Block:
    name: str
    season: str  # "winter" or "other"
    start: date  # first target day of the test block
    end: date  # last target day of the test block (inclusive)


def seasonal_blocks(first_winter: int, last_date: date) -> list[Block]:
    """Winter and non-winter blocks from the winter starting in ``first_winter``.

    Blocks are truncated at ``last_date`` and blocks that start after it are dropped.
    """
    blocks: list[Block] = []
    year = first_winter
    while date(year, 11, 1) <= last_date:
        winter_end = date(year + 1, 3, 1) - timedelta(days=1)  # last day of February
        blocks.append(
            Block(
                f"winter {year}-{str(year + 1)[2:]}",
                "winter",
                date(year, 11, 1),
                winter_end,
            )
        )
        other_start = date(year + 1, 3, 1)
        if other_start <= last_date:
            blocks.append(
                Block(
                    f"mar-oct {year + 1}", "other", other_start, date(year + 1, 10, 31)
                )
            )
        year += 1
    return [
        Block(b.name, b.season, b.start, min(b.end, last_date))
        for b in blocks
        if b.start <= last_date
    ]


def train_cutoff(block: Block, lead_days: int) -> date:
    """Last target day that may be used for training (inclusive)."""
    return block.start - timedelta(days=lead_days)


def assert_no_leakage(
    train_targets: pd.Series, test_targets: pd.Series, lead_days: int
) -> None:
    """Check that every training target is known before the first test forecast is made.

    Both arguments hold target days. The first test origin is the earliest test
    target minus ``lead_days``, and training targets must not be later than it.
    """
    if len(train_targets) == 0 or len(test_targets) == 0:
        return
    first_origin = pd.Timestamp(test_targets.min()) - pd.Timedelta(days=lead_days)
    latest_train = pd.Timestamp(train_targets.max())
    if latest_train > first_origin:
        raise LeakageError(
            f"training reaches target day {latest_train.date()} but the first test forecast is made on "
            f"{first_origin.date()} (lead {lead_days} days)"
        )
    overlap = set(pd.to_datetime(train_targets)) & set(pd.to_datetime(test_targets))
    if overlap:
        raise LeakageError(f"{len(overlap)} target days appear in both train and test")


@dataclass
class Split:
    block: Block
    train: np.ndarray  # positional indices into the frame
    test: np.ndarray


def walk_forward(
    target_days: pd.Series,
    blocks: list[Block],
    lead_days: int,
    min_train_days: int = 365,
    window_days: int | None = None,
) -> Iterator[Split]:
    """Yield train and test positions for each block, oldest first.

    ``target_days`` has the target day of every row. Rows are used for training if
    their target day is on or before ``train_cutoff``. With ``window_days`` set, only the
    most recent ``window_days`` before the cutoff are used (otherwise the window
    expands). Blocks with fewer than ``min_train_days`` of training rows, or with no
    test rows, are skipped. Every split is checked with ``assert_no_leakage``.
    """
    days = pd.to_datetime(target_days).reset_index(drop=True)
    for block in blocks:
        cutoff = pd.Timestamp(train_cutoff(block, lead_days))
        train_mask = days <= cutoff
        if window_days is not None:
            train_mask &= days > cutoff - pd.Timedelta(days=window_days)
        test_mask = (days >= pd.Timestamp(block.start)) & (
            days <= pd.Timestamp(block.end)
        )
        if train_mask.sum() < min_train_days or not test_mask.any():
            continue
        assert_no_leakage(days[train_mask], days[test_mask], lead_days)
        yield Split(block, np.flatnonzero(train_mask), np.flatnonzero(test_mask))


def train_validation_split(
    train_targets: pd.Series, validation_days: int, lead_days: int
) -> tuple[np.ndarray, np.ndarray]:
    """Split training rows into a fitting part and a later validation part.

    The validation part is the last ``validation_days`` days of the training targets.
    The fitting part stops ``lead_days`` before the validation part starts, for the
    same reason as the gap before the test block.
    """
    days = pd.to_datetime(train_targets).reset_index(drop=True)
    validation_start = days.max() - pd.Timedelta(days=validation_days - 1)
    validation = days >= validation_start
    fit = days <= validation_start - pd.Timedelta(days=lead_days)
    assert_no_leakage(days[fit], days[validation], lead_days)
    return np.flatnonzero(fit), np.flatnonzero(validation)
