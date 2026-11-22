# Research questions


Each question is answered with evidence from this repository's code, or reported as unanswerable with the reason. 
Questions are divided into 2 parts:
 - Main questions: The project answers with key features
 - Optional questions: If time allows, and if we can find data. We will add analysis to answer these questions

MAIN:
RQ1: What air quality and weather related data exist for Tashkent (Uzbekistan), and are they relevant and sufficient for forecasting?
RQ2: Do 24 hour PM2.5 forecasts beat a persistence baseline, and by how much (MAE, RMSE)?
RQ3: How much do meteorological features improve forecasts over PM2.5 history alone? 
RQ4: What seasonal, daily and weather-related patterns appear in historical PM2.5? 

Optional:
RQ5: How well do models generalize to unseen time periods, including other seasons? 
RQ6: How does accuracy vary across stations? 
RQ7: How reliable are forecasts during high-pollution episodes? 
RQ8: Which features contribute most to the model's 24 hour forecasts, beyond recent PM2.5 history? (Only meaningful if RQ2 shows the model beats the baseline. Describes the model, not causes.)

## Hypotheses

Hypotheses are written down before testing, in the notebook or report that tests them, with the test and significance threshold. None are registered yet.


## Status of the questions (2026-11-22)

Evidence is in `reports/model_evaluation/` and the notebooks. Numbers are winter daily-mean errors in ug/m3 with real archived forecasts (about 140 days) unless stated, and are limited by one station.

| Question | Status | Answer in short | Where |
|---|---|---|---|
| RQ1 data | Answered | One reference-grade station (2018-11 to 2025-02) with complete ERA5 weather and 13 months of archived forecasts is enough for a single-station daily forecast. Several stations are not accessible. | `feasibility_report.md` |
| RQ2 beat persistence | Answered | In winter, yes: LightGBM 17.1 / 20.9 / 22.0 against persistence 24.1 / 32.4 / 35.1 at 1 / 2 / 3 days. Ridge with forecast weather beats persistence by 6.0 / 10.0 / 11.5 (intervals exclude 0). From March to October with real forecasts, persistence beats every model that uses forecast wind. | `comparison.md` |
| RQ3 weather vs history only | Answered | Weather cuts winter error by about 2 to 7 ug/m3 (LightGBM, leads 1 to 3). One lag of PM2.5 is as good as seven lags with rolling statistics once weather is in. | `comparison.md` |
| RQ4 patterns | Partly answered | Descriptive analysis is done (notebook 03). The formal hypothesis tests of section 2.4 are not run: `hypotheses.md` is not frozen. | notebooks 03, 04 |
| RQ5 unseen periods | Answered | Skill against persistence varies by winter (0.10 to 0.42 at lead 1); winter 2023-24 is the hardest; March to October 2024 is the weakest warm-season block. | `error_analysis.md` |
| RQ6 stations | Not answerable | Only one station has multi-year data. | `docs/research/spatial_decision.md` |
| RQ7 high episodes | Answered | Days at or above 100 are forecast too low by 24 to 59 ug/m3 on average, although the 55.5 alert level is reached on 80% to 100% of them. | `error_analysis.md` |
| RQ8 features | Answered | Origin-day PM2.5 and forecast wind at 1 day; forecast wind, gusts, the 14-day mean, pressure and rain at 3 days. Associations only. | `explainability.md` |
