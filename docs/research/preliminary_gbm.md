# Preliminary gradient boosting experiment (US Embassy station)

Status: preliminary. One station, one split, fixed hyperparameters, no repeated runs. Treat differences of about 1 ug/m3 as noise. Not a result for AERON.

Code: `src/aeron/gbm_experiment.py`. Baselines and data: see [preliminary baselines](preliminary_baselines.md).

## Setup

- Model: scikit-learn `HistGradientBoostingRegressor`, one model per lead time (24, 48, 72 h). Fixed parameters (300 iterations, learning rate 0.05, depth 6, minimum leaf 50, L2 1.0). Nothing was tuned on the test period.
- Target: hourly PM2.5 at time t + h. Train on targets before 2024-01-01. Test on targets from 2024-01-01 to 2025-02-25.
- All methods in the table are scored on the same rows, those where both the origin value and the target value are observed.
- Variant A (lags): PM2.5 at the origin and at lags 1, 2, 3, 6, 12, 24, 48, 72, 168 h; 24 h mean, maximum and standard deviation; 168 h mean; hour, month and weekday of the target time. Missing lags are passed through as missing.
- Variant B (lags plus ERA5): A plus ERA5 weather at the target hour (temperature, humidity, precipitation, pressure, cloud cover, wind speed, gusts, wind components) and the temperature change from the origin to the target.
- **Variant B uses observed (reanalysis) weather at the target time, which is a perfect weather forecast.** It shows the most that weather inputs could add. Operational skill will be lower. Forecast weather is only available from 2024-01-19 (see data sources).

## Results (MAE / RMSE, ug/m3)

| Method | Lead | All | Winter | Other months |
|---|---|---|---|---|
| Persistence | 24 h | 24.4 / 40.4 | 37.2 / 51.5 | 14.3 / 28.9 |
| Climatology | 24 h | 26.0 / 37.9 | 34.2 / 46.2 | 19.5 / 29.8 |
| GBM A (lags) | 24 h | 22.8 / 35.7 | 33.8 / 45.4 | 14.3 / 25.7 |
| GBM B (lags + ERA5) | 24 h | 20.0 / 32.0 | 28.8 / 39.6 | 13.1 / 24.5 |
| Persistence | 48 h | 28.6 / 47.5 | 45.2 / 61.3 | 15.6 / 33.0 |
| Climatology | 48 h | 26.0 / 38.1 | 34.3 / 46.5 | 19.6 / 29.9 |
| GBM A (lags) | 48 h | 25.1 / 38.8 | 38.1 / 50.4 | 15.0 / 26.4 |
| GBM B (lags + ERA5) | 48 h | 21.5 / 33.7 | 31.0 / 41.8 | 14.1 / 25.7 |
| Persistence | 72 h | 30.0 / 49.7 | 46.6 / 62.9 | 17.0 / 36.2 |
| Climatology | 72 h | 26.0 / 37.9 | 34.5 / 46.8 | 19.3 / 29.0 |
| GBM A (lags) | 72 h | 25.1 / 38.9 | 36.6 / 49.7 | 16.0 / 27.7 |
| GBM B (lags + ERA5) | 72 h | 22.3 / 35.0 | 32.5 / 44.2 | 14.3 / 25.6 |

Winter is November to February. Number of test rows: 8,786 (24 h), 8,689 (48 h), 8,640 (72 h).

## Observations

- Lag features alone (A) give little over climatology in winter. At 24 h the MAE is 33.8 against 34.2. At 48 h and 72 h A is worse than climatology in winter (38.1 and 36.6 against 34.3 and 34.5), although better in other months. Past PM2.5 values lose most of their information after one day.
- Adding perfect weather (B) improves on climatology in every winter row: MAE 28.8, 31.0 and 32.5 against 34.2, 34.3 and 34.5, and RMSE 39.6, 41.8 and 44.2 against 46.2 to 46.8. Most of that gain comes from weather at the target time, so the realistic gain with forecast weather will be smaller.
- B at 72 h (MAE 22.3) is about as good as A at 24 h (22.8), which says how much of the signal is in the weather.
- Winter errors remain large (MAE 29 to 33 against a test winter mean of 60.3). Forecasts of hourly values in winter are weak even with perfect weather.

## Forecast weather instead of observed weather

Code: `src/aeron/gbm_forecast_weather.py`; data from `src/aeron/ingest/openmeteo.py` (Open-Meteo Previous Runs API, not committed).

- Variant C uses the same model as B, trained on ERA5 weather before 2024-01-01, but at test time takes the archived forecast for the target hour. The forecast issued 2, 3 and 4 days before the valid time is used for leads of 24, 48 and 72 h. That leaves a margin of about one day for model run publication, so it is conservative: forecasts issued one day closer would be more accurate.
- Test rows are targets from 2024-01-19 to 2025-02-25, the period with archived multi-variable forecasts. All methods use identical rows. Winter test rows are about 3,300 to 3,400 hours (late Jan to Feb 2024, Nov and Dec 2024, Jan and Feb 2025).
- Archived forecasts against ERA5 at the station: temperature MAE 1.7 to 2.0 C (correlation 0.98 to 0.99), relative humidity MAE 9 to 10 points, wind speed MAE 3.5 to 3.8 km/h with a bias of about -2.5 and correlation only 0.4. Forecasts of wind and precipitation are poor, and the model trained on ERA5 sees inputs with a different distribution.

MAE / RMSE in ug/m3, winter and all months:

| Method | Lead | Winter | All |
|---|---|---|---|
| Climatology | 24 h | 33.0 / 44.2 | 25.1 / 36.4 |
| GBM A (lags) | 24 h | 32.6 / 43.8 | 21.8 / 34.3 |
| GBM B (ERA5 weather) | 24 h | 27.4 / 37.0 | 19.0 / 30.3 |
| GBM C (forecast weather) | 24 h | 29.1 / 38.7 | 20.2 / 31.4 |
| Climatology | 48 h | 33.0 / 44.3 | 25.0 / 36.5 |
| GBM A (lags) | 48 h | 36.4 / 48.3 | 23.7 / 36.9 |
| GBM B (ERA5 weather) | 48 h | 29.5 / 39.3 | 20.4 / 31.9 |
| GBM C (forecast weather) | 48 h | 31.2 / 40.9 | 21.7 / 32.9 |
| Climatology | 72 h | 33.1 / 44.8 | 24.9 / 36.2 |
| GBM A (lags) | 72 h | 35.2 / 47.9 | 23.8 / 37.2 |
| GBM B (ERA5 weather) | 72 h | 31.1 / 42.0 | 21.1 / 33.2 |
| GBM C (forecast weather) | 72 h | 32.6 / 43.1 | 22.5 / 34.1 |

- Replacing observed weather with archived forecasts costs about 1.5 to 1.7 ug/m3 of winter MAE and about 1 to 1.4 over all months. Most of the gain from weather survives.
- In winter, C beats climatology at 24 h (29.1 against 33.0) and 48 h (31.2 against 33.0). At 72 h the gap is 0.5 in MAE and 1.7 in RMSE, which this single split cannot distinguish from noise.
- Variant A (lags only) is no better than climatology in winter at 48 and 72 h in this window either.

## Not yet done

- Uncertainty: no confidence intervals. A single split with two partial winters cannot separate model differences from year-to-year variation. Rolling-origin evaluation by season is needed.
- Daily-mean target, feature importance and error analysis by pollution level (events above 100 ug/m3).
- Stations other than the US Embassy.
