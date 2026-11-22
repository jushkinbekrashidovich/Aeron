# Explaining the headline model (task 4.2)

Source: `notebooks/08_model_explainability.ipynb`; table `importance_winter.csv` in this folder; figure `reports/figures/08_dependence_lead1.png`. Model: LightGBM on the `forecast` feature set, refitted for every walk-forward block (as in the model comparison) and explained on that block's test days. Tools: TreeSHAP values computed by LightGBM (mean absolute value over winter days, in ug/m3) and permutation importance (rise in winter MAE when an input is shuffled). Observed view = perfect-forecast weather (upper bound, 446 to 467 winter days); real-forecast view = archived forecasts (about 140 winter days, 3 blocks).

**Everything below describes what the model uses, learned from one station's data. These are associations. None of it shows that an input changes PM2.5.**

## Global importance (4.2.1)

- **By group** (share of summed mean absolute SHAP, winter, observed view; leads 1 / 2 / 3): PM2.5 history 50% / 34% / 26%; forecast weather for the target day 35% / 46% / 50%; weather observed up to today 13% / 17% / 17%; calendar 3% / 4% / 7%. History dominates at lead 1 and forecast weather takes over from lead 2. In the real-forecast view the split is similar (forecast weather 41% / 49% / 57%).
- **Single inputs, lead 1:** the evening mean of the origin day (6.5 ug/m3), the origin-day mean (5.4), forecast mean wind speed (4.4), the origin-day sea-level pressure (1.6), and the forecast wind components (1.6 and 1.5). **Lead 3:** forecast wind speed (5.2), the 14-day mean (3.4), forecast gusts (2.8), pressure (2.5) and the 3-day rain index (2.3).
- **Permutation importance** names the same leaders: at lead 1 forecast wind speed (+8.8 ug/m3 MAE when shuffled) and the evening mean (+8.7), then today's mean (+4.8); at lead 3 gusts (+9.3) and wind speed (+8.0).
- **The two rankings only partly agree.** Spearman correlation over all inputs 0.69 / 0.54 / 0.44 (leads 1 / 2 / 3, observed view) and 0.27 to 0.34 with real forecasts; the top 10 share 8 to 9 inputs in the observed view and 5 to 6 with real forecasts. Many inputs are strongly related (wind speed, gusts and components; today's value, lags and rolling means), so credit is shared between them in a way that depends on the method. Compare groups, not single inputs.
- **Real forecasts shift the weight to wind.** Mean absolute SHAP of forecast wind speed is 8.8 / 6.1 / 8.0 with real forecasts against 4.4 / 4.7 / 5.2 with observed weather. Forecast wind is biased low, so the model sees "calm" days more often than it was trained on. This fits the overprediction seen with real forecasts (comparison report) but the link was not tested.

## Shape of the effects (4.2.2)

From the dependence plots and medians by fifth of each input (lead 1, observed view, winter):

- **Forecast wind speed:** median contribution +7.8 ug/m3 in the calmest fifth (below about 4.9 km/h), +2.6 around 6 to 7 km/h, about -1.4 around 8 to 9 and -3.1 in the windiest fifth. The effect is steep between 3 and 8 km/h and flat above about 9 km/h.
- **Origin-day PM2.5 and its evening mean:** contributions rise from about -3 to -5 (clean day) to +12 and +14 (top fifth), then flatten above about 100 to 150 ug/m3. The model cannot extrapolate beyond the highest values it has seen, which is the reason for the underprediction of the highest days in the error analysis.
- **Sea-level pressure (origin day):** about 0 below 1025 hPa and up to +5.7 (median of the top fifth, individual days up to +10) above about 1030 hPa. High pressure goes with higher forecasts, as expected in stagnant winter conditions.
- **Wind direction** (components u and v) matters much less than speed: mean absolute SHAP 1.1 to 2.1 against 4.4 to 5.2 for speed in the observed view, 0.9 to 1.7 against 6.1 to 8.8 with real forecasts.

**Local explanations** (lead 1, observed view, base value about 38 ug/m3):

- Highest forecast, target day 2023-12-14 (observed 214, forecast 131): the origin-day evening mean of 176 adds +32.6, a cold origin day (-14 C) +14.8, the origin-day mean 125 +11.8, light forecast wind (3.9 km/h) +10.2, high pressure (1036 hPa) +8.2.
- Largest winter underprediction, 2021-11-07 (observed 207, forecast 97): the origin day was an extreme 379 ug/m3, yet its contribution is only +19.2. The model has seen few days like it and saturates.
- Cleanest day, 2023-01-05 (observed 7, forecast 24): low evening mean (-5.1), westerly wind of 8.6 km/h (u component, -4.2), strong wind (-2.6). Still overpredicted, in line with the overprediction of clean days in the error analysis.

## Stability across winters (4.2.3)

- **Ranking is stable.** Spearman correlation of mean absolute SHAP over all inputs between pairs of winters is 0.83 to 0.94 at lead 1 and 0.88 to 0.92 at lead 3. Consecutive winters share 7 to 9 of their top 10 inputs.
- **Weights change.** The evening mean of the origin day matters about twice as much from winter 2022-23 on (mean absolute SHAP 8.5 / 7.6 / 9.4) as in 2020-21 and 2021-22 (3.5 / 3.6); forecast wind speed rises from 3.8 and 2.9 to 4.2, 4.5 and 6.4. Pressure is large only in 2020-21 (3.9, against 0.7 to 1.6 later). Part of this is the model being fitted on a growing training set, and the cause was not tested.
- **Permutation importance is less stable** (winter 2020-21 gives about zero or negative gains for most inputs, the evening mean gives +7.0 in 2022-23). With 70 to 110 days per winter the permutation numbers are noisy.

## Caveats

- Five winters, one station. The real-forecast view has about 140 winter days, so its rankings are weak evidence.
- SHAP and permutation importance split credit among related inputs differently. No input should be read as "the" driver.
- Explanations are about the model and the data it saw. For example, "forecast wind speed lowers PM2.5" means the model learned that days with strong forecast wind tend to have lower PM2.5, not that wind causes the change. Season, weather type and emissions move together.
- The model is not a physical model of the atmosphere. Effects above about 100 to 150 ug/m3 are not learned reliably.
