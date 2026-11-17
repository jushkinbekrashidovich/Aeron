# Preliminary rolling-origin evaluation (US Embassy station)

Status: preliminary. One station, fixed hyperparameters, no tuning. Variant B uses observed (ERA5) weather at the target hour, so it is an upper bound on what weather inputs add. See [gradient boosting note](preliminary_gbm.md) for the cost of using archived forecast weather instead (about 1.5 ug/m3 of winter MAE in the 2024 to 2025 window).

Code: `src/aeron/rolling_eval.py`.

## Setup

- Test blocks alternate between winters (Nov to Feb) and Mar to Oct, from winter 2020-21 to winter 2024-25 (nine blocks). The last winter ends 2025-02-25 where the series ends.
- Expanding window: for each block, every model (and climatology) is fitted on all targets before the block starts, then scored on targets inside the block. No test data is used to choose parameters.
- Methods: persistence, climatology (month by hour mean), GBM A (PM2.5 lags and calendar), GBM B (A plus ERA5 weather at the target hour). Same features and parameters as the earlier notes.
- Scoring uses rows where all four methods have a prediction and the target is observed.
- Intervals: 95% percentile intervals from 1,000 resamples of 7-day blocks of pooled test errors, resampled jointly for all methods so differences are paired. They reflect sampling variation within the data. With five winters they do not capture how a new winter might differ, so the per-season table matters more than the intervals.

## Winter pooled MAE (ug/m3) with 95% intervals

| Lead | Persistence | Climatology | GBM A | GBM B |
|---|---|---|---|---|
| 24 h | 34.0 [30.1, 38.1] | 33.7 [30.0, 37.9] | 31.4 [27.8, 35.2] | 27.1 [24.0, 30.4] |
| 48 h | 40.2 [35.0, 45.6] | 33.7 [29.5, 38.1] | 34.5 [30.3, 39.0] | 28.8 [25.0, 32.8] |
| 72 h | 41.9 [37.0, 47.8] | 33.7 [29.7, 38.9] | 35.3 [30.8, 40.3] | 30.2 [26.4, 34.7] |

Paired MAE differences in winter (negative means the first method is better):

| Lead | B - climatology | A - climatology | B - A |
|---|---|---|---|
| 24 h | -6.6 [-8.3, -4.7] | -2.3 [-3.8, -0.9] | -4.2 [-5.4, -3.2] |
| 48 h | -4.8 [-6.8, -3.1] | +0.8 [-0.5, +2.1] | -5.7 [-7.1, -4.3] |
| 72 h | -3.6 [-5.1, -2.1] | +1.5 [+0.1, +2.7] | -5.1 [-6.3, -3.9] |

Pooled winter test hours: 11,101 (24 h), 10,907 (48 h), 10,682 (72 h).

## Mar to Oct pooled MAE (ug/m3)

| Lead | Persistence | Climatology | GBM A | GBM B |
|---|---|---|---|---|
| 24 h | 13.2 | 15.6 | 12.2 | 11.2 |
| 48 h | 14.6 | 15.7 | 13.3 | 12.1 |
| 72 h | 15.7 | 15.6 | 13.9 | 12.3 |

Both GBM variants beat climatology in these months at every lead (intervals for the differences exclude zero).

## MAE by winter (ug/m3), 24 h / 48 h / 72 h

| Winter | Mean PM2.5 | Climatology | GBM A | GBM B |
|---|---|---|---|---|
| 2020-21 | 54 | 24.3 / 24.7 / 25.1 | 21.9 / 25.5 / 26.4 | 18.9 / 20.9 / 22.0 |
| 2021-22 | 53 to 56 | 26.1 / 27.5 / 28.5 | 24.3 / 27.5 / 29.8 | 21.2 / 23.1 / 25.6 |
| 2022-23 | 63 to 66 | 47.4 / 47.1 / 46.7 | 39.8 / 45.5 / 45.8 | 32.1 / 34.4 / 36.0 |
| 2023-24 | 65 to 68 | 39.9 / 38.1 / 37.2 | 38.5 / 38.8 / 38.3 | 34.8 / 35.4 / 34.4 |
| 2024-25 | 61 to 62 | 34.6 / 34.9 / 35.1 | 34.6 / 38.3 / 38.8 | 30.3 / 32.3 / 34.6 |

## Observations

- GBM B beats climatology in all five winters at all three leads. The margin is large in 2022-23 (climatology MAE 47, B 32 to 36) and smallest in winter 2024-25 at 72 h (34.6 against 35.1). This is with perfect weather, so the realistic margin is smaller.
- GBM A (lags only) is not reliably better than climatology in winter. It is better at 24 h (-2.3, interval excludes zero), indistinguishable at 48 h, and worse at 72 h (+1.5, interval barely excludes zero). Persistence is worse than climatology at 48 and 72 h.
- The weather inputs add 4 to 6 ug/m3 of winter MAE over lags alone at every lead, with intervals well away from zero. Weather is where the winter skill comes from.
- Winters differ a lot. Winter 2022-23 has the highest climatology error (47) and only 1,768 test rows at 24 h, so it has missing data. A climatological profile fitted on earlier winters misses year-to-year level changes.
- Absolute winter errors stay large (MAE 27 to 30 for the best model against winter means of 53 to 68), so hourly winter values are only moderately predictable even with the best inputs here.

## Not yet done

- Forecast weather in the rolling setup (only available from 2024-01-19, so only the last winter).
- Daily-mean target, feature importance, error analysis on high-pollution days.
- A model fitted for warm and cold seasons separately, hyperparameter tuning with a validation block, and quantile forecasts.
- Other stations.
