import numpy as np
import pandas as pd
import pytest

from aeron.imputation import TrainOnlyImputer


def frame():
    index = pd.date_range("2024-01-01", periods=10, freq="D")
    return pd.DataFrame(
        {
            "a": [1.0, 2.0, np.nan, 4.0, 5.0, 100.0, np.nan, 300.0, 400.0, 500.0],
            "b": 1.0,
        },
        index=index,
    )


def test_fill_values_come_from_training_rows_only():
    data = frame()
    train, test = data.iloc[:5], data.iloc[5:]
    imputer = TrainOnlyImputer(test.index.min()).fit(train)
    assert imputer.fill_values["a"] == 3.0  # median of 1, 2, 4, 5
    out = imputer.transform(test)
    assert out.loc["2024-01-07", "a"] == 3.0  # not the median of the test period
    assert out.loc["2024-01-07", "a__was_missing"] == 1.0
    assert out.loc["2024-01-06", "a__was_missing"] == 0.0


def test_fitting_on_all_data_would_give_different_values():
    data = frame()
    leaky = TrainOnlyImputer(pd.Timestamp("2030-01-01")).fit(data)
    honest = TrainOnlyImputer(data.index[5]).fit(data.iloc[:5])
    assert leaky.fill_values["a"] != honest.fill_values["a"]


def test_refuses_to_fit_on_rows_at_or_after_the_cutoff():
    data = frame()
    with pytest.raises(ValueError):
        TrainOnlyImputer(data.index[5]).fit(data.iloc[:6])


def test_transform_requires_fit_and_same_columns():
    data = frame()
    with pytest.raises(RuntimeError):
        TrainOnlyImputer(data.index[5]).transform(data)
    imputer = TrainOnlyImputer(data.index[5]).fit(data.iloc[:5])
    with pytest.raises(ValueError):
        imputer.transform(data[["a"]])


def test_column_without_training_values_is_kept():
    data = frame()
    data["c"] = np.nan
    imputer = TrainOnlyImputer(data.index[5]).fit(data.iloc[:5])
    out = imputer.transform(data.iloc[5:])
    assert (
        "c" in out.columns and out["c"].eq(0.0).all()
    )  # empty column is filled with 0
