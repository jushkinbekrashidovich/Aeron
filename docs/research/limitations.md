# Limitations

Collected from the analyses in this repository. Each item points to where the evidence is. The list is for the final report and the Research page; it does not replace them.

## Data

1. **One station.** The US Diplomatic Post is the only multi-year series. All results describe one point in the city, and nothing about spatial variation is claimed (`spatial_decision.md`).
2. **The PM2.5 series ends on 2025-02-25** (valid hours from 2018-11-27). A current forecast needs another source. The demo has to replay historical data (`feasibility_report.md`).
3. **Gaps.** The daily series is made of 119 unbroken runs (longest 158 days) with a gap of about four months in 2022. Gaps are not filled (missing-data policy), which limits lag features and rules out ARIMA-style models (notebook 04, part A).
4. **Few winters.** Five winters (2020-21 to 2024-25) are used for testing and the first two blocks are used only for training. About 690 winter days are worth about 74 independent days given the autocorrelation.
5. **Licence.** The licence of the US series is not stated, so no data sample is committed. The results are reproducible only with the owner's OpenAQ key.
6. **Weather inputs are model output.** ERA5 is reanalysis on a grid, not station measurement. Boundary layer height has no archived forecast and is missing from ERA5 in 2024-01 to 2024-06.

## Forecast evaluation

7. **Archived forecasts exist only from 2024-01-19**, so the realistic test ("real forecasts") has about 140 winter days from two winters. Models are trained on observed (ERA5) weather and tested on forecasts, a distribution shift the models never saw. The observed-weather results are a perfect-forecast upper bound and are never the headline (`comparison.md`).
8. **Models are close.** Ridge regression, random forest, XGBoost and LightGBM are within about 1 to 2 ug/m3 winter MAE of each other, and with real forecasts no tree model is reliably better than ridge. The choice of LightGBM as headline model is a decision, not a finding (`comparison.md`).
9. **Forecast weather helps in winter only.** From March to October 2024 weather models are worse than history-only models on real forecasts, and persistence beats every model that uses forecast wind.
10. **Post hoc choices.** The wind-bias handling was looked at on the same two winters where the overprediction was seen. Dropping the wind features changes MAE inconsistently and is not confirmed.
11. **Small hyper-parameter grids** (4 settings per model). No claim is made that these are optimal. No correction for multiple comparisons was applied in the model comparison tables.
12. **No independent confirmation.** There is no later winter held out of all choices. The hypotheses were also written after exploratory analysis of the same data (`hypotheses.md`).

## Model behaviour

13. **The highest days are underpredicted.** Winter days at or above 100 ug/m3 are forecast too low by 24 to 59 ug/m3 on average, and the forecast reaches 100 on 0% to 31% of them. The alert level 55.5 is reached on 80% to 100% of them (`error_analysis.md`). Low days are overpredicted.
14. **Errors come in spells** (day-to-day correlation of the error 0.25 to 0.52 in winter), so daily errors are not independent. Winter 2023-24 is the hardest and the error follows how polluted the winter is.
15. **Explanations describe the model, not the atmosphere.** Importances are shared among related inputs, differ between SHAP and permutation importance (Spearman 0.44 to 0.69 with observed weather, 0.27 to 0.34 with real forecasts) and are associations only (`explainability.md`).
16. **No causal claims.** Wind, pressure and boundary layer relationships are associations in one station's data. Season, weather type and emissions move together.

## Uncertainty

17. **Intervals under-cover in winter with observed weather** (80% to 86% for a 90% interval) and are very wide (60 to 130 ug/m3). Misses cluster: after a miss, the next day is a miss on 21% to 44% of days.
18. **The calibration year uses observed weather.** With real forecasts, Platt probabilities are overconfident (mean 0.59 to 0.63 against an observed rate of 0.45) and March to October 2024 coverage is 74%. Conformal probabilities are better calibrated in that case (`uncertainty.md`).
19. **The first two blocks (winter 2020-21, March to October 2021) have no calibrated intervals** because the calibration model needs more than a year of earlier data.

## Scope cuts (decided by the project owner)

Hourly forecasts, deep learning (LSTM, GRU), spatial interpolation, a database and scheduled refresh, hosted deployment and the map page are not done (`deep_learning_decision.md`, `spatial_decision.md`).

## Future work

Ordered by how much each would change what can be claimed.

1. **More stations and winters.** Access to the city network data would allow station-level evaluation and leave-one-station-out spatial interpolation, and would answer RQ6. Another winter held out of all choices would give the confirmation this project lacks.
2. **A current data source.** A live PM2.5 feed that is validated against the reference monitor (the one low-cost sensor compared read about 40% as high) would allow current forecasts.
3. **Calibration with real forecasts.** Archived forecasts accumulate over time. Calibrating intervals and probabilities on days with real forecasts would remove the optimism of the observed-weather calibration year.
4. **The highest days.** Models trained for the upper tail (quantile or event-focused objectives, or a separate regime model for stagnant winter days) could reduce the underprediction of days at or above 100 ug/m3. The preliminary error notes suggest this is where most of the error lies.
5. **Hourly forecasts and sequence models.** Hourly targets give about 44,000 rows. Whether LSTM or GRU models help there was not tested.
6. **Hosted demo** with the data owner's permission, a live refresh job and uptime monitoring (`docs/deployment.md`).
