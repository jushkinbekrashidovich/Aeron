# Model comparison (task 3.4)

Source: `notebooks/07_model_comparison.ipynb` (tables in `model_comparison_metrics.csv`, 114 MLflow runs). Target: daily mean PM2.5 (ug/m3) of the local day, 1, 2 and 3 days ahead, issued at the end of the local day. Single station (US Diplomatic Post). Walk-forward protocol with a gap equal to the lead (`docs/research/methodology.md`).

## How to read the numbers

- **Observed view** (all winters 2020-21 to 2024-25, 446 to 467 winter days): weather models get the weather that happened on the target day in place of a forecast. This is a perfect-forecast **upper bound**, not what a user would get.
- **Real forecast view** (archived forecasts, only from 2024, 140 to 146 winter days): the realistic case. The sample is small, so differences of about 1 to 2 ug/m3 between models are within noise.
- Intervals are 95% paired block-bootstrap intervals (14-day blocks) of the difference in MAE; a negative difference favours the first model. No correction for the number of comparisons was applied, so isolated "significant" intervals should not be over-read.
- Tuning used the last training year of each block with the same gap. Tree models use 300 trees and a small grid (depth, leaf size or learning rate).

## Winter MAE (ug/m3), leads 1 / 2 / 3

| Model | Observed view | Real forecasts |
|---|---|---|
| Persistence | 21.7 / 28.5 / 30.7 | 24.1 / 32.4 / 35.1 |
| Climatology | 26.8 / 27.1 / 27.2 | 25.9 / 25.7 / 25.8 |
| Ridge, history only | 17.6 / 23.5 / 25.1 | 19.0 / 25.8 / 27.0 |
| Ridge, forecast weather | 15.7 / 19.7 / 20.6 | 18.2 / 22.4 / 23.6 |
| Random forest, forecast weather | 15.1 / 18.5 / 19.1 | 18.0 / 22.9 / 23.5 |
| XGBoost, forecast weather | 15.1 / 18.9 / 18.4 | 17.7 / 22.1 / 22.0 |
| LightGBM, forecast weather | 15.5 / 18.6 / 19.2 | 17.1 / 20.9 / 22.0 |
| LightGBM, no wind | 16.7 / 21.0 / 21.2 | 16.8 / 21.6 / 21.4 |

## What the data show

1. **Every weather-aware model beats the naive forecasts in winter.** Ridge with forecast weather beats persistence by 6.0 to 11.5 ug/m3 and climatology by 2.2 to 11.2 (all intervals exclude 0), in both views.
2. **Weather matters more than the choice of model.** Adding weather to LightGBM cuts winter MAE by 3.2 / 5.9 / 6.9 in the observed view and 1.9 / 5.4 / 4.3 with real forecasts (intervals exclude 0 except lead 3 with real forecasts, [-8.6, +0.4]).
3. **Trees versus ridge: a small gain, mostly not distinguishable from noise.** With observed weather the random forest is 1.2 and 1.6 ug/m3 better than ridge at leads 2 and 3 (intervals exclude 0), XGBoost 2.2 better at lead 3. With real forecasts every interval against ridge includes 0.
4. **The three tree models are not separable from each other** in the observed view (differences of 0.1 to 0.3, except that XGBoost is 0.8 better than LightGBM at lead 3). With real forecasts LightGBM is 1.9 better than the random forest and 1.1 better than XGBoost at lead 2 (intervals exclude 0), but not at leads 1 and 3.
5. **Dropping the wind features is inconsistent.** It hurts by 1.3 / 2.3 / 2.1 with observed weather (intervals exclude 0) and changes the real-forecast result by -0.3 / +0.6 / -0.6 (all intervals include 0). So the earlier post hoc idea that wind forecasts hurt is not confirmed in MAE. What does hold is the bias: with real forecasts the models with wind overpredict (+1.6 to +10.4 ug/m3) and the no-wind models underpredict (-0.3 to -9.6), which fits the known low bias of forecast wind.
6. **Mar to Oct is different.** With observed weather the boosters are best (LightGBM 6.1 / 7.9 / 8.0 against ridge 6.8 / 8.9 / 9.7). With real forecasts in March to October 2024 (about 215 days) weather models are worse than history-only ones (ridge 10.5 against 7.7 at lead 1), and persistence (8.5) beats every model that uses forecast wind. Those models, trained on observed weather and fed real forecasts, overpredict in that block (bias +5 to +12).
7. **Exceedance of 55.5 ug/m3 (winter base rate 45%).** Always predicting an exceedance has F1 0.62. In the observed view the best models reach F1 0.79 to 0.80 at lead 1, 0.75 at lead 2 and 0.77 at lead 3 (random forest, ridge, XGBoost, LightGBM are all within a few points). With real forecasts the best models (0.75 to 0.78 at lead 1, 0.70 to 0.73 at lead 2, 0.70 to 0.73 at lead 3) are above the always-yes F1. The models with forecast wind have recall 0.74 to 0.92 and precision 0.57 to 0.71.
8. **All models underpredict on average in the observed view** (bias -2 to -11 ug/m3 in winter, most for the boosters) and RMSE is about 40 to 55% above MAE, so the highest days are missed. The extreme-event analysis is task 4.1.2.
9. **Winters differ.** Winter 2023-24 is the hardest block for every model (lead 1 MAE 20 to 22); winter 2020-21 the easiest (about 11 to 13). Results must be reported per winter (per-block table in the notebook).

## Ablations (LightGBM, forecast feature set)

- **Lag window (RQ3).** Using only today's value plus same-day statistics performs as well as 7 lags with rolling statistics. Winter MAE with the longest window minus that with one lag: observed view -0.1 / +0.3 / 0.0, real forecasts +0.6 / -0.4 / -0.4; every interval includes 0 (the lead 1 real-forecast interval is [-0.0, +1.3], the longer window slightly worse). In this dataset, PM2.5 history beyond the last day adds no measurable skill once weather is in, which agrees with the partial autocorrelation being close to zero after lag 1 (notebook 04 part A).
- **Wind bias correction.** The observed/forecast wind ratio was fitted on training days only and was about 1.5 in the last block. Corrected minus raw winter MAE: +0.0 / -0.1 / -0.8 with intervals [-1.0, +0.8], [-1.8, +1.5], [-2.9, +1.3]. No evidence that it helps PM2.5 forecasts, although it does reduce the wind error itself (notebook 05). It can only be tested on the real-forecast view.
- **Weather on or off.** See finding 2.

## Limitations of this comparison

- One station, five winters. The real-forecast view has about 140 winter days from two winters (2023-24 partially, 2024-25), so it cannot separate similar models. A forecast from a later winter would be the proper confirmation, and none exists.
- Training uses observed (ERA5) weather in place of the forecast, so test-time forecast errors are a distribution shift the models never saw. The Mar to Oct 2024 result suggests this shift can matter.
- Hyper-parameter grids are small (4 settings), by design given about 1,800 daily rows. No claim is made that these are optimal.
- No multiple-comparison correction in the tables above.
- The selected headline model is a decision for the project owner (task 3.4.5). The numbers above do not single out one winner: LightGBM, XGBoost, random forest and ridge with forecast weather are close.
