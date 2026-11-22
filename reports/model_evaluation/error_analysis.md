# Error analysis of the headline model (task 4.1)

Source: `notebooks/07b_error_analysis.ipynb`; tables `error_by_level.csv` and `episodes_observed_view.csv` in this folder; figure `reports/figures/07b_rolling_mae.png`. Model: LightGBM on the `forecast` feature set, the headline model chosen in task 3.4.5. Errors are forecast minus observed daily mean PM2.5 in ug/m3. Sample sizes: the observed-weather view ("observed", an upper bound) has 446 to 467 winter days; the real-forecast view has 140 to 146 winter days and about 215 March to October days. One station and a daily target, so "by hour" and "by station" do not apply.

## 4.1.1 Error structure

- **Error is dominated by winter and by high days.** Winter MAE (observed view, leads 1/2/3) is 15.5 / 18.6 / 19.2 against 6.1 / 7.9 / 8.0 from March to October. In winter the days at or above 100 ug/m3 are 12% of days and give 33% / 36% / 38% of the total absolute error.
- **Strong pull towards the middle.** Low days are overpredicted and high days underpredicted, and the pattern grows with the lead. Winter bias by observed level (observed view, lead 1 / lead 3): below 25 ug/m3 +10.5 / +13.6; 25 to 55.5 +3.1 / +4.3; 55.5 to 100 -9.3 / -14.6; at or above 100 -40.6 / -58.7. With real forecasts it is similar and the low days are overpredicted more (below 25: +17.8 / +26.7), which fits the forecast-weather mismatch.
- **Calendar.** Errors are largest in December (MAE 19.9, bias -9.8) and January (17.0, bias -6.1) and smallest in May (4.3). Weekday MAE ranges from 7.9 (Monday) to 11.0 (Wednesday) with no obvious pattern; no test was run, so this is a description only.
- **Errors repeat from one day to the next.** The correlation of the winter error with the previous day's error is 0.25 / 0.38 / 0.52 at leads 1 / 2 / 3 (observed view) and 0.12 / 0.28 / 0.32 with real forecasts. The model misses whole spells, not single days, which matters for intervals (task 4.3) because daily errors are not independent.

## 4.1.2 Extreme events (RQ7)

- **Large underprediction of the highest days.** Winter days at or above 100 ug/m3 (observed view: 58 / 57 / 55 days at leads 1 / 2 / 3) have mean error -40.6 / -53.8 / -58.7. The forecast reaches 100 on only 31% / 5% / 4% of them. With real forecasts (17 / 16 / 16 days) the mean error is -24.0 / -34.5 / -30.6 and the forecast reaches 100 on 24% / 0% / 25%.
- **The alert level is usually reached.** The forecast is at or above 55.5 on 93% / 84% / 80% of those days (observed view) and 100% / 94% / 94% with real forecasts. Persistence reaches it on 86% / 65% / 67% (observed view). The model therefore warns of most severe days but understates how severe they are.
- **Episodes** (two or more consecutive days at or above 100, observed view): 18 / 17 / 18 episodes at leads 1 / 2 / 3. The forecast reached 55.5 on at least half the days of 17 / 14 / 14 of them and never on 1 / 2 / 4 of them. The never-alerted episodes are mostly in winter 2023-24 (for example 2023-12-29 to 2023-12-30 at lead 1). The biggest miss is 2021-11-06/07 at lead 3 (observed mean 293, forecast 69). One episode is outside winter (2024-09-28 to 2024-09-30, peak 171).
- **False alarms are rare.** Runs of two or more days with an alert forecast and no observed exceedance: 3 / 6 / 4 runs (8 / 14 / 9 days, of 197 / 172 / 159 alert days) in the observed view, and 1 / 5 / 3 runs with real forecasts.
- Ridge regression has the same problem (mean error on days at or above 100 of -32.9 / -53.8 / -59.3), so this comes from the data and the target (few extreme days, mean-squared and absolute-error training both shrink towards typical values), not from the choice of boosting. The model is trained with an absolute-error objective, which targets the median and underpredicts skewed peaks by design.

## 4.1.3 Temporal stability (RQ5)

- **No steady worsening or improvement.** Winter MAE at lead 1 by winter (starting year 2020 to 2024): 12.6, 11.4, 16.6, 22.3, 15.0. Winter 2023-24 is the worst for every model.
- **Error follows how polluted the winter was.** The two most polluted winters (mean 66 to 67 ug/m3) have MAE 16.6 and 22.3; the two cleanest (50 to 54) have 11.4 and 12.6. With five winters this is a description, not a tested relation.
- **Skill against persistence varies a lot by winter**: 0.10, 0.37, 0.23, 0.23, 0.42 at lead 1 (one minus the MAE ratio), and 0.19 to 0.53 at lead 3. In winter 2020-21 and 2023-24 the headline model is worse than ridge at lead 1 (12.6 against 10.9, and 22.3 against 20.5).
- **March to October 2024 is the weak block**: MAE 7.8 against persistence 8.5, skill 0.08, the lowest of any March to October block (0.19 to 0.23). It is also the block with forecast-weather mismatch (see `comparison.md`).
- The rolling 28-day MAE curve in `reports/figures/07b_rolling_mae.png` shows the error rising in each winter.

## Limits

- Five winters, one station, and a real-forecast sample of about 140 winter days from two winters. Block-level numbers rest on 70 to 110 days each and carry wide uncertainty; none of the statements above was tested with an interval except where `comparison.md` does so.
- Percentages of "days reaching the alert" use the same model on the same data used to describe it, with no correction for choosing which breakdowns to show.
