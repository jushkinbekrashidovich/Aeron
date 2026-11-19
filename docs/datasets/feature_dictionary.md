# Feature dictionary

The features used for the daily forecasts, built by `aeron.features.build_features(daily, lead)` from the processed daily table (see the [data dictionary](data_dictionary.md)). Demonstration, checks and findings are in notebook 05, and the leakage tests in `tests/test_features.py`.

A row is one forecast origin O, the end of local day O. The target is the daily mean PM2.5 of day D = O + lead (lead 1, 2 or 3). Every feature below is known at the end of day O, except the `wxt_` group, which is a perfect-forecast scenario for upper bounds.

| Group | Columns | Definition |
|---|---|---|
| target | `y`, `y_origin`, `origin_date`, `target_date` | `y`: daily mean of day D. `y_origin`: daily mean of day O (equal to `hist_pm_lag0`). Not features. |
| history `hist_` | `hist_pm_lag0` to `hist_pm_lag6` | Daily mean PM2.5 of day O, O-1, ..., O-6 |
| | `hist_pm_roll7_mean`, `_roll7_std`, `_roll7_max`, `hist_pm_roll14_mean` | Rolling statistics over the last 7 or 14 days ending on O (at least 4 or 8 days with a value) |
| | `hist_pm_delta1`, `hist_pm_trend7` | Day O minus day O-1, and day O minus its 7-day mean |
| | `hist_day_max`, `hist_day_evening_mean`, `hist_day_hours` | Maximum, local evening mean and number of observed hours of day O |
| time `time_` | `time_doy_sin`, `time_doy_cos`, `time_month`, `time_winter`, `time_dow`, `time_weekend` | Calendar of the target day D. Day of year is encoded as sine and cosine. Winter is November to February. |
| weather now `wxo_` | `wxo_<name>_l0`, `wxo_<name>_l1` | Observed (ERA5) daily weather of day O and day O-1 for temperature, humidity, wind, rain, 3-day rain, sea-level pressure and its change |
| weather forecast `wxf_` | `wxf_<name>`, `wxf_temp_range` | Archived forecast for day D issued lead + 1 days before the valid hours: temperature (mean, min, max), humidity, wind speed, gust, wind east and north components, rain, 3-day rain, pressure, cloud, radiation, vapour pressure deficit, sea-level pressure and its change |
| weather that happened `wxt_` | `wxt_<name>`, `wxt_temp_range`, `wxt_blh_mean`, `wxt_blh_min`, `wxt_vent_mean` | ERA5 weather of day D, including boundary layer height and ventilation. **Not known at the origin.** |

## Feature sets

| Set | Groups | Features | Use |
|---|---|---|---|
| `history` | hist, time | 22 | What the series' own history gives |
| `history_weather_now` | + wxo | 36 | Adds weather observed up to the origin |
| `forecast` | + wxf | 53 | Headline set: everything a real forecast could use |
| `forecast_no_wind` | forecast without forecast wind, gust and wind components | 49 | Tests the effect of the biased forecast wind |
| `observed_upper_bound` | history, time, wxo and wxt | 56 | Perfect-forecast ceiling, never a headline result |

## Rules

- No missing value is filled in. Rows keep their missing values (see the [missing data policy](missing_data_policy.md)).
- Boundary layer height, snow and ventilation have no archived forecast and appear only in `observed_upper_bound`.
- Archived forecasts exist from 2024, so models are trained with the observed weather in the forecast columns (`observed_as_forecast`) and tested on the real forecast columns.
- Forecast wind can be bias-corrected with `aeron.features.bias`, with the factor fitted on days up to the training cutoff of each test block only.
