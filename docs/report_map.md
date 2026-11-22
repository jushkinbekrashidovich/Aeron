# Map for the final report

For the person writing the final report. Each row says what can be claimed, where the number comes from, and what to say next to it. Everything traces to code in this repository. Re-running notebooks needs the processed data, which is not committed (see README).

## 1. Problem and scope

- Question, target (daily mean PM2.5, local day, 1 to 3 days ahead, issued at the end of the day) and the single-station scope: `docs/research/problem_statement.md`, `research_questions.md` (status table at the end), `methodology.md`.
- Why one station: `docs/research/feasibility_report.md`, `spatial_decision.md`.

## 2. Data

| Claim | Source |
|---|---|
| US Diplomatic Post, OpenAQ location 8881, hourly from 2018-11-27 to 2025-02-25; 1,823 daily means (at least 18 valid hours) of 2,282 days | `data/processed/metadata.json` (local), `docs/datasets/data_sources.md`, notebook 01 |
| 119 unbroken runs, longest 158 days; winter autocorrelation 0.64 / 0.41 / 0.31 at lags 1 / 2 / 3; 690 winter days are worth about 74 independent days | notebook 04 part A, `src/aeron/timeseries.py` |
| Cleaning rules and counts | notebook 02, `docs/datasets/cleaning_log.md`, `missing_data_policy.md` |
| Weather: ERA5 (2018 to 2026) and archived forecasts from 2024-01-19 (previous-runs API) | `docs/datasets/data_sources.md`, notebook 05 |
| Wind forecast bias about -2.5 km/h, fitted ratio about 1.5 | notebook 05, `src/aeron/features/bias.py` |
| Exploratory patterns (winter wind, ventilation, boundary layer, wind direction) | notebook 03, figures in `reports/figures/` |
| Hypothesis tests H1 to H5: wind and ventilation supported (Spearman -0.56 and -0.52), boundary layer height present but weak (-0.42), wind direction supported (+26.5 ug/m3), persistence reduction supported (0.158), weekday inconclusive (ratio 1.011, interval 0.880 to 1.110), winter difference not supported (+13.0, interval -3.3 to 26.4) | `reports/data_analysis/hypothesis_tests.md`, notebook 04 part B, `src/aeron/hypotheses.py`; frozen in `docs/research/hypotheses.md` (commit before the tests) |

## 3. Methods

| Claim | Source |
|---|---|
| Walk-forward blocks by season from winter 2020-21, expanding window, gap equal to the lead, assertion against leakage | `src/aeron/evaluation/splits.py`, `tests/test_evaluation_splits.py`, `methodology.md` |
| Features and the rule "only what is known at the origin" | `src/aeron/features/build.py`, `docs/datasets/feature_dictionary.md`, leakage tests in `tests/test_features.py` |
| Training on observed (ERA5) weather and testing on real archived forecasts | `methodology.md`, `comparison.md` ("How to read the numbers") |
| Paired 14-day block bootstrap for differences | `src/aeron/evaluation/metrics.py` |
| Interval and probability method | `src/aeron/uncertainty.py`, `reports/model_evaluation/uncertainty.md` |
| Experiment tracking (114 MLflow runs: 84 for the main comparison and 30 for the ablations) | `src/aeron/evaluation/tracking.py`, notebook 07 (local `mlruns/`, not committed) |

## 4. Results

| Result | Number | Source |
|---|---|---|
| Baselines and models, winter MAE at 1 / 2 / 3 days, real forecasts | persistence 24.1 / 32.4 / 35.1; ridge 18.2 / 22.4 / 23.6; LightGBM 17.1 / 20.9 / 22.0 | `comparison.md`, notebook 07, `model_comparison_metrics.csv` |
| Same, observed weather (upper bound) | LightGBM 15.5 / 18.6 / 19.2 | same |
| Weather effect (LightGBM with minus without weather) | -3.2 / -5.9 / -6.9 observed; -1.9 / -5.4 / -4.3 real forecasts | `comparison.md` |
| Models are close | differences between ridge and the trees at most about 2 ug/m3; with real forecasts all intervals against ridge include 0 | `comparison.md` |
| Lag window (RQ3) | seven lags with rolling statistics minus one lag: -0.1 / +0.3 / 0.0 (observed) | `comparison.md` |
| Wind bias correction | +0.0 / -0.1 / -0.8, intervals include 0 | `comparison.md` |
| Deep learning skipped | 1,823 daily means, 119 runs, flat partial autocorrelation | `deep_learning_decision.md` |
| Error structure, high days, episodes, stability | see below | `error_analysis.md`, notebook 07b |
| Intervals | 90% interval winter coverage 85.5 / 84.6 / 80.3% (observed), 92.5 / 87.4 / 88.6% (real forecasts); 74% in March to October 2024 | `uncertainty.md`, notebook 09 |
| Probabilities | conformal better calibrated with real forecasts (ECE 0.07 to 0.10 against 0.17 to 0.20) | `uncertainty.md` |
| Importance | group shares and top inputs; Spearman 0.83 to 0.94 between winters | `explainability.md`, notebook 08 |
| Replay check | winter MAE 17.5 / 21.7 / 21.2 with the replay model; 340 origin days | `docs/research/live_data_decision.md` |

Error analysis numbers: days at or above 100 are underpredicted by 40.6 / 53.8 / 58.7 (observed) and 24.0 / 34.5 / 30.6 (real forecasts); 18 / 17 / 18 episodes of two or more days at or above 100 (observed view); the 55.5 alert level was forecast on 93% / 84% / 80% (observed) of those days.

## 5. Discussion points the numbers support

- Weather forecasts add skill in winter at all leads; the gain from a more complex model is small and not reliably above noise.
- The model warns of severe days but understates how severe they are.
- Intervals are honest on average but not conditional on a spell.
- Calibration with observed weather is optimistic for real forecasts.

## 6. Not done, and why

`docs/research/limitations.md` (scope cuts and future work).

## 7. Figures

`reports/figures/` holds the figures made by notebooks 03 to 09. The error-analysis rolling MAE figure is `07b_rolling_mae.png`; the dependence plots are `08_dependence_lead1.png`.
