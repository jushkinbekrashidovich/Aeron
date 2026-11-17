# Preliminary test of stagnation inputs (US Embassy station)

Status: preliminary. One station, fixed settings, one run, no intervals. All weather inputs are observed (ERA5) at or before the target hour, so results are an upper bound for operational skill. Same winter rolling blocks (winters 2020-21 to 2024-25, expanding window) as the [rolling evaluation](preliminary_rolling_eval.md) and the [upper-tail note](preliminary_upper_tail.md), which found that very high PM2.5 is strongly underpredicted.

Code: `src/aeron/stagnation_experiment.py`. Data: `src/aeron/openmeteo_extra_download.py` (ERA5 via Open-Meteo, retrieved 2026-11-17).

## Question

Do variables that describe stagnant air, which the earlier models lacked, reduce the underprediction of high PM2.5 or improve detection of high hours?

## Feature sets (all taken at the target hour)

- B: PM2.5 lags, calendar and basic ERA5 weather (the earlier set).
- S_noBLH: B plus shortwave radiation, vapour pressure deficit, mean sea-level pressure and its 24 h change, snow depth, 72 h rain total and 24 h mean wind. These exist as archived forecasts, so they can be tested with forecast weather later.
- S: S_noBLH plus boundary layer height (BLH), its 24 h mean and minimum, and a ventilation proxy (BLH times wind speed, also as 24 h mean). BLH is not available as an archived forecast, and the ERA5 series is missing from 2024-01-01 to 2024-06-30.

Pressure-level temperatures and winds (needed for a direct inversion measure) were not available from this source.

Simple check before modelling: in winter hours, PM2.5 averages 83 ug/m3 when BLH is 20 m or lower and 40 ug/m3 when BLH is above 235 m. Spearman correlation of PM2.5 with BLH is -0.37.

## Results (winter, all test rows)

The test rows are 11,101, 10,907 and 10,682 hours at 24, 48 and 72 h. Rows with BLH present give the same picture (see the script output; 9,816, 9,623 and 9,399 rows).

| Lead | Set | MAE | RMSE | Bias 100-150 | Bias above 150 | q90 F1 at 100 | AP at 55.5 | Brier skill at 55.5 |
|---|---|---|---|---|---|---|---|---|
| 24 h | B | 27.1 | 44.1 | -40.6 | -111.8 | 0.50 | 0.74 | 25% |
| 24 h | S_noBLH | 26.2 | 43.1 | -37.7 | -103.1 | 0.52 | 0.76 | 28% |
| 24 h | S | 26.0 | 43.0 | -37.3 | -105.1 | 0.52 | 0.78 | 30% |
| 48 h | B | 28.8 | 48.0 | -44.7 | -129.6 | 0.45 | 0.69 | 20% |
| 48 h | S_noBLH | 27.6 | 46.6 | -40.0 | -123.3 | 0.48 | 0.71 | 25% |
| 48 h | S | 26.9 | 45.9 | -39.2 | -121.9 | 0.48 | 0.73 | 28% |
| 72 h | B | 30.2 | 49.4 | -46.3 | -132.8 | 0.42 | 0.68 | 17% |
| 72 h | S_noBLH | 27.8 | 46.8 | -41.6 | -122.6 | 0.47 | 0.72 | 24% |
| 72 h | S | 27.1 | 46.3 | -40.4 | -121.2 | 0.48 | 0.73 | 26% |

Bias is prediction minus truth, in ug/m3. For the exceedance threshold of 100 ug/m3, AP is 0.44 / 0.46 / 0.47 (24 h, B / S_noBLH / S), 0.38 / 0.38 / 0.38 (48 h) and 0.36 / 0.40 / 0.39 (72 h). Brier skill at 100 ug/m3 is 15% / 16% / 17% (24 h), 9% / 9% / 8% (48 h) and 6% / 10% / 9% (72 h).

## Observations

- The extra inputs lower winter MAE by about 1.2 (24 h), 2.0 (48 h) and 3.0 (72 h) ug/m3 with S against B, and raise the Brier skill for exceeding 55.5 ug/m3 by 5 to 9 percentage points. This is the largest improvement of any step after adding weather.
- Most of the gain comes from the variables that exist as forecasts. BLH adds only a further 0.2 to 0.8 ug/m3 of MAE beyond S_noBLH. The gain at 72 h (MAE 30.2 to 27.8 with S_noBLH) is the largest.
- They do not fix the underprediction of the highest values. Bias above 150 ug/m3 improves by 6 to 12 ug/m3 and remains between -105 and -122. The 90th-percentile forecast still covers only 13%, 4% and 4% of hours above 150 ug/m3. Hours of 100 to 150 are underpredicted by 37 to 40 instead of 41 to 46.
- Detection of hours at or above 100 ug/m3 improves a little (90th-percentile F1 0.52, 0.48, 0.48 against 0.50, 0.45, 0.42). Probabilities for exceeding 100 ug/m3 are mixed: AP and Brier skill rise at 24 h and 72 h and not at 48 h. Differences of this size cannot be separated from noise in one run.
- A likely reason the extremes stay hard: hours above 150 ug/m3 come from a few episodes (for example Nov 2021) in a single series, so the model sees few examples and the true drivers (local sources, regional transport, inversion strength) are only partly captured by surface and reanalysis fields at one grid point.

## Limitations

- Observed weather throughout. The benefit with forecast weather is unknown for BLH, and the S_noBLH variables are only tested with ERA5, not archived forecasts.
- No confidence intervals, one run. The BLH gap in 2024 affects the last part of winter 2023-24 and the training of winter 2024-25.
- Reanalysis BLH is coarse and does not resolve local inversions in the Tashkent basin.
- One station.

## Next steps this suggests

- Test S_noBLH with archived forecast weather (shortwave radiation, vapour pressure deficit and pressure are available in the Previous Runs API for 2024 onward).
- Repeat with block-bootstrap intervals.
- Calibrate the quantile and probability forecasts on a validation block (next planned task).
