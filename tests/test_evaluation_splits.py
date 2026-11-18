import itertools
from datetime import date

import pandas as pd
import pytest

from aeron.evaluation import splits
from aeron.evaluation.splits import Block, LeakageError

FIRST, LAST = date(2018, 11, 28), date(2025, 2, 25)


def target_days():
    return pd.Series(pd.date_range(FIRST, LAST, freq="D"))


def test_seasonal_blocks_cover_winters_and_the_rest_in_order():
    blocks = splits.seasonal_blocks(2020, LAST)
    assert [b.name for b in blocks] == [
        "winter 2020-21",
        "mar-oct 2021",
        "winter 2021-22",
        "mar-oct 2022",
        "winter 2022-23",
        "mar-oct 2023",
        "winter 2023-24",
        "mar-oct 2024",
        "winter 2024-25",
    ]
    assert blocks[0].start == date(2020, 11, 1) and blocks[0].end == date(2021, 2, 28)
    assert blocks[6].end == date(2024, 2, 29)  # leap year
    assert blocks[-1].end == LAST  # truncated at the end of the data
    assert all(
        a.end < b.start for a, b in itertools.pairwise(blocks)
    )  # no overlap, in order
    assert {b.season for b in blocks} == {"winter", "other"}


def test_blocks_after_the_last_date_are_dropped():
    blocks = splits.seasonal_blocks(2020, date(2021, 1, 15))
    assert len(blocks) == 1 and blocks[0].end == date(2021, 1, 15)


@pytest.mark.parametrize("lead", [1, 2, 3])
def test_every_split_is_leak_free_and_has_the_walk_forward_gap(lead):
    days = target_days()
    blocks = splits.seasonal_blocks(2020, LAST)
    produced = list(splits.walk_forward(days, blocks, lead))
    assert len(produced) == len(blocks)
    for s in produced:
        train, test = days.iloc[s.train], days.iloc[s.test]
        # Training stops lead days before the block starts: known at the first test forecast.
        assert train.max() == pd.Timestamp(s.block.start) - pd.Timedelta(days=lead)
        assert test.min() == pd.Timestamp(s.block.start)
        assert test.max() <= pd.Timestamp(s.block.end)
        first_origin = test.min() - pd.Timedelta(days=lead)
        assert train.max() <= first_origin
        assert not set(train) & set(test)


def test_training_window_expands_and_blocks_without_history_are_skipped():
    days = target_days()
    blocks = splits.seasonal_blocks(
        2019, LAST
    )  # winter 2019-20 has under a year of history
    produced = list(splits.walk_forward(days, blocks, 1, min_train_days=365))
    assert produced[0].block.name != "winter 2019-20"
    sizes = [len(s.train) for s in produced]
    assert sizes == sorted(sizes) and len(set(sizes)) == len(sizes)


def test_fixed_window_uses_only_recent_days():
    days = target_days()
    blocks = splits.seasonal_blocks(2020, LAST)
    for s in splits.walk_forward(days, blocks, 2, window_days=400):
        assert len(s.train) == 400


def test_leaky_split_without_the_gap_is_caught():
    days = target_days()
    block = Block("b", "winter", date(2023, 11, 1), date(2024, 2, 29))
    leaky_train = days[
        days < pd.Timestamp(block.start)
    ]  # no gap: reaches the day before the block
    test = days[(days >= pd.Timestamp(block.start)) & (days <= pd.Timestamp(block.end))]
    with pytest.raises(LeakageError):
        splits.assert_no_leakage(leaky_train, test, lead_days=3)
    splits.assert_no_leakage(leaky_train, test, lead_days=1)  # fine for a one-day lead
    with pytest.raises(LeakageError):
        splits.assert_no_leakage(test.iloc[:5], test, lead_days=1)  # overlapping days


def test_shuffled_order_does_not_change_the_split():
    days = target_days()
    blocks = splits.seasonal_blocks(2020, LAST)
    shuffled = days.sample(frac=1, random_state=0).reset_index(drop=True)
    first = next(splits.walk_forward(shuffled, blocks, 2))
    assert shuffled.iloc[first.train].max() == pd.Timestamp(
        first.block.start
    ) - pd.Timedelta(days=2)
    assert shuffled.iloc[first.test].min() == pd.Timestamp(first.block.start)


def test_validation_split_is_chronological_with_a_gap():
    days = target_days()
    train = days[days <= pd.Timestamp("2023-10-30")]
    fit, validation = splits.train_validation_split(
        train, validation_days=120, lead_days=3
    )
    assert len(validation) == 120
    assert train.iloc[fit].max() == train.iloc[validation].min() - pd.Timedelta(days=3)
    assert set(fit).isdisjoint(validation)


def test_train_cutoff():
    block = Block("b", "winter", date(2023, 11, 1), date(2024, 2, 29))
    assert splits.train_cutoff(block, 3) == date(2023, 10, 29)
    assert splits.train_cutoff(block, 1) == date(2023, 10, 31)
