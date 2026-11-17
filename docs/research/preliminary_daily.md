# Preliminary daily-mean forecasts (US Embassy station)

Status: preliminary. One station, fixed settings, one run. Weather inputs are observed ERA5 values for the target day, which is a perfect weather forecast, so results are an upper bound. Follows from the [calibration note](preliminary_calibration.md), which found that hourly warnings fire too often and the hourly target is noisy.

Code: `src/aeron/daily_experiment.py`.

## Setup

- Local days (Asia/Tashkent, UTC+5). A forecast is issued at the end of day O for the daily mean of day O+1, O+2 or O+3. A daily mean needs at least 18 observed hours. The daily frame runs to 2026 because weather does, but PM2.5 ends on 2025-02-25. Of about 2,300 days in the observed period, 1,824 have a daily mean (79%), the rest falling in gaps such as the 2022 outage.
- Winter blocks (target days in Nov to Feb, winters 2020-21 to 2024-25), expanding window, training on target days before the block. Test days: 466 (1 day), 455 (2 days), 445 (3 days). Model settings are fixed and not tuned on test data (gradient boosting, 200 iterations, depth 4, minimum leaf 20).
- Feature sets: A, PM2.5 history (daily means of the last 7 days, 7 and 14 day means, previous evening mean, previous day maximum) and calendar; W, A plus ERA5 weather aggregated over the target day (temperature mean, minimum and maximum, humidity, wind, gusts, rain, rain over 3 days, pressure and its change, cloud, radiation, vapour pressure deficit, snow); S, W plus boundary layer height and ventilation (missing from 2024-01-01 to 2024-06-30).
- Baselines: persistence (mean of day O), climatology (training mean within 15 days of the same day of year), and always predicting an exceedance.
- Intervals: 95% percentile intervals from 1,000 resamples of 7-day blocks, paired across methods.

## Daily-mean PM2.5 (MAE / RMSE, ug/m3)

| Method | 1 day | 2 days | 3 days |
|---|---|---|---|
| Persistence | 21.7 / 30.6 | 28.4 / 42.5 | 30.7 / 45.0 |
| Climatology | 26.6 / 36.9 | 27.1 / 38.9 | 27.3 / 39.5 |
| A (history only) | 19.0 / 25.8 | 25.1 / 35.9 | 26.9 / 38.6 |
| W (history + weather) | 16.0 / 22.5 | 18.7 / 28.8 | 19.0 / 29.7 |
| S (W + boundary layer) | 15.8 / 22.3 | 18.6 / 28.9 | 19.1 / 29.6 |

The mean observed winter daily value is about 60 ug/m3 (53.7 to 67.2 by winter).

Paired MAE differences (negative means the first method is better):

| Comparison | 1 day | 2 days | 3 days |
|---|---|---|---|
| W - climatology | -10.5 [-13.2, -8.2] | -8.4 [-11.2, -5.7] | -8.3 [-10.9, -6.1] |
| W - persistence | -5.7 [-7.4, -3.9] | -9.7 [-12.4, -7.0] | -11.7 [-15.3, -8.4] |
| W - A | -2.9 [-4.0, -1.9] | -6.4 [-8.1, -4.6] | -7.9 [-10.3, -5.3] |
| A - climatology | -7.6 [-10.4, -5.5] | -2.0 [-4.2, +0.1] | -0.4 [-1.9, +1.1] |
| S - W | -0.2 [-0.5, +0.0] | -0.1 [-0.5, +0.3] | +0.1 [-0.3, +0.6] |

W beats climatology in every winter at every lead (for example 1 day: 13.0 against 19.5 in 2020-21 and 16.9 against 26.7 in 2024-25).

## Daily exceedances

Event means the daily mean is at or above the threshold. "Always yes" is a forecaster that always predicts an event (F1 is 2r/(1+r) for base rate r). F1 for classifiers uses a 0.5 cut-off. AUC is for classifier probabilities. Brier skill is relative to predicting the base rate.

Daily mean at or above 55.5 ug/m3 (base rate 0.45, always-yes F1 0.62):

| Method | 1 day F1 / AUC / Brier skill | 2 days | 3 days |
|---|---|---|---|
| Persistence (F1) | 0.70 | 0.60 | 0.57 |
| Climatology (F1) | 0.44 | 0.44 | 0.42 |
| A classifier | 0.75 / 0.84 / 0.33 | 0.53 / 0.70 / 0.03 | 0.49 / 0.63 / -0.06 |
| W classifier | 0.78 / 0.88 / 0.42 | 0.71 / 0.84 / 0.29 | 0.70 / 0.83 / 0.27 |
| S classifier | 0.79 / 0.87 / 0.42 | 0.72 / 0.84 / 0.30 | 0.71 / 0.84 / 0.30 |

Daily mean at or above 35.5 ug/m3 (base rate 0.71 to 0.72, always-yes F1 0.83 to 0.84): the W classifier has F1 0.88, 0.85 and 0.84, which is barely above always-yes. Its AUC is 0.88, 0.84 and 0.83 and its Brier skill 0.36, 0.29 and 0.24.

## Observations

- Daily means are much more predictable than hourly values. With weather, MAE is 16 to 19 ug/m3 for a mean of about 60, a relative error of 27% to 32%. The hourly winter MAE for the best model was 27 to 30 against a mean of about 60 (45% to 50%). The gain over climatology is 8 to 10.5 ug/m3, or 30% to 40%.
- Weather is the main source of skill. Without it (A), the model beats climatology only at 1 day, and its exceedance probabilities at 2 and 3 days are no better or worse than a constant (Brier skill 0.03 and -0.06 at 55.5). With target-day weather the forecasts stay useful to 3 days: AUC 0.83 to 0.84 at 55.5 ug/m3 and F1 0.70 against 0.62 for always-yes.
- The boundary layer variables add nothing measurable at the daily level (S - W within 0.2 ug/m3, intervals include zero), in contrast with the small hourly gains.
- At 1 day persistence is a strong baseline (MAE 21.7, F1 0.70 at 55.5) but W improves on it by 5.7 ug/m3 [3.9, 7.4]. At 2 and 3 days persistence is worse than climatology.
- The 35.5 ug/m3 threshold is exceeded on about 71% of winter days, so forecasts of it add little beyond always-yes. The 55.5 threshold (45% of days) is where the information is.
- Bias is small and negative (-2 to -5 ug/m3), not the large underprediction seen for hourly peaks, because daily means are less extreme.

## Limitations

- Observed weather over the target day, including hours after the forecast is issued. With real forecast weather the gain over history-only models will be smaller (the hourly tests lost about 1.5 ug/m3).
- Four to five winters, so differences between winters are large (MAE for W at 1 day ranges from 11 to 20 ug/m3) and the intervals above only cover sampling within those winters.
- One station, and thresholds applied to the station's own daily mean. The daily mean uses local days with at least 18 observed hours, which drops days inside gaps.
- No calibration step for the classifiers. Probabilities were not checked for reliability as in the calibration note.

## Next steps this suggests

- Rerun with archived forecast weather for 2024 to 2025 (daily aggregates of the Previous Runs forecasts).
- Calibrate the daily exceedance probabilities and report reliability.
- Test a second station or source.
