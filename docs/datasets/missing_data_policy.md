# Missing data policy

Status: decided in task 2.2.3 from the evidence in notebook 02 (section 7). Applies to all analyses and models. The cleaning rules that decide which readings count as missing are in the [cleaning log](cleaning_log.md).

## Policy

1. **Targets are never imputed.** An hourly value that is missing stays missing. A daily mean needs at least 18 observed hours in the local day (UTC+5) and is the mean of the observed hours. The threshold is a parameter (`time.min_hours_for_daily_mean` in `configs/sources.toml`) and Phase 3 reports the sensitivity to it (for example 22 hours).
2. **PM2.5 gaps are not interpolated.** No linear interpolation, forward fill or backward fill of hourly PM2.5, in the target or in predictors.
3. **Predictors.** Tree models receive missing predictors as missing (histogram gradient boosting handles them natively). Models that cannot (for example linear regression) get median imputation with a missing-value indicator column, fitted on the training rows only. `aeron.imputation.TrainOnlyImputer` enforces this: it raises an error if the training rows reach the start of the test period, and fill values come only from the training rows.
4. **Weather.** ERA5 has no empty cells in the core variables and none are imputed. Boundary layer height is empty from 2024-01-01 to 2024-06-30 and is left missing (it is also excluded from headline models, see the methodology). For archived forecasts, a local day needs at least 22 forecast hours to have daily weather aggregates, otherwise the day is dropped from forecast-weather tests.
5. **No use of the future.** Nothing is filled with information from after the forecast origin. Any statistic used to fill a gap is computed on data before the test period.

## Evidence (US Diplomatic Post PM2.5, after cleaning)

Gaps. The cleaned hourly series has 10,850 missing hours on its grid in 696 gaps. 417 gaps are a single hour and 531 are 3 hours or shorter, but together those 531 gaps hold only 679 hours (6% of the missing hours). 43 gaps longer than 24 hours hold 8,405 hours (77%). Interpolating short gaps would therefore recover little.

Interpolation is inaccurate here. Hiding consecutive hours inside complete days and filling them by linear interpolation gives a mean absolute error of 6.4 ug/m3 per filled hour for a one-hour gap, 8.3 for three hours and 10.5 for six hours. The mean daily value on complete days is 41.8 ug/m3. Hourly PM2.5 changes too quickly for interpolation to help, so a filled value would be less reliable than leaving it out.

Days with a daily mean (2,289 local days in the observed period):

| Minimum observed hours | Days |
|---|---|
| 24 | 1,349 |
| 22 | 1,668 |
| 20 | 1,738 |
| 18 | 1,823 |
| 16 | 1,849 |
| 12 | 1,875 |

Error of the observed-hours mean. On the 1,349 complete days, hiding hours and taking the mean of the rest gives these errors against the true daily mean (ug/m3):

| Hours hidden | MAE, random hours | MAE, one block | Bias, one block | 95th percentile of absolute error, one block |
|---|---|---|---|---|
| 1 | 0.6 | 0.6 | -0.01 | 1.9 |
| 2 | 0.9 | 1.2 | 0.04 | 3.6 |
| 3 | 1.1 | 1.7 | 0.09 | 5.5 |
| 4 | 1.3 | 2.2 | 0.24 | 7.1 |
| 6 | 1.7 | 3.3 | 0.47 | 10.6 |
| 8 | 2.0 | 4.3 | 0.91 | 13.9 |

With the 18-hour rule (up to 6 hours missing) the typical error of a daily mean is 1.7 to 3.3 ug/m3 and stays below about 10.6 ug/m3 in 95% of the worst-case contiguous gaps. That is small next to the daily forecast errors of 16 to 19 ug/m3 but not negligible for single days. Raising the threshold to 22 hours would cost 155 days (1,668 against 1,823). The choice of 18 is kept and tested for sensitivity in Phase 3.

Archived forecasts. The empty hours in the forecast file are the start of the archive, not scattered gaps. Forecasts issued 2, 3 and 4 days ahead are empty until 2024-01-20 11:00, 2024-01-21 11:00 and 2024-01-22 11:00 UTC (36, 60 and 84 hours), for every variable at once. The first usable forecast weather therefore starts a day or more after 2024-01-19.

## Notes

- One daily mean fewer than counted earlier: removing the four extreme PM2.5 spikes (cleaning rules) drops one local day below 18 hours, so 1,823 local days qualify after cleaning against 1,824 before.
- Imputation is not applied anywhere in the exploratory scripts of `src/aeron/` (gradient boosting handles missing values natively). If a later model needs imputation, it must use `TrainOnlyImputer`.
