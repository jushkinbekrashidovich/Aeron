# Preliminary daily forecasts with archived forecast weather (US Embassy station)

Status: preliminary. One station, 139 to 145 test days from two winters, fixed settings, one run. Follows from the [daily note](preliminary_daily.md), which used observed weather for the target day (a perfect forecast) and found a daily-mean MAE of 16 to 19 ug/m3. This note replaces that with archived forecasts.

Code: `src/aeron/daily_forecast_weather.py`. Data: Open-Meteo Previous Runs API, retrieved 2026-11-17 (`src/aeron/ingest/openmeteo.py`).

## Setup

- Same task as the daily note: a forecast issued at the end of local day O for the daily mean of day O+1, O+2 or O+3 (leads of 1, 2 and 3 days).
- Weather for the target day comes from the forecast issued k+1 days before each valid hour (2, 3 and 4 days for leads 1, 2 and 3). This is conservative: it was available at least about a day before the forecast is issued, and a forecast issued one day closer would be more accurate. Days with fewer than 22 forecast hours are dropped.
- Test days: target days from 2024-01-20 (the first local day fully covered by archived forecasts) to 2025-02-25 in the winter blocks. That gives 37 days from winter 2023-24 and 104 to 108 days from winter 2024-25, so 145 (1 day), 142 (2 days) and 139 (3 days) days in total. The mean observed daily value is 58.3 ug/m3.
- Models are trained on ERA5 weather (aggregated to days, as before) with target days before each block, and tested twice on identical days: with ERA5 weather for the target day (`W_obs`, perfect forecast) and with the archived forecast (`W_fc`). The snow variable is dropped because it has no archived forecast.
- `Wn` is the same with the wind variables (mean wind, maximum gust) removed. This was added after seeing that `W_fc` was biased upward on these test days, so it is a post-hoc choice on the same two winters and not an independent test.
- Baselines: persistence, climatology, and the history-only model `A`. Intervals: 95% percentile intervals from 1,000 resamples of 7-day blocks, paired.

## How good is the forecast weather?

Daily aggregates against ERA5 at the station (forecast issued 2 days ahead; the 4-day values are in brackets):

| Variable | ERA5 mean | Bias (forecast - ERA5) | MAE | Correlation |
|---|---|---|---|---|
| Mean temperature (C) | 13.4 | +0.9 (+1.0) | 1.2 (1.5) | 0.99 (0.99) |
| Mean relative humidity (%) | 58.9 | -1.3 (-1.3) | 6.1 (7.2) | 0.92 (0.89) |
| Mean wind speed (km/h) | 8.0 | -2.5 (-2.8) | 2.6 (2.9) | 0.70 (0.62) |
| Maximum gust (km/h) | 27.1 | -1.2 (-2.0) | 5.2 (5.7) | 0.75 (0.71) |
| Daily rain (mm) | 2.0 | -0.6 (-0.7) | 1.1 (1.4) | 0.79 (0.71) |
| Mean cloud cover (%) | 49.0 | +5.7 (+5.2) | 12.6 (14.5) | 0.89 (0.84) |
| Mean sea-level pressure (hPa) | 1017.2 | +0.3 (+0.3) | 0.7 (1.2) | 1.00 (0.99) |

Temperature and pressure are forecast well. Wind is biased low by about a third and correlates only 0.6 to 0.7 with ERA5.

## Daily-mean PM2.5 (MAE, ug/m3; bias in brackets)

| Method | 1 day | 2 days | 3 days |
|---|---|---|---|
| Persistence | 24.1 (+0.4) | 32.4 (+0.2) | 35.1 (0.0) |
| Climatology | 25.7 (-6.8) | 25.7 (-7.2) | 25.7 (-7.7) |
| A (history only) | 20.0 (-2.4) | 27.1 (-5.6) | 27.0 (-4.2) |
| W_obs (perfect weather) | 15.3 (+2.1) | 18.8 (+0.5) | 17.9 (-0.1) |
| W_fc (forecast weather) | 19.0 (+10.2) | 22.9 (+8.7) | 24.1 (+11.8) |
| Wn_obs (no wind, perfect weather) | 16.8 (-2.3) | 19.8 (-5.1) | 19.2 (-4.8) |
| Wn_fc (no wind, forecast weather) | 17.1 (-1.4) | 20.7 (-4.1) | 21.5 (-2.6) |

Paired MAE differences (negative means the first is better):

| Comparison | 1 day | 2 days | 3 days |
|---|---|---|---|
| W_fc - W_obs | +3.7 [+2.1, +5.4] | +4.1 [+2.4, +5.9] | +6.2 [+3.0, +9.9] |
| W_fc - climatology | -6.7 [-9.6, -3.9] | -2.7 [-5.0, -0.1] | -1.7 [-5.1, +2.3] |
| Wn_fc - climatology | -8.6 [-10.8, -6.6] | -5.0 [-7.4, -2.6] | -4.2 [-7.6, -1.1] |
| Wn_fc - W_fc | -1.9 [-3.6, -0.2] | -2.2 [-4.0, -0.6] | -2.5 [-5.5, +0.2] |
| Wn_fc - Wn_obs | +0.3 [-0.8, +1.3] | +0.9 [-0.7, +2.5] | +2.3 [0.0, +5.0] |

## Exceedance of a daily mean of 55.5 ug/m3

Base rate 0.45 (65, 64 and 63 days; always-yes F1 0.62). F1 with a 0.5 cut-off, then AUC and Brier skill over the base rate:

| Method | 1 day | 2 days | 3 days |
|---|---|---|---|
| Persistence (F1) | 0.66 | 0.54 | 0.48 |
| W_obs | 0.79 / 0.85 / 0.37 | 0.75 / 0.83 / 0.31 | 0.75 / 0.83 / 0.29 |
| W_fc | 0.76 / 0.80 / 0.19 | 0.73 / 0.76 / 0.17 | 0.68 / 0.76 / 0.12 |
| Wn_fc | 0.72 / 0.83 / 0.30 | 0.68 / 0.77 / 0.18 | 0.66 / 0.73 / 0.12 |

## Observations

- Real forecast weather costs much more at the daily level than at the hourly level. MAE rises by 3.7, 4.1 and 6.2 ug/m3 (interval above zero at every lead) against about 1.5 for hourly values. The gain over climatology shrinks from 8 to 10 ug/m3 with perfect weather (daily note) to 1.7 to 6.7 with archived forecasts.
- The loss comes mostly from wind. Forecast wind is low by 2.5 to 2.8 km/h, so the model trained on ERA5 reads the days as calmer than they are and overpredicts by 9 to 12 ug/m3 (bias +10.2, +8.7, +11.8). Removing wind and gusts brings the bias to between -1.4 and -4.1 and lowers MAE by about 2 ug/m3 at each lead, though perfect weather without wind is worse than with it (16.8 against 15.3 at 1 day). Because this fix was chosen after seeing the results, treat it as a lead for a proper test, not a result.
- With wind removed, the forecast-weather model beats climatology at all three leads (-8.6, -5.0 and -4.2 ug/m3, intervals exclude zero) and beats persistence and the history-only model clearly at 2 and 3 days. Skill beyond one day is about half of what perfect weather would give.
- At 3 days the full model with wind is not distinguishable from climatology (-1.7 [-5.1, +2.3]), and exceedance detection is weak: F1 0.66 to 0.68 against 0.62 for always-yes, AUC 0.73 to 0.76, Brier skill 12%. At 1 day the exceedance forecast is useful (F1 0.72 to 0.76, Brier skill 19% to 30%).
- Probabilities are the most sensitive to the weather input. Brier skill at 55.5 ug/m3 falls from 0.37, 0.31 and 0.29 with perfect weather to 0.19, 0.17 and 0.12 with forecasts for the full model.

## Limitations

- 139 to 145 days, 37 of them from one winter. Intervals reflect only sampling within these days.
- The no-wind variant was chosen after looking at these results.
- Archived forecasts issued 2 to 4 days ahead are conservative. Boundary layer height and snow have no archived forecasts and were not tested.
- Model training uses ERA5 weather, so there is a distribution shift at test time. Training on archived forecasts is not possible with so little history.
- One station.

## Next steps this suggests

- Bias-correct forecast wind (or use model output statistics fitted on earlier forecasts) instead of dropping it, using only forecast history from before each test block.
- Try the forecast issued k days ahead instead of k+1, which is closer to how an operational system would work.
- Calibrate the daily probabilities and test a second station.
