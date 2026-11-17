# Preliminary calibration of exceedance probabilities and the 90th-percentile forecast (US Embassy station)

Status: preliminary. One station, one run, observed (ERA5) weather, so absolute numbers are an upper bound. Follows from the [upper-tail note](preliminary_upper_tail.md), where the exceedance probabilities and 90th-percentile forecast were not calibrated or checked for reliability.

Code: `src/aeron/calibration.py`.

## Setup

- Features: set S_noBLH from the [stagnation note](preliminary_stagnation.md) (PM2.5 lags, calendar, ERA5 weather at the target hour, radiation, vapour pressure deficit, pressure, snow, rain total, wind mean). All of these exist as archived forecasts, but this run uses observed values.
- Test winters: 2021-22, 2022-23, 2023-24 and 2024-25. Winter 2020-21 is excluded because too little earlier data remains. Test hours: 8,865 (24 h), 8,677 (48 h), 8,500 (72 h).
- For each test winter, base models are trained on targets before the start date minus 365 days. The calibrators use winter rows (Nov to Feb) from the previous winter, 1,654 to 2,464 hours. The base models therefore do not see the most recent winter, and absolute scores are a little worse than in the other notes. Raw and calibrated forecasts come from the same base model, so differences are due to calibration only.
- Probabilities: isotonic regression and Platt scaling (logistic regression on the logit of the raw probability). Brier differences are paired.
- 90th-percentile forecast: split-conformal shift of the forecast, either additive (shift by the 90% quantile of observed minus forecast on the calibration winter) or multiplicative (ratio of observed to forecast, with the forecast floored at 5 ug/m3).
- Intervals: 95% percentile intervals from 1,000 resamples of 7-day blocks of the pooled test rows.

## Exceedance probabilities

ECE is the expected calibration error with ten equal-count bins. "Mean p" is the average predicted probability, to compare with the base rate.

At 55.5 ug/m3 (base rate 0.41 at all three leads):

| Lead | Method | Brier | Log loss | ECE | Mean p |
|---|---|---|---|---|---|
| 24 h | raw | 0.1741 | 0.541 | 0.067 | 0.370 |
| 24 h | isotonic | 0.1775 | 0.549 | 0.038 | 0.408 |
| 24 h | Platt | 0.1756 | 0.532 | 0.029 | 0.406 |
| 48 h | raw | 0.1784 | 0.547 | 0.061 | 0.371 |
| 48 h | Platt | 0.1816 | 0.546 | 0.031 | 0.408 |
| 72 h | raw | 0.1835 | 0.563 | 0.079 | 0.356 |
| 72 h | Platt | 0.1824 | 0.550 | 0.021 | 0.402 |

At 100 ug/m3 (base rate 0.17):

| Lead | Method | Brier | Log loss | ECE | Mean p |
|---|---|---|---|---|---|
| 24 h | raw | 0.1205 | 0.433 | 0.079 | 0.104 |
| 24 h | isotonic | 0.1167 | 0.408 | 0.037 | 0.159 |
| 24 h | Platt | 0.1140 | 0.366 | 0.021 | 0.158 |
| 48 h | raw | 0.1260 | 0.451 | 0.083 | 0.088 |
| 48 h | Platt | 0.1188 | 0.381 | 0.027 | 0.150 |
| 72 h | raw | 0.1289 | 0.487 | 0.092 | 0.078 |
| 72 h | Platt | 0.1192 | 0.387 | 0.026 | 0.146 |

Paired Brier difference against the raw forecast (negative means better):

| Threshold | Lead | Isotonic | Platt |
|---|---|---|---|
| 55.5 | 24 h | +0.0034 [-0.0014, +0.0080] | +0.0015 [-0.0031, +0.0057] |
| 55.5 | 48 h | +0.0055 [-0.0013, +0.0117] | +0.0032 [-0.0029, +0.0094] |
| 55.5 | 72 h | +0.0022 [-0.0047, +0.0086] | -0.0011 [-0.0074, +0.0045] |
| 100 | 24 h | -0.0038 [-0.0107, +0.0032] | -0.0066 [-0.0120, -0.0016] |
| 100 | 48 h | -0.0065 [-0.0136, +0.0002] | -0.0073 [-0.0139, -0.0014] |
| 100 | 72 h | -0.0091 [-0.0164, -0.0025] | -0.0097 [-0.0163, -0.0037] |

## 90th-percentile forecast

Target coverage is 0.90. Coverage by forecast level uses the level of the forecast itself (levels below 35.5, 35.5 to 100, 100 to 200, above 200), which is what a user sees. Alerts mean the forecast is at or above 100 ug/m3, scored against observed values at or above 100.

| Lead | Method | Coverage [95% interval] | Coverage where forecast is 100 to 200 | Alert precision / recall | Alerts (share of hours) |
|---|---|---|---|---|---|
| 24 h | raw | 0.773 [0.741, 0.804] | 0.71 | 0.49 / 0.63 | 1,956 (22%) |
| 24 h | additive | 0.881 [0.854, 0.907] | 0.85 | 0.33 / 0.85 | 3,956 (45%) |
| 24 h | multiplicative | 0.878 [0.851, 0.902] | 0.86 | 0.35 / 0.84 | 3,745 (42%) |
| 48 h | raw | 0.758 [0.718, 0.793] | 0.71 | 0.46 / 0.57 | 1,822 (21%) |
| 48 h | additive | 0.882 [0.850, 0.910] | 0.86 | 0.29 / 0.84 | 4,225 (49%) |
| 48 h | multiplicative | 0.881 [0.846, 0.911] | 0.88 | 0.31 / 0.82 | 3,908 (45%) |
| 72 h | raw | 0.750 [0.705, 0.787] | 0.68 | 0.48 / 0.54 | 1,637 (19%) |
| 72 h | additive | 0.887 [0.856, 0.919] | 0.87 | 0.29 / 0.85 | 4,212 (50%) |
| 72 h | multiplicative | 0.882 [0.849, 0.914] | 0.87 | 0.32 / 0.83 | 3,808 (45%) |

For forecasts above 200 ug/m3 (few hours: 35 to 115 for the additive version, 437 to 467 for the multiplicative one) multiplicative coverage is 0.89 to 0.97.

## Observations

- The raw classifiers are too low on average. At the 100 ug/m3 threshold the mean predicted probability is 0.08 to 0.10 against an observed rate of 0.17, and at the 55.5 threshold it is 0.36 to 0.37 against 0.41. Raw probabilities in the low bins are too small by a factor of two or more (for example predicted 0.00 to 0.01 against observed 0.02 to 0.09 at 100 ug/m3). A likely cause is that winter levels rose: mean PM2.5 was about 53 to 55 ug/m3 in 2020-21 and 2021-22 and about 62 to 66 ug/m3 in 2022-23 to 2024-25 (rolling evaluation note), so models trained on earlier winters expect a cleaner season. This was not tested directly.
- Platt scaling fixes most of this: ECE falls from 0.06 to 0.09 to 0.02 to 0.03 at all leads and thresholds, and log loss falls (for example 0.433 to 0.366 at 100 ug/m3, 24 h). Brier score improves at 100 ug/m3 (intervals exclude zero for Platt at all leads) and shows no clear change at 55.5 ug/m3. Isotonic regression is slightly worse than Platt on Brier at 55.5 and similar at 100 ug/m3, with wider intervals. On this sample Platt is the better choice.
- Calibration improves the reliability of the probabilities but does not make them sharper. The Brier gain at 100 ug/m3 is 0.004 to 0.010 against a base-rate Brier of about 0.14.
- The raw 90th-percentile forecast covers only 75% to 77% of hours, and 68% to 71% of hours when it forecasts 100 to 200 ug/m3. The 95% intervals exclude 0.90. The conformal shift brings coverage to 0.88 to 0.89 (intervals include 0.90). Coverage at the 100 to 200 level is 0.85 to 0.88, so it stays a little low where it matters. Multiplicative scaling is more even across forecast levels than the additive shift.
- The price is a very wide upper bound. The calibrated forecast is 100 ug/m3 or higher in 42% to 50% of winter hours. Alerts catch 82% to 85% of hours at or above 100 ug/m3 but have a precision of 29% to 35% (the base rate is 17%). It works as a conservative "could be high" signal rather than a useful warning on its own.
- The conformal guarantee assumes exchangeable data. These are autocorrelated time series with year-to-year shifts, so the coverage of 0.88 against a target of 0.90 is about what to expect.

## Limitations

- The calibration set is one winter (1,654 to 2,464 hours, strongly autocorrelated), so the effective sample is small, and the calibrators inherit the level of that winter.
- Observed weather, a single station, and no repeat across seeds or alternative base models.
- Intervals reflect sampling within four winters, not the variation between winters.
- The hourly values are scored without any tolerance for the timing of peaks.

## Next steps this suggests

- Calibrate on a rolling window of several winters, and repeat with archived forecast weather for 2024 to 2025.
- Use a daily or 24 h maximum target for health-relevant warnings, which would make alerts less frequent and more meaningful.
- Report exceedance probabilities with reliability diagrams in the dashboard instead of a single forecast value.
