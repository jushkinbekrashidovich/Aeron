# Preliminary upper-tail models (US Embassy station)

Status: preliminary. One station, fixed settings, no repeated runs. All models use feature set B (PM2.5 lags, calendar, ERA5 weather at the target hour), so weather is observed rather than forecast and results are an upper bound. Same rolling-origin winter blocks as the [rolling evaluation](preliminary_rolling_eval.md) (winters 2020-21 to 2024-25, expanding window, nothing tuned on test blocks). Follows from the [error analysis](preliminary_error_analysis.md), which found that high PM2.5 is strongly underpredicted.

Code: `src/aeron/upper_tail.py`. Winter test hours: 11,101 (24 h), 10,907 (48 h), 10,682 (72 h). Bias is prediction minus truth.

## Variants

- `mse`: squared-error gradient boosting (the earlier model B).
- `log`: squared error on log(1 + PM2.5), transformed back.
- `weighted`: squared error with sample weights 1 + y/35, so high values count more.
- `q50`, `q90`: quantile loss for the median and the 90th percentile.
- Exceedance classifiers: probability that PM2.5 is at or above 55.5 or 100 ug/m3.

## Point forecasts, 24 h lead

| Method | MAE | RMSE | Bias 100-150 | Bias above 150 | F1 at 55.5 | F1 at 100 (recall) |
|---|---|---|---|---|---|---|
| Persistence | 34.0 | 55.0 | -26.9 | -59.3 | 0.62 | 0.46 (0.47) |
| mse | 27.1 | 44.1 | -40.6 | -111.8 | 0.67 | 0.37 (0.28) |
| log | 26.4 | 45.2 | -50.1 | -124.6 | 0.62 | 0.28 (0.18) |
| weighted | 30.5 | 48.3 | -32.4 | -102.8 | 0.69 | 0.40 (0.36) |
| q50 | 26.0 | 44.1 | -47.0 | -121.1 | 0.66 | 0.31 (0.20) |
| q90 | 36.8 | 49.6 | -7.5 | -71.8 | 0.65 | 0.50 (0.68) |

F1 at 100 for 48 h and 72 h (recall in brackets): persistence 0.34 (0.35) and 0.31 (0.31); mse 0.28 (0.20) and 0.23 (0.16); weighted 0.37 (0.34) and 0.30 (0.24); q90 0.45 (0.60) and 0.42 (0.55). F1 at 55.5 for 48 h and 72 h: persistence 0.53 and 0.51; mse 0.65 and 0.63; weighted 0.67 and 0.64; q90 0.64 and 0.63. MAE for 48 h and 72 h: mse 28.8 and 30.2, log 28.0 and 28.7, q50 27.5 and 28.5, weighted 31.2 and 32.2, q90 38.8 and 39.7.

An always-yes forecaster has F1 0.58 at 55.5 and 0.27 at 100.

## q90 coverage (share of observed values at or below the q90 forecast)

| Lead | All hours | Observed below 35.5 | 35.5 to 100 | 100 to 150 | Above 150 |
|---|---|---|---|---|---|
| 24 h | 0.81 | 1.00 | 0.82 | 0.39 | 0.12 |
| 48 h | 0.79 | 0.99 | 0.81 | 0.30 | 0.04 |
| 72 h | 0.78 | 0.99 | 0.81 | 0.26 | 0.03 |

A calibrated 90th percentile would cover 0.90 everywhere.

## Exceedance probabilities

Brier skill is 1 minus the Brier score over the Brier score of always predicting the test base rate. F1 and recall use the probability cut-offs 0.5, 0.3 and 0.2, all reported (none selected on test data).

| Threshold | Lead | Base rate | AUC | Brier skill | F1 at p>=0.5 | F1 at p>=0.3 | F1 at p>=0.2 (recall) |
|---|---|---|---|---|---|---|---|
| 55.5 | 24 h | 0.41 | 0.80 | 25% | 0.65 | 0.69 | 0.68 (0.85) |
| 55.5 | 48 h | 0.41 | 0.77 | 20% | 0.61 | 0.67 | 0.67 (0.84) |
| 55.5 | 72 h | 0.41 | 0.76 | 17% | 0.60 | 0.65 | 0.66 (0.83) |
| 100 | 24 h | 0.15 | 0.81 | 15% | 0.30 | 0.43 | 0.47 (0.50) |
| 100 | 48 h | 0.15 | 0.78 | 9% | 0.22 | 0.35 | 0.41 (0.41) |
| 100 | 72 h | 0.15 | 0.77 | 6% | 0.19 | 0.32 | 0.39 (0.38) |

## Observations

- No change of loss fixes the underprediction of the highest values. Log and median targets make it worse (bias above 150 of -121 to -141). Weighting reduces it a little (-103 against -112 at 24 h) at the cost of overpredicting mid-range hours and a higher MAE (30.5 against 27.1). Even the 90th percentile forecast covers only 12%, 4% and 3% of hours above 150 at the three leads. The inputs probably lack information on what drives the extremes (stagnant air, inversions, boundary layer height is not in the data), so a different loss cannot recover it.
- The q90 forecast is the most useful for detecting hours at or above 100 ug/m3: F1 0.50, 0.45 and 0.42 against persistence 0.46, 0.34 and 0.31. It reaches recall 0.68, 0.60 and 0.55 but with precision of about 0.34 to 0.39, and it overpredicts moderate hours by about 25 ug/m3. It works as a warning level, not as a forecast of the value.
- The probability classifiers add calibrated risk rather than a value. Brier skill over the base rate is 25%, 20% and 17% for the 55.5 threshold, but only 15%, 9% and 6% for 100 ug/m3, so very high levels are only weakly predictable. The 100 ug/m3 classifier at a 0.2 cut-off (F1 0.47, 0.41, 0.39) is comparable to q90 and slightly above persistence at 48 and 72 h.
- At 24 h persistence remains competitive for hours at or above 100 (F1 0.46 against 0.50 for q90 and 0.47 for the classifier), and this sample cannot separate them.
- For the 55.5 threshold, weighted and classifier outputs (F1 about 0.69 at 24 h) are slightly better than the plain model (0.67). This is within what this sample can resolve.

## Limitations

- Observed weather in all models (upper bound). No intervals were computed for these results.
- Few distinct high-pollution episodes, so counts above 100 and 150 ug/m3 are noisy.
- No hyperparameter tuning, no calibration step for the classifiers or the quantile model, and cut-offs for probabilities were only compared, not chosen on separate validation data.
- One station. Hourly target only.

## Next steps this suggests

- Add inputs that describe stagnation or inversion (boundary layer height, wind at higher altitude, temperature differences) if a source for forecasts exists.
- Calibrate quantile and probability forecasts on a validation block and report reliability curves.
- Daily maximum or daily mean targets for health-relevant warnings.
- Repeat with archived forecast weather and with other stations.
