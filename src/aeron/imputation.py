"""Imputation that can only learn from the training period.

Policy (see docs/datasets/missing_data_policy.md): targets are never imputed and
PM2.5 gaps are not interpolated. Tree models take missing predictors as they
are. When a model cannot (for example linear regression), missing predictors are
filled with the median of the training rows, with an indicator column marking the
filled cells. The imputer is fitted on rows strictly before the test period and
refuses to fit otherwise.
"""

from __future__ import annotations

import pandas as pd
from sklearn.impute import SimpleImputer


class TrainOnlyImputer:
    """Median imputation fitted on training rows, with missing-value indicators."""

    def __init__(self, cutoff: pd.Timestamp) -> None:
        """``cutoff`` is the first timestamp of the test period."""
        self.cutoff = pd.Timestamp(cutoff)
        self._imputer = SimpleImputer(
            strategy="median", add_indicator=True, keep_empty_features=True
        )
        self.columns: list[str] = []

    def fit(self, train: pd.DataFrame) -> TrainOnlyImputer:
        if len(train) and pd.Timestamp(train.index.max()) >= self.cutoff:
            raise ValueError(
                f"training data reaches {train.index.max()}, which is not before the cutoff {self.cutoff}"
            )
        self.columns = list(train.columns)
        self._imputer.fit(train)
        return self

    def transform(self, frame: pd.DataFrame) -> pd.DataFrame:
        if not self.columns:
            raise RuntimeError("fit the imputer on training data first")
        if list(frame.columns) != self.columns:
            raise ValueError("columns differ from the training data")
        values = self._imputer.transform(frame)
        indicator_names = [
            f"{self.columns[i]}__was_missing"
            for i in self._imputer.indicator_.features_
        ]
        names = self.columns + indicator_names
        return pd.DataFrame(values, index=frame.index, columns=names)

    @property
    def fill_values(self) -> dict[str, float]:
        """Median used for each column, learned from the training rows only."""
        return dict(zip(self.columns, self._imputer.statistics_, strict=True))
