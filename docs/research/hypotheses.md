# Hypotheses (draft for review)

Status: **draft, not yet registered.** Nothing in this document has been tested. After review, the hypotheses, thresholds and methods below are frozen before notebook 04 runs any test, and any change afterwards is recorded as a change with its reason.

All hypotheses describe associations in observed data from one station (US Diplomatic Post, 2018-11 to 2025-02). None of them tests a cause.

## 1. A limit on how confirmatory these tests are

The exploratory analysis (notebook 03) was run on the same data before this document was written, and the hypotheses below were chosen after seeing its figures and numbers, including the direction of each effect. The tests are therefore not a clean confirmation on new data. To limit the harm:

- the thresholds and decision rules below are written before any interval is computed;
- all primary tests are reported, whether or not they succeed, with the number of tests stated;
- any test added later is labelled exploratory;
- results are described as "consistent with" or "not consistent with" a hypothesis, and not as proof.

The real test of whether these associations hold would be new data (a later winter), which this project does not have.

## 2. Common design

**Data.** `data/processed/daily_us_embassy.csv` (local days, daily mean needs at least 18 observed hours) and, for H3, `hourly_us_embassy.csv`. Winter means November to February. The first winter (2018-19, 78 days from late November) is excluded from tests that compare winters. Days or hours with a missing variable are dropped from the test that needs it (pairwise deletion). Boundary layer height is missing from 2024-01-01 to 2024-06-30, so tests using it use the other days.

**Dependence.** Daily PM2.5 is strongly autocorrelated (winter lag-1 autocorrelation 0.69, lag 7 about 0.25), so ordinary p-values and intervals would be too optimistic. Every interval below is a **moving-block bootstrap**: resample blocks of 14 consecutive days (a block never crosses a gap in the data), 5,000 resamples, seed 0. Sensitivity runs use 7-day and 28-day blocks. The autocorrelation diagnostics in notebook 04 (part A) support this choice: winter daily autocorrelation is 0.12 at 14 days and 0.08 at 21 days, and the 690 winter days are worth about 74 independent days. For hourly data (H3) the blocks are 14 days of hours.

**Multiple tests.** The primary family has 7 tests (H1, H2a, H2b, H2c, H3, H4, H5). Decisions use Bonferroni-adjusted intervals, that is 99.29% intervals (1 - 0.05 / 7). Per-test results are also shown with 95% intervals, labelled as unadjusted.

**Effect size before significance.** A hypothesis counts as supported only if the interval excludes the null value and the estimate passes the practical threshold stated for it. The thresholds are set so that a result is large enough to matter for forecasting, which is the project's purpose. A statistically clear but tiny effect is reported as "present but small".

**Outcome.** Daily mean PM2.5 in ug/m3 (or its natural log where a ratio is stated).

## 3. Hypotheses

### H1. Winters differ

- **Claim.** Winter air is dirtier in the three most recent complete winters (2022-23, 2023-24, 2024-25) than in the three earlier complete winters (2019-20, 2020-21, 2021-22).
- **Null.** The mean daily PM2.5 of the two groups of winters is the same.
- **Test.** Difference between the mean winter daily PM2.5 of the later and earlier groups, with a block bootstrap interval (blocks resampled within each group).
- **Supported if** the 99.29% interval excludes 0 and the difference is at least 5 ug/m3.
- **Not supported if** the interval includes 0. A difference below 5 with an interval excluding 0 is reported as present but small.
- **What it would show.** That winters differ beyond sampling variation, so forecast evaluation must be reported per winter. It would not show a trend, a cause, or whether the difference is weather, emissions or instrument drift.
- **Secondary (unadjusted).** Per-winter means and medians with 95% intervals.

### H2. Weather and stagnation proxies (three tests)

Outcome: winter daily mean PM2.5. Predictors are same-day ERA5 values: H2a mean wind speed, H2b mean boundary layer height, H2c ventilation index (boundary layer height times wind speed). These are reanalysis fields and not station measurements, and boundary layer height is not a direct inversion measure.

- **Claim.** Winter daily PM2.5 is lower on days with more wind (H2a), a deeper boundary layer (H2b) and a larger ventilation index (H2c).
- **Null.** The Spearman correlation between PM2.5 and the predictor is zero (or positive).
- **Test.** Spearman correlation on winter days with a block bootstrap interval.
- **Supported if** the upper end of the 99.29% interval is below -0.30 (at least a moderate negative association).
- **Not supported if** the upper end is -0.30 or higher. A correlation that is negative but weaker than -0.30 is reported as present but weak.
- **Secondary (unadjusted).** Difference in median PM2.5 between the lowest and highest fifth of each predictor; the same correlations for lags of 1 to 3 days and for the whole year.

### H3. Wind direction at similar wind speed

- **Claim.** Hours with wind from the east or north-east have higher PM2.5 than hours with wind from the north or north-west, among winter hours with the same moderate wind speed.
- **Null.** The mean PM2.5 of the two direction groups is the same.
- **Test.** Winter hours with ERA5 wind speed above 3 and up to 10 km/h. Sectors are the 45 degree sectors centred on N, NE, E and NW (as in notebook 03). Group A is E and NE, group B is N and NW. Difference of the group means with a block bootstrap interval.
- **Supported if** the 99.29% interval excludes 0 and the difference is at least 10 ug/m3.
- **Not supported if** the interval includes 0. A smaller difference is reported as present but small.
- **What it would show.** That wind direction in ERA5 carries information about PM2.5 at similar wind speed. It would not identify a source, because the ERA5 wind is a grid-cell value and direction is confounded with season, time of day and weather type.
- **Secondary (unadjusted).** An ordinary least squares fit of log PM2.5 on wind-speed bin, direction group, winter indicator and hour of day, with block bootstrap intervals for the direction coefficient.

### H4. Weekday and weekend

- **Claim.** There is no practically relevant difference in daily PM2.5 between weekends and weekdays.
- **Test.** Ratio of the mean daily PM2.5 on Saturdays and Sundays to the mean on Monday to Friday, for winter days, with a block bootstrap interval (equivalence test against a margin of plus or minus 10%).
- **Supported (no meaningful difference) if** the 99.29% interval for the ratio lies inside 0.90 to 1.10.
- **Contradicted if** the interval lies entirely outside 0.90 to 1.10.
- **Inconclusive** otherwise (the data cannot rule out a difference of 10%).
- **Secondary (unadjusted).** The same for all days of the year, and for each winter.

### H5. Persistence and weather

- **Claim.** Part of the day-to-day persistence of winter PM2.5 is explained by persistence in the weather.
- **Null.** The lag-1 autocorrelation of log daily PM2.5 is the same before and after removing the linear effect of same-day weather.
- **Test.** For winter days with all predictors, fit an ordinary least squares regression of log daily PM2.5 on same-day mean wind speed, mean boundary layer height, mean temperature and sea-level pressure. Compute the lag-1 autocorrelation of the log PM2.5 and of the residuals, and their difference, with a block bootstrap interval (the regression is refitted in every resample).
- **Supported if** the 99.29% interval for the reduction excludes 0 and the reduction is at least 0.10.
- **Not supported if** the interval includes 0. A smaller reduction is reported as present but small.
- **What it would show.** That weather accounts for a share of the persistence. It does not mean the weather causes the remainder, and the regression uses same-day observed weather, a perfect-forecast scenario.

## 4. Diagnostics that are not hypotheses (task 2.4.2)

These are reported as properties of the series, with no decision rule:

- autocorrelation and partial autocorrelation of daily PM2.5 and of log daily PM2.5, by season;
- stationarity tests (augmented Dickey-Fuller and KPSS) on the daily series, on the log series and on the deseasonalised series, reported with their limits (gaps, seasonality, heteroscedasticity);
- the implications for model design, such as which lags to include and whether to model in logs.

## 5. What happens with the results

- Results go in notebook 04 and a summary in `reports/data_analysis/`.
- Each hypothesis is reported as supported, not supported, contradicted or inconclusive under the rules above, with its estimate, interval and sample size.
- If a hypothesis is not supported, that is stated in the same place, and the feature or analysis it motivated is not presented as established.
- Results feed the feature choices in Phase 3 only as hypotheses to test with forecast evaluation, not as conclusions.

## 6. Questions for review

1. Are the practical thresholds right (5 ug/m3 for winters, correlation -0.30, 10 ug/m3 for wind direction, a 10% margin for weekdays, 0.10 for the autocorrelation drop)? They are judgement calls, based on the forecast errors seen so far (16 to 19 ug/m3 for daily means).
2. Is 14-day blocks with 99.29% Bonferroni intervals the right level of strictness for 7 tests?
3. Should any hypothesis be dropped, or one added (for example for rain or surface pressure)?
