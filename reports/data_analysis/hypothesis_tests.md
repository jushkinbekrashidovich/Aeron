# Hypothesis tests H1 to H5 (task 2.4)

Source: `notebooks/04_statistical_analysis.ipynb` (Part B), code `src/aeron/hypotheses.py` (19 unit tests on synthetic data with known answers), table `hypothesis_results.csv`, figures `reports/figures/04_h1_winters.png`, `04_h2_scatter.png`, `04_h3_sectors.png`.

## How these were run

- The hypotheses, thresholds, block length and decision rules of `docs/research/hypotheses.md` were **frozen in a commit before any test was computed** (2026-11-22). The test code was committed before it was run on the real data. Each test was run once as specified. Nothing was changed after seeing a result.
- **Not a clean confirmation.** The exploratory analysis in notebook 03 used the same data first and the direction of each effect was known. Results are "consistent with" or "not consistent with" a hypothesis. No test addresses a cause.
- Moving-block bootstrap, blocks of 14 consecutive calendar days that never cross a gap, 5,000 resamples, seed 0. Seven primary tests, so decisions use Bonferroni-adjusted 99.29% intervals; unadjusted 95% intervals are shown for information. Station: US Diplomatic Post only.

## Results (14-day blocks)

| Test | Estimate | 99.29% interval (decides) | 95% interval (unadjusted) | n | Decision under the frozen rule |
|---|---|---|---|---|---|
| H1 later minus earlier winters, mean daily PM2.5 (ug/m3) | +13.0 | [-3.3, 26.4] | [0.7, 22.3] | 612 days | **Not supported** (interval includes 0) |
| H2a Spearman, PM2.5 and mean wind speed | -0.56 | [-0.62, -0.41] | [-0.59, -0.45] | 690 days | **Supported** |
| H2b Spearman, PM2.5 and boundary layer height | -0.42 | [-0.49, -0.20] | [-0.45, -0.24] | 632 days | **Present but weak** |
| H2c Spearman, PM2.5 and ventilation index | -0.52 | [-0.59, -0.34] | [-0.56, -0.38] | 632 days | **Supported** |
| H3 mean hourly PM2.5, wind from E+NE minus N+NW, wind 3 to 10 km/h (ug/m3) | +26.5 | [14.0, 33.4] | [16.1, 30.0] | 8,082 hours (748 days) | **Supported** |
| H4 weekend over weekday ratio of mean daily PM2.5 | 1.011 | [0.880, 1.110] | [0.908, 1.074] | 690 days | **Inconclusive** |
| H5 drop in lag-1 autocorrelation of log PM2.5 after removing same-day weather | +0.158 | [0.084, 0.248] | [0.100, 0.214] | 632 days | **Supported** |

Four of seven are supported, one is present but weak, one is inconclusive and one is not supported.

## What each result means

**H1, winters differ: not supported.** The later three winters average 65.6 ug/m3 over 289 days against 52.6 over 323 days for the earlier three, a difference of 13.0. With only three winters per group and strong day-to-day dependence, the strict 99.29% interval reaches below 0 (-3.3). The unadjusted 95% interval (0.7 to 22.3) just excludes 0, so the data are not inconsistent with a real rise, but they do not establish it under the rule set in advance. The per-winter means (39.3, 50.8, 53.6, 53.5, 67.7, 68.6 and 61.5 ug/m3 from 2018-19 to 2024-25) rise, but their 95% intervals overlap widely. It would show nothing about emissions, weather or sensor change. The practical consequence stated in the hypotheses stays: report forecast skill per winter.

**H2, weather proxies: wind and ventilation supported, boundary layer height only weakly.** Wind speed has the strongest association (-0.56) and the upper end of its interval (-0.41) is clear of the -0.30 threshold. The ventilation index is also supported (-0.52, upper end -0.34). Boundary layer height (-0.42) is clearly negative but its interval reaches -0.20, so it is "present but weak" at 14-day blocks. **This decision depends on the block length:** it is also "present but weak" with 7-day blocks (upper end -0.24) and "supported" with 28-day blocks (upper end -0.36), so treat H2b as borderline. Secondary (unadjusted): the median PM2.5 in the calmest fifth of days is 53 ug/m3 above that of the windiest fifth (95% interval 40 to 58), and 39 (10 to 46) for boundary layer height and 47 (29 to 57) for ventilation. The correlation with the previous day's wind is -0.48, falls to -0.30 at two days and -0.20 at three days. For boundary layer height it is -0.28, -0.12 and -0.10, so the lagged value is not informative beyond one day. Whole-year correlations are of similar size (-0.48, -0.49, -0.51). The plots show relationships that are steep at low wind and boundary layer height and flat above, so a rank correlation describes them better than a straight line. These are ERA5 reanalysis values, not station measurements, and boundary layer height is not a direct inversion measure.

**H3, wind direction: supported.** At the same moderate wind speed (3 to 10 km/h), winter hours with ERA5 wind from the east or north-east average 73.4 ug/m3 (5,071 hours) against 47.0 (3,011 hours) for north or north-west, a difference of 26.5 with an interval of 14.0 to 33.4, above the 10 ug/m3 threshold at all block lengths. By sector the means are N 49, NE 71, E 75 and NW 45 ug/m3. After adjusting for wind-speed bin and hour of day (secondary, unadjusted) the ratio of the two groups is 1.30 (95% interval 1.12 to 1.39), smaller than the raw ratio of 1.56, so part of the raw difference goes with speed and time of day. It identifies no source: ERA5 direction is a grid-cell value and direction goes together with season, time of day and the type of weather.

**H4, weekday and weekend: inconclusive, by a narrow margin.** The ratio is 1.011, almost exactly 1. The 99.29% interval is 0.880 to 1.110, which exceeds the upper margin of 1.10 by 0.01, so the data cannot rule out a weekend effect of 10%. The unadjusted 95% interval (0.908 to 1.074) lies inside the margin; under that looser interval the result would count as supporting equivalence, but the frozen rule uses the adjusted interval. All-year ratio 0.972 (95% interval 0.91 to 1.01). Per winter the ratios range from 0.87 to 1.25 with wide intervals; winters 2021-22 (1.25) and 2022-23 (1.23) have higher weekend means, with an interval for 2022-23 of 1.00 to 1.53. There is no sign of a consistent weekend effect, but the data are too noisy to prove its absence at the chosen margin.

**H5, persistence and weather: supported.** The lag-1 autocorrelation of log daily PM2.5 in winter is 0.646. After removing the linear effect of same-day wind, boundary layer height, temperature and pressure it is 0.488, a drop of 0.158 (interval 0.084 to 0.248), above the practical threshold of 0.10. Weather therefore accounts for a part of the persistence, and most of it (0.49) remains unexplained by these four variables. The regression uses same-day observed weather, a perfect-forecast scenario, so it does not say how much a forecast of the weather could explain.

## Robustness and limits

- **Block length.** Decisions are the same at 7, 14 and 28 days except for H2b (above). All point estimates are identical by construction; only the intervals change.
- **Dependence.** Winter days are strongly autocorrelated, which is why block intervals are used. Whether 14 days removes all the dependence is not tested beyond the 7 and 28 day comparisons.
- **Multiple tests.** Seven primary tests; the secondary results are unadjusted and exploratory.
- **Small samples where it matters.** H1 rests on three winters per group, with missing days in every winter (winter 2018-19 starts in late November and winter 2024-25 ends on 25 February). H3 and H5 use observed ERA5 weather and one station.
- **Fitted on the same data used to choose the hypotheses.** The tests are not independent confirmation; a later winter would be the real test.

## Use in the rest of the project

H2a, H2c, H3 and H5 are consistent with the forecasting design (wind, ventilation and wind direction as inputs, weather alongside PM2.5 history). They did not decide any feature choice, which was made with forecast evaluation (`comparison.md`, `explainability.md`). Notably, the explainability analysis also finds forecast wind speed among the most used inputs, and the model's wind direction components matter less than speed (explainability report), which is in line with the smaller adjusted ratio in H3.
