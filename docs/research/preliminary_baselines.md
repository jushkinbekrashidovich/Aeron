# Preliminary baselines (US Embassy station)

Status: preliminary. One station, one test period, no weather inputs. These numbers set the level any model has to beat. They are not results for AERON.

Code: `src/aeron/baselines.py`. Data: OpenAQ hourly PM2.5, US Diplomatic Post Tashkent (see [data sources](../datasets/data_sources.md)). Retrieved 2026-11-17.

## Setup

- Target: hourly PM2.5 (ug/m3) at lead h = 24, 48, 72 hours after the forecast origin.
- Split: chronological. Climatology is fitted on data before 2024-01-01. Targets lie between 2024-01-01 and 2025-02-25 (the series ends then).
- Test hours with a valid value: 9,218. Mean 38.5, standard deviation 42.1 ug/m3.
- Pairs with a missing origin or target value are skipped, so n differs by method and lead. Values are not imputed.
- No outliers were removed. Zero values (78 in the whole series) are kept. The large spikes (up to 978 ug/m3 in Nov 2021, in the training period) are kept because they are the events a forecast must handle.
- Winter means November to February. Test winter months are Jan and Feb 2024, Nov and Dec 2024, and Jan and Feb 2025.

## Methods

- Persistence: prediction is the value at the origin.
- Mean of last 24 h: mean of the 24 hours up to the origin (at least 18 valid).
- Climatology: training-period mean for the target's month and hour of day. Uses no recent observations.

## Results (MAE / RMSE, ug/m3)

| Method | Lead | All | Winter | Other months |
|---|---|---|---|---|
| Persistence | 24 h | 24.4 / 40.4 | 37.2 / 51.5 | 14.3 / 28.9 |
| Persistence | 48 h | 28.6 / 47.5 | 45.2 / 61.3 | 15.6 / 33.0 |
| Persistence | 72 h | 30.0 / 49.7 | 46.6 / 62.9 | 17.0 / 36.2 |
| Mean of last 24 h | 24 h | 24.6 / 39.5 | 38.0 / 50.9 | 14.0 / 27.4 |
| Mean of last 24 h | 48 h | 26.5 / 42.1 | 42.1 / 55.4 | 14.1 / 27.6 |
| Mean of last 24 h | 72 h | 27.4 / 43.1 | 42.5 / 55.6 | 15.4 / 29.7 |
| Climatology | 24 h | 26.0 / 37.9 | 34.2 / 46.2 | 19.5 / 29.8 |
| Climatology | 48 h | 26.0 / 38.1 | 34.3 / 46.5 | 19.6 / 29.9 |
| Climatology | 72 h | 26.0 / 37.9 | 34.5 / 46.8 | 19.3 / 29.0 |

## Observations

- Persistence error grows with lead time (MAE 24.4 to 30.0). Climatology does not depend on lead, and beats persistence at 48 and 72 h on both MAE and RMSE.
- In winter, climatology beats persistence at every lead (RMSE 46 against 51 to 63). A model that does not beat climatology in winter has no useful skill there.
- Climatology (bias = prediction minus truth) underpredicts in winter by about 9 ug/m3 and overpredicts in other months by about 11. The test winters were dirtier, and the test warm months cleaner, than the 2019 to 2023 average for the same months. A fixed seasonal profile does not follow year-to-year changes.
- Errors are large relative to the test mean (38.5). Hourly values are noisy, and daily means may be the more forecastable target. This is not tested yet.

## Limitations

- Single station and a single 14-month test window with two winters partly covered.
- No weather features, no model fitted yet.
- The Embassy series ends 2025-02-25, so nothing here says how a model performs in the winter of 2025 to 2026.
