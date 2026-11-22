# Uncertainty: intervals and exceedance probabilities (task 4.3)

Source: `notebooks/09_uncertainty.ipynb`, code in `src/aeron/uncertainty.py`; tables `interval_coverage.csv` and `probability_metrics.csv` in this folder. Model: the headline LightGBM on the `forecast` feature set. Test days: winter 2021-22 to winter 2024-25 (the first two blocks are skipped because the calibration model needs more than a year of earlier data). Two views as before: **observed** (perfect-forecast weather, upper bound; 361 to 379 winter days) and **real forecasts** (archived forecasts from 2024; 140 to 146 winter days, 214 to 217 March to October days).

## Method and why (4.3.1)

Chosen by the project owner: split-conformal intervals plus Platt-scaled probabilities.

- **Calibration.** In every walk-forward block the last 365 training target days (with a gap equal to the lead) form a calibration year. A copy of the model fitted on the earlier rows forecasts that year, so the calibration errors are out-of-sample. The model used for the test days is refitted on all training rows.
- **Intervals.** Quantiles of the calibration errors give asymmetric 80% and 90% intervals. `plain` intervals add fixed error quantiles; `scaled` intervals use quantiles of the error divided by the forecast level (at least 15 ug/m3), so polluted days get wider intervals.
- **Probabilities.** Platt scaling is a logistic regression of "daily mean at or above 55.5 (or 35.5) ug/m3" on the forecast, fitted on the calibration year. For comparison, a "conformal" probability uses the share of calibration errors that would reach the threshold, and "base" is the calibration-year base rate.
- **Why this fits the data.** About 1,800 daily rows are too few for stable quantile models, no error distribution is assumed, and coverage is checked with the same leak-free protocol as the point forecasts. **Why it can fail:** conformal coverage holds on average only if calibration and test days are exchangeable. PM2.5 errors come in spells (error analysis), and the calibration year uses observed weather while the real-forecast test uses archived forecasts.

## Interval coverage (4.3.2)

Nominal 90%, share of winter days inside the interval (leads 1 / 2 / 3), with the mean interval width in ug/m3 in brackets:

| View | Plain | Level-scaled |
|---|---|---|
| Observed weather | 78.6% / 75.1% / 75.3% (48 / 56 / 61) | 85.5% / 84.6% / 80.3% (61 / 69 / 72) |
| Real forecasts | 71.9% / 69.9% / 67.9% (62 / 75 / 81) | 92.5% / 87.4% / 88.6% (87 / 115 / 127) |

- **Winter coverage falls short of 90% with observed weather**, for both interval types (block-bootstrap 95% intervals for the scaled version: [80, 90], [78, 91], [73, 87]). At the 80% level the scaled intervals cover 72% / 71% / 72%.
- **Scaling fixes the polluted days.** By forecast level (winter, observed view, lead 1) the plain interval covers 67% of days forecast at 55.5 to 100 ug/m3 and 40% of days forecast at or above 100, the scaled one 90% and 85% (20 days at or above 100; at leads 2 and 3 there are only 7 and 4 such days, too few to judge). The plain interval is too narrow in winter and too wide from March to October (coverage 95% to 97%), because one error spread is applied to every season; scaled intervals cover 85% to 89% from March to October.
- **Real forecasts: winter coverage is close to nominal (87% to 93%) but with very wide intervals** (87 to 127 ug/m3 wide, against 61 to 72 with observed weather). The model forecasts higher on average with real forecasts, so level-scaled intervals widen. In March to October 2024 the scaled intervals cover only 74%. These samples are small (about 140 and 215 days from one and a half years).
- **Coverage varies by block.** Scaled 90% coverage by test block with observed weather, lead 1: 85%, 94%, 86%, 86%, 75%, 80%, 94% (winter 2021-22, March to October 2022, winter 2022-23, March to October 2023, winter 2023-24, March to October 2024, winter 2024-25). The weakest are winter 2023-24 (73% to 75% at all leads) and winter 2022-23 at lead 3 (62%).
- **Misses come in spells.** In winter, with observed weather, 15% / 15% / 20% of days fall outside the 90% interval (leads 1 / 2 / 3), but after a miss the next day is also a miss on 21% / 39% / 44% of days (51 to 63 such days). Coverage is therefore correct only on average, and an interval that failed yesterday is more likely to fail again today. (Real-forecast samples after a miss are only 11 to 17 days.)

## Exceedance probabilities

Winter days, threshold 55.5 ug/m3 (observed rate 45%). Brier score (lower is better), skill against always forecasting the observed winter rate (a reference that already knows the answer on average), expected calibration error (ECE) and AUC:

| View | Lead | Method | Brier | Skill | ECE | AUC |
|---|---|---|---|---|---|---|
| Observed | 1 | Platt | 0.133 | 0.46 | 0.053 | 0.89 |
| Observed | 2 | Platt | 0.175 | 0.30 | 0.107 | 0.84 |
| Observed | 3 | Platt | 0.181 | 0.27 | 0.094 | 0.82 |
| Real forecasts | 1 | Platt | 0.197 | 0.21 | 0.168 | 0.84 |
| Real forecasts | 2 | Platt | 0.233 | 0.06 | 0.187 | 0.78 |
| Real forecasts | 3 | Platt | 0.244 | 0.02 | 0.200 | 0.76 |
| Real forecasts | 1 | Conformal | 0.159 | 0.36 | 0.067 | 0.85 |
| Real forecasts | 2 | Conformal | 0.190 | 0.24 | 0.066 | 0.78 |
| Real forecasts | 3 | Conformal | 0.194 | 0.22 | 0.096 | 0.77 |

- **With observed weather the probabilities are useful and reasonably calibrated.** Platt and conformal probabilities are equal in Brier score (differences of 0.0006, -0.0003 and -0.0010, all intervals include 0). Platt has the lower ECE (0.05 to 0.11 against 0.08 to 0.13).
- **With real forecasts Platt probabilities are overconfident.** The average predicted probability is 0.59 to 0.63 against an observed rate of 0.45 to 0.46. In the reliability table the bin with a mean predicted probability of 0.96 had an observed frequency of 0.62 at lead 1 and 0.71 at lead 3 (28 to 29 days per bin). The conformal probability is better calibrated (ECE 0.07 to 0.10) and has a lower Brier score. Platt minus conformal Brier: +0.037 [+0.012, +0.061], +0.043 [+0.005, +0.079] and +0.050 [+0.013, +0.090] (leads 1 / 2 / 3). This is a gap between the calibration year, which uses observed weather, and real forecasts, not a difference between the methods on equal data. The cause was not tested beyond this comparison.
- **At the 35.5 level** the pattern is the same with smaller gaps (real forecasts: Platt ECE 0.10 / 0.12 / 0.13, conformal 0.08 / 0.09 / 0.09).
- **As an alert rule**, "Platt probability at least 0.5" gives about the same F1 as "forecast at or above 55.5" (winter, real forecasts: 0.77 / 0.68 / 0.70 against 0.76 / 0.70 / 0.72), with higher recall (0.89 / 0.80 / 0.83 against 0.82 / 0.75 / 0.77) and lower precision.

## Where this fails (summary)

1. Winter coverage with observed weather is 80% to 86% instead of 90%, because errors are not exchangeable across winters and they come in spells.
2. Intervals are wide: 60 to 130 ug/m3 for a winter daily mean, comparable to the forecast itself on a typical day.
3. With real forecasts the calibration year is optimistic. Platt probabilities are overconfident and March to October 2024 coverage is 74%. A calibration period that uses archived forecasts would fix this, but they exist for only about 13 months.
4. The highest days remain hard: few observations at or above 100 ug/m3 are available for calibration, and the point forecast underpredicts them (error analysis).

## Decision for deployment (Phase 5)

Use the level-scaled 90% interval and report the 80% interval alongside it. State the winter coverage found here (about 85%), not the nominal 90%. For the probability of an exceedance, use the **conformal probability** rather than Platt scaling: it was better calibrated with real weather forecasts, the realistic case. Platt scaling was the method first chosen; the project owner confirmed the change to conformal on 2026-11-22. The API still returns both values, with conformal marked as the recommended one, and the web app shows only the conformal probability.
