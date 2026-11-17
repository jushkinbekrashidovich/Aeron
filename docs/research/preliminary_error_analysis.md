# Preliminary error analysis by pollution level (US Embassy station)

Status: preliminary. One station, fixed hyperparameters. Built on the out-of-sample predictions of the [rolling-origin evaluation](preliminary_rolling_eval.md), winter blocks only (Nov to Feb, five winters, 2020-21 to 2024-25), rows where all methods have a prediction. GBM B uses observed ERA5 weather at the target hour, so it is an upper bound. See [gradient boosting note](preliminary_gbm.md) for the cost of using forecast weather.

Code: `src/aeron/error_analysis.py`. Levels follow US EPA PM2.5 breakpoints (12.0, 35.4, 55.4 ug/m3); 100 ug/m3 is added as a higher threshold. Bias is prediction minus truth.

## Error by observed level, 24 h lead (MAE / bias, ug/m3)

| Observed level | Hours | Persistence | Climatology | GBM A | GBM B |
|---|---|---|---|---|---|
| below 12 | 607 | 33.0 / +32.5 | 47.9 / +47.9 | 40.4 / +40.4 | 28.6 / +28.6 |
| 12 to 35 | 3,606 | 24.2 / +19.0 | 26.0 / +25.9 | 23.3 / +22.8 | 19.0 / +17.9 |
| 35.5 to 55 | 2,332 | 24.3 / +3.9 | 11.9 / +5.7 | 14.9 / +5.0 | 15.4 / +7.0 |
| 55.5 to 100 | 2,848 | 33.8 / -5.8 | 22.7 / -20.1 | 24.7 / -15.2 | 22.4 / -9.4 |
| 100 to 150 | 1,128 | 52.1 / -26.9 | 62.4 / -62.4 | 52.9 / -49.3 | 44.4 / -40.6 |
| above 150 | 580 | 101.3 / -59.3 | 152.4 / -152.4 | 129.5 / -129.1 | 112.9 / -111.8 |

At 72 h the pattern is the same and larger for B: bias -10.7 (55.5 to 100), -46.3 (100 to 150), -132.8 (above 150).

## Exceedance detection, winter

Event means observed PM2.5 at or above the threshold. A method predicts an event when its prediction is at or above the same threshold. "Always yes" is the trivial forecaster that predicts an event every time; its precision equals the base rate and its F1 is 2r/(1+r).

Hourly, threshold 55.5 (base rate 0.41, always-yes F1 0.58):

| Lead | Persistence | Climatology | GBM A | GBM B |
|---|---|---|---|---|
| 24 h | 0.62 | 0.49 | 0.58 | 0.67 |
| 48 h | 0.53 | 0.49 | 0.49 | 0.65 |
| 72 h | 0.51 | 0.49 | 0.48 | 0.63 |

Hourly, threshold 100 (base rate 0.15, always-yes F1 0.26). F1, with GBM B recall in brackets:

| Lead | Persistence | Climatology | GBM A | GBM B |
|---|---|---|---|---|
| 24 h | 0.46 | 0.00 | 0.26 | 0.37 (0.28) |
| 48 h | 0.34 | 0.00 | 0.10 | 0.28 (0.20) |
| 72 h | 0.31 | 0.00 | 0.07 | 0.23 (0.16) |

Daily means (days with at least 18 observed target hours; 460, 449 and 438 days at 24, 48, 72 h). F1:

| Threshold | Lead | Always yes | Persistence | Climatology | GBM A | GBM B |
|---|---|---|---|---|---|---|
| 35.5 (base rate 0.72) | 24 h | 0.84 | 0.83 | 0.84 | 0.83 | 0.87 |
| 35.5 | 72 h | 0.83 | 0.76 | 0.83 | 0.83 | 0.84 |
| 55.5 (base rate 0.44) | 24 h | 0.61 | 0.73 | 0.46 | 0.66 | 0.76 |
| 55.5 | 48 h | 0.61 | 0.61 | 0.45 | 0.55 | 0.74 |
| 55.5 | 72 h | 0.61 | 0.55 | 0.45 | 0.50 | 0.70 |

Daily-mean MAE (ug/m3), 24 h / 48 h / 72 h: persistence 20.1 / 27.1 / 30.2, climatology 26.3 / 25.9 / 26.5, GBM A 22.1 / 25.1 / 26.9, GBM B 17.2 / 18.5 / 21.0.

## Observations

- All methods pull predictions toward the middle. Low hours (below 12) are overpredicted by 29 to 49 ug/m3 and high hours are underpredicted. Even with observed weather, hours of 100 to 150 are underpredicted by 41 to 46 ug/m3 and hours above 150 by 112 to 133 ug/m3 (mean observed 208 to 214). The models are fitted by least squares, which favours the middle of the distribution. The most severe episodes are not forecast.
- Hourly detection of values at or above 100 ug/m3 is weak. At 24 h GBM B finds 28% of such hours (F1 0.37); at 72 h, 16% (F1 0.23, below the always-yes F1 of 0.26). Persistence is better than all models at this threshold at every lead (F1 0.46, 0.34, 0.31), because a high hour tends to be followed by a high hour a day later.
- Daily detection at 55.5 ug/m3 is where weather helps most clearly: GBM B F1 is 0.76, 0.74 and 0.70 against always-yes 0.61, and persistence 0.73, 0.61 and 0.55. At 24 h persistence is nearly as good as GBM B (0.73 against 0.76), which this data cannot separate.
- Climatology and the lag-only model give little over the trivial forecaster. At the daily 35.5 threshold (most winter days exceed it) nothing beats always-yes by much.
- Daily-mean errors (MAE 17 to 21 for GBM B) are smaller than hourly errors (27 to 30), but not small against a winter daily mean of about 60.

## Limitations

- Observed weather in the best model (upper bound). With forecast weather the gap to climatology and persistence shrinks.
- The intervals from the rolling evaluation are not repeated here. Counts of very high hours come from a small number of episodes (for example Nov 2021), so detection scores at 100 ug/m3 are noisy.
- Thresholds are applied to the same hour or day with no tolerance for timing, so a peak predicted one hour late counts as both a miss and a false alarm.
- One station.

## Next steps this suggests

- Models aimed at the upper tail: quantile or log-target models, sample weights on high values, and evaluating probability of exceedance instead of point forecasts.
- Daily or 24 h-maximum targets for health-relevant warnings.
- Repeat with archived forecast weather for the 2024 to 2025 winter.
