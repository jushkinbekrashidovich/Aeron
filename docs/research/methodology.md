# Methodology

Status: draft written at the end of Phase 1, based on the [feasibility report](feasibility_report.md). The target, horizons and single-station scope are confirmed. Phase 3 will implement them with tests, and the exploratory scripts in `src/aeron/` are not the final pipeline.

## 1. Task definition

- **Target.** Daily mean PM2.5 (ug/m3) over the local day (Asia/Tashkent, UTC+5). A day counts only if at least 18 hourly values were observed. Secondary: hourly PM2.5.
- **Events.** A daily mean at or above 55.5 ug/m3 (US EPA breakpoint, "unhealthy for sensitive groups" upper bound), and at or above 35.5 ug/m3 as a secondary threshold. Hourly analyses also use 100 ug/m3.
- **Forecast origin.** The end of local day O, using data observed up to that moment. Forecasts are for day O+1, O+2 and O+3. The main result is 1 day ahead.
- **Station.** The US Diplomatic Post station (OpenAQ location 8881) until multi-station data becomes available.

## 2. Data handling

- All timestamps are stored in UTC and converted to local time only for daily aggregation.
- Raw data is downloaded by scripts to `data/raw/` with the retrieval date, and is never committed.
- Missing values are not imputed. Rows need an observed target. Missing predictors are passed to the model as missing (models that accept this) or the row is dropped, and each analysis states which.
- Outliers are not removed. High values are the events of interest. Zeros and empty readings are reported in the data quality notes.
- Wind direction is encoded as sine and cosine components.

## 3. Leakage rules

1. Every feature for origin t uses only information available at t. PM2.5 lags and rolling statistics look backwards only.
2. Weather for the target period must be a forecast that existed at the origin. Observed weather (ERA5) at the target time is a perfect-forecast scenario, so results with it are labelled "upper bound" and are never the headline result.
3. Models may be trained on ERA5 weather (long history), then evaluated with archived forecasts issued at least one day before the origin (previous run k+1 for lead k). The distribution shift between the two is part of the evaluation.
4. Climatology, scalers, calibrators and any imputation are fitted on training data only.
5. Chronological splits only. No random train and test split of time series.
6. Variables with no archived forecast (boundary layer height, snow depth) are not used in headline models.

Phase 3 adds unit tests for these rules.

## 4. Evaluation design

- **Rolling origin.** For each test block (winters Nov to Feb, and Mar to Oct), train on all targets before the block (expanding window) and score on the block. Report winter separately and pooled, and each winter on its own because winters differ strongly.
- **Calibration.** If probabilities are calibrated, the calibrator is fitted on a separate earlier block (the previous winter in the exploratory work), and the base models do not see it.
- **No tuning on test data.** Hyperparameters are fixed or chosen on a validation block that precedes the test block. Post-hoc changes made after seeing test results are labelled as such and tested again on data not used for the choice.

## 5. Baselines

- Persistence (the last observed day, or hour).
- Climatology (training-period mean within 15 days of the same day of year, or by month and hour for hourly values).
- Always predicting an event (precision equals the base rate, F1 = 2r/(1+r)). This is the benchmark for exceedance forecasts, because winter days exceed 35.5 ug/m3 about 71% of the time.
- A history-only model, to separate the contribution of weather.

## 6. Metrics

- Point forecasts: MAE (main), RMSE, bias (prediction minus truth). Also by observed level, season and lead.
- Events: precision, recall and F1 at fixed cut-offs, AUC, average precision, and Brier skill over predicting the base rate. Report the base rate and the always-yes F1 next to every F1.
- Probabilities: Brier score, log loss, expected calibration error and reliability tables.
- Quantile forecasts: coverage overall and by forecast level, with the cost in alerts.
- Mean absolute percentage error is not used (zeros and low values).

## 7. Uncertainty

- Block bootstrap of 7-day blocks, resampling pooled test rows jointly across methods so that comparisons are paired. Report 95% percentile intervals for differences in MAE and Brier score.
- These intervals cover sampling within the data and not the variation between winters. Per-winter tables are reported next to them.

## 8. Models

- Gradient boosting (scikit-learn histogram version) as the first model, with fixed settings. Random forest, linear regression, XGBoost and LightGBM follow in Phase 3 with the same protocol.
- Quantile and classification variants for upper-tail and exceedance forecasts.
- Deep learning is deferred, because there are about 1,800 daily observations.

## 9. Reporting rules

- Nothing is reported as a result unless code in this repository produced it, with the data version and retrieval date.
- Preliminary analyses state the sample size, the station and the weather input type (observed or forecast).
- Findings describe association, not cause.
- Negative and inconclusive results are reported, including where a model does not beat a baseline.

## 10. Known limitations

- A single station and about five winters.
- Archived forecasts exist for about 13 months.
- Coarse ERA5 and forecast grids do not resolve local inversions.
- The reference series ends in February 2025, so the pipeline cannot be validated on the latest winter without new data.

## 11. Evaluation framework (implemented in task 3.1)

Code: `src/aeron/evaluation/` (`splits.py`, `metrics.py`, `tracking.py`), tested in `tests/test_evaluation_*.py`.

**Splits.** Test blocks are winters (November to February) and March to October, in time order from the winter of 2020-21, with an expanding training window. For lead k days a forecast for target day D is issued at the end of day D - k. A model used at that moment can only have been trained on rows whose target day is on or before D - k. For a block starting on day S, training therefore stops at target day S - k (the walk-forward gap equals the lead time). `assert_no_leakage` checks this for every split and a test shows that a split without the gap is caught. Hyperparameters are tuned on a validation period made of the last days of the training window (`train_validation_split`), again with a gap of k days before it, and the model is then refitted on the whole training window.

**Metrics.** Point forecasts: MAE (main), RMSE, bias and R2. MAPE exists but ignores days with an observed value below 10 ug/m3 and is not a main metric. Events: precision, recall and F1 next to the always-yes F1, plus AUC, average precision, Brier score and skill, expected calibration error, reliability tables and quantile coverage. Slices by season, block, lead time and observed level are made with `slice_metrics`. Slicing on the observed value (for example days above 100 ug/m3) selects on the outcome, so those errors are reported as a description of how the model behaves on such days and not as the accuracy a forecaster would expect. Comparisons between two methods use `paired_block_bootstrap`: non-overlapping blocks of 14 calendar days are resampled together for both methods, which keeps the comparison paired and the dependence between neighbouring days.

**Check against the exploratory results.** Persistence and climatology for the daily mean in winters 2020-21 to 2024-25, computed with the new splits on the processed data, give MAE of 21.7, 28.5 and 30.7 (persistence) and 26.6, 27.1 and 27.4 (climatology) at 1, 2 and 3 days. The exploratory scripts gave 21.7, 28.4 and 30.7, and 26.6, 27.1 and 27.3. The small differences come from the walk-forward gap and the cleaned data.

**Experiment tracking.** MLflow (local SQLite store in `mlruns/`, not committed; install with `pip install -e ".[tracking]"`). Each run records:

- parameters: model and its settings, feature set size, seed, split scheme (blocks, gap, window), lead time. Names that look like keys or tokens are dropped;
- tags: git commit and whether tracked files had uncommitted changes, checksums and build time of the processed tables (data version), and Python, numpy, pandas and scikit-learn versions;
- artifacts: the feature list and, optionally, the predictions of the run;
- metrics: named like `mae/winter/lead1`. Missing values are not logged.

To browse runs, install the full `mlflow` package and run `mlflow ui --backend-store-uri sqlite:///mlruns/mlflow.db`.
