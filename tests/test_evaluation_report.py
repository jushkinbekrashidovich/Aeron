import numpy as np
import pandas as pd
import pytest

from aeron.evaluation import report


def predictions():
    days = pd.date_range("2024-01-01", periods=60, freq="D")
    y = np.linspace(20, 80, 60)
    return pd.DataFrame(
        {
            "target_date": days,
            "y": y,
            "season": ["winter"] * 40 + ["other"] * 20,
            "block": ["w1"] * 20 + ["w2"] * 20 + ["o1"] * 20,
            "good": y + 2.0,
            "bad": y + 10.0,
            "gappy": np.where(np.arange(60) % 2 == 0, y + 5.0, np.nan),
        }
    )


def test_summarize_groups_and_counts():
    out = report.summarize(predictions(), ["good", "bad", "gappy"])
    assert set(out["group"]) == {"winter", "other", "all"}
    row = out[(out["group"] == "winter") & (out["model"] == "good")].iloc[0]
    assert (
        row["n"] == 40
        and row["mae"] == pytest.approx(2.0)
        and row["bias"] == pytest.approx(2.0)
    )
    assert out[(out["group"] == "all") & (out["model"] == "bad")].iloc[0][
        "mae"
    ] == pytest.approx(10.0)
    gappy = out[(out["group"] == "all") & (out["model"] == "gappy")].iloc[0]
    assert gappy["n"] == 30  # missing predictions are skipped and counted


def test_summarize_event_columns_match_the_always_yes_reference():
    row = report.summarize(predictions(), ["good"]).query("group == 'all'").iloc[0]
    assert 0 < row["base_rate"] < 1
    assert row["always_yes_f1"] == pytest.approx(
        2 * row["base_rate"] / (1 + row["base_rate"])
    )
    assert 0 <= row["f1"] <= 1


def test_per_block_mae_is_in_time_order_with_day_counts():
    table = report.per_block_mae(predictions(), ["good", "bad"])
    assert list(table.index) == ["w1", "w2", "o1"]
    assert table["days"].tolist() == [20, 20, 20]
    assert table.loc["w2", "bad"] == pytest.approx(10.0)


def test_paired_difference_sign_and_interval():
    result = report.paired_difference(
        predictions(), "good", "bad", "winter", block_days=7
    )
    assert result["diff"] == pytest.approx(-8.0)
    assert result["lo"] <= result["diff"] <= result["hi"] and result["hi"] < 0
    flipped = report.paired_difference(
        predictions(), "bad", "good", "winter", block_days=7
    )
    assert flipped["diff"] == pytest.approx(8.0)
