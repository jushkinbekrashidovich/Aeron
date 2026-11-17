# Feasibility report (Phase 1)

Status: draft for review. Written 2026-11-17 from real queries, downloads and exploratory runs in this repository. Every number below comes from code in `src/aeron/` and is described in the linked notes. The modelling results are preliminary: one station, small samples, fixed settings, and code that predates the evaluation framework planned for Phase 3 (no leakage unit tests yet). They support feasibility decisions, not final claims.

Association, not causation: all findings describe associations in observed data.

## 1. Summary

- **What exists.** One long reference-grade PM2.5 series (US Embassy station, OpenAQ, Nov 2018 to Feb 2025, 44,081 valid hours with a 2022 gap of about four months). Complete ERA5 weather (2018 to 2026) and archived weather forecasts from 2024-01-19. A city network of low-cost stations exists but its data could not be downloaded.
- **What can be forecast.** Daily-mean PM2.5 one to three days ahead at the US Embassy point, and the probability that a daily mean exceeds 55.5 ug/m3, are feasible and beat simple baselines when weather inputs are used. Hourly values are noisy and peaks are not forecastable.
- **What cannot yet.** Multi-station and spatial forecasts (no accessible multi-station data), anything after February 2025 (the reference series ends), and reliable forecasts of the most severe episodes.
- **Recommended target:** daily mean PM2.5 (local day) at 1, 2 and 3 days ahead, at one station, with exceedance probabilities. Hourly forecasts become a secondary analysis.

## 2. Data found (RQ1)

Details and licences are in [data sources](../datasets/data_sources.md).

| Source | Content | Coverage | Access and licence | Verdict |
|---|---|---|---|---|
| OpenAQ, US Diplomatic Post (location 8881) | Hourly PM2.5 (and ozone), reference-grade monitor | 2018-11-27 to 2025-02-25. 44,081 valid hours (80.5% of the span). 91 gaps of 24 h or more, the longest 2,783 h from 2022-07-05. 14% of rows empty. | API with free key. Licence not stated by OpenAQ. | Core source. One point only. Series ends. |
| OpenAQ, Sputnik-4 (AirGradient) | Hourly PM2.5, humidity, temperature, low-cost | About 2025-09 to 2026-01-19 (3,277 hours). Listed from 2023-07 but the API returned nothing before 2025-06. | CC BY 4.0 | Too short for training. Useful as a recent cross-check. |
| Mendeley Data, TIIAME station | 30-minute PM and gases, weather | 2024-02-26 to 2024-09-18, one station, 96.9% complete, no winter. | CC BY 4.0 | Development and pipeline tests only. |
| Tashkent Open Data portal (datasets 133 and 230) | Per-station PM2.5, AQI, humidity, temperature, rain (133); city series with fog (230) | Posted from 2024-03-18 (133), network since 2022 to 2023, 10 to 16 stations reported. | No key. Licence not stated. **Download returns HTTP 500 (2026-11-17).** | Most valuable and currently blocked. |
| Open-Meteo ERA5 reanalysis | Hourly temperature, humidity, wind, pressure, cloud, radiation, boundary layer height, and more | 2018-11 to 2026-11, no gaps (boundary layer height missing 2024-01-01 to 2024-06-30) | Terms to verify before publication | Complete, but observed weather is more favourable than real forecasts. |
| Open-Meteo archived forecasts (Previous Runs API) | Forecasts issued 1 to 7 days earlier | Temperature from about 2022. Other variables from 2024-01-19. Not available for boundary layer height or snow. | As above | Needed for fair evaluation. About 13 months of history. |

Not assessed: satellite aerosol products, other air-quality networks, official Uzhydromet data, land use and elevation.

Data quality notes (to be expanded in `data_quality.md`): the US series has 7,411 empty hourly values and 78 zeros, and a maximum of 978 ug/m3 in November 2021, which looks like a real episode and was kept. Low-cost sensors may overread in humid or foggy air (stated by the portal owner). ERA5 values are grid-cell model output, not station measurements.

## 3. What the research questions can already say

All results are for the US Embassy point and are preliminary. Weather inputs are observed ERA5 unless marked "forecast weather".

**RQ2: do 24 h forecasts beat persistence?**
Yes with weather, not reliably without it.
- Hourly, 24 h, winters 2020-21 to 2024-25 (rolling origin, MAE): persistence 34.0, climatology 33.7, history-only model 31.4, history plus observed weather 27.1 ug/m3 ([rolling evaluation](preliminary_rolling_eval.md)).
- Daily mean, 1 day ahead, winter: persistence 21.7, climatology 26.6, history-only 19.0, with observed weather 16.0 ([daily](preliminary_daily.md)).
- Daily mean with archived forecast weather (139 to 145 winter days from 2024 to 2025): persistence 24.1, 32.4 and 35.1, history-only 20.0, 27.1 and 27.0, with forecast weather 17.1, 20.7 and 21.5 (wind removed), against climatology 25.7, for 1, 2 and 3 days ([forecast weather](preliminary_daily_forecast_weather.md)).

**RQ3: how much do weather features add?**
Most of the winter skill comes from weather.
- Hourly winter MAE falls by 4 to 6 ug/m3 when observed weather is added to history at every lead. With archived forecasts the loss against observed weather was about 1.5 ug/m3 ([GBM note](preliminary_gbm.md)).
- Daily, history-only forecasts beat climatology only at 1 day. With observed weather MAE is 16 to 19 ug/m3 at 1 to 3 days (27% to 32% of the winter mean of about 60).
- With archived forecasts the daily gain is smaller: 8.6, 5.0 and 4.2 ug/m3 over climatology at 1, 2 and 3 days after removing wind, which has a forecast bias of about -2.5 m/s (with wind included, 6.7, 2.7 and 1.7). That choice was made after seeing the results and needs an independent test.
- Boundary layer height, radiation and pressure add 1 to 3 ug/m3 hourly and nothing measurable for daily means ([stagnation](preliminary_stagnation.md)).

**RQ4: seasonal and weather patterns.** Partly answered. Monthly mean PM2.5 at the US station is 57 (Jan), 61 (Nov) and 67 (Dec) against 22 (May). Winter hours with low boundary layers average about 83 ug/m3 against 40 with high ones. No formal exploratory or statistical analysis has been done (Phase 2).

**RQ5: unseen periods and seasons.** The rolling evaluation scores five winters and four Mar to Oct blocks with models trained only on earlier data. The model with observed weather beats climatology in all of them, with large differences between winters (for example climatology MAE 47 in 2022-23 against 24 in 2020-21).

**RQ6: variation across stations.** Cannot be answered. Only one station has usable data.

**RQ7: high-pollution episodes.** Poor for hourly peaks, acceptable for daily exceedances at short range.
- Hours above 150 ug/m3 are underpredicted by 105 to 122 ug/m3 even with observed weather and stagnation inputs, and the 90th-percentile forecast covers only 4% to 13% of them ([error analysis](preliminary_error_analysis.md), [upper tail](preliminary_upper_tail.md), [stagnation](preliminary_stagnation.md)).
- Hourly detection of values at or above 100 ug/m3 is weak (F1 0.23 to 0.52).
- A daily mean of at least 55.5 ug/m3 (45% of winter days) is forecast with F1 0.78, 0.71 and 0.70 and AUC 0.88, 0.84 and 0.83 at 1, 2 and 3 days with observed weather. With forecast weather the 3-day values drop to F1 0.66 to 0.68 and Brier skill 12%, close to always predicting an exceedance (F1 0.62).
- Raw probabilities were too low by roughly a factor of two and Platt scaling fixed this on average ([calibration](preliminary_calibration.md)).

**RQ8: feature contributions.** Not yet analysed.

## 4. Feasibility decisions (proposed, to confirm)

| Question | Decision | Evidence |
|---|---|---|
| Target | Daily mean PM2.5 over the local day (Asia/Tashkent), at least 18 observed hours. Probability of exceeding 55.5 ug/m3 (and 35.5 as secondary). | Daily errors are 27% to 32% of the mean against 45% to 50% for hourly values. Hourly peaks are not forecastable. |
| Horizons | 1, 2 and 3 days, issued at the end of the local day. Report 1 day as the main result. | Skill with forecast weather is clear at 1 day, reduced at 2 days, and not distinguishable from climatology at 3 days for the full model. |
| Station | US Embassy station only for now. Revisit when city portal data is obtained. | Only series with several winters. |
| Weather input | Train on ERA5, test with archived forecasts issued k+1 days earlier. Report perfect-weather results only as an upper bound. | Forecast weather costs 4 to 6 ug/m3 of daily MAE. |
| Baselines | Persistence, climatology (day-of-year window), always predicting an exceedance. | Climatology beats persistence at 2 and 3 days. Always-yes is hard to beat at the 35.5 threshold. |
| Evaluation | Rolling-origin by season (winters and Mar to Oct), block bootstrap intervals, reporting winter separately. | One split with two partial winters could not separate models. |
| Models | Gradient boosting first. Compare with linear regression and random forest in Phase 3. Defer deep learning. | About 1,800 daily rows. Too little for deep models to be justified now. |
| Multi-station and maps | Deferred until multi-station data is accessible. | Download blocked. |

Dropped or deferred features:
- Boundary layer height and snow depth: no archived forecasts, so they cannot be tested in a fair forecast setting. Kept as analysis variables.
- Hourly peak forecasting and point forecasts above 100 ug/m3: not supported by the data. Report as a limitation.
- Satellite aerosol products: not assessed. Deferred.
- Live or recent forecasts: not possible with the US station (ends 2025-02-25) and the 4-month Sputnik-4 series. Requires the city portal data or another current source.

## 5. Risks and open items

- **Blocked city portal data.** Without it the project is a single-station study. Action: contact the Department of Digital Development for a bulk export and a licence statement, and the authors of the Tashkent paper. Not yet done.
- **Small effective sample.** About five winters and 140 days with forecast weather. Differences between winters are as large as differences between models.
- **Exploratory code.** The experiments were run before the Phase 3 evaluation framework (walk-forward splits with leak tests, MLflow). They need to be re-implemented and tested there before any result is reported as final.
- **No formal EDA, statistics, data dictionary or data quality report yet** (Phase 2).
- **Licences.** OpenAQ US station, Open-Meteo and the city portal terms must be confirmed before publication.
- **Sensor quality.** The US station is reference-grade. Humidity bias for low-cost sensors has not been quantified.

## 6. What Phase 1 still needs

- Confirm the decisions in section 4.
- Contact the data owners for the city portal export and licence.
- Notebooks 01 and 02 (data collection, data quality) and the `data_dictionary.md` and `data_quality.md` documents.
- Revise `tasks.md` and `roadmap.md` after confirmation. [Methodology](methodology.md) is drafted with the proposed decisions.

## 7. Evidence index

| Note | Subject |
|---|---|
| [literature notes](literature_notes.md) | Two papers: Tashkent hourly PM forecasting, Isfahan daily PM2.5 classification |
| [preliminary baselines](preliminary_baselines.md) | Persistence, 24 h mean and climatology |
| [preliminary GBM](preliminary_gbm.md) | First gradient boosting model, with archived forecast weather test |
| [preliminary rolling evaluation](preliminary_rolling_eval.md) | Nine seasonal blocks with bootstrap intervals |
| [preliminary error analysis](preliminary_error_analysis.md) | Error by pollution level, exceedance detection |
| [preliminary upper tail](preliminary_upper_tail.md) | Log, weighted, quantile and classifier variants |
| [preliminary stagnation](preliminary_stagnation.md) | Boundary layer height, radiation, pressure |
| [preliminary calibration](preliminary_calibration.md) | Probability calibration and conformal shift |
| [preliminary daily](preliminary_daily.md) | Daily-mean forecasts with observed weather |
| [preliminary daily forecast weather](preliminary_daily_forecast_weather.md) | Daily forecasts with archived forecast weather |
