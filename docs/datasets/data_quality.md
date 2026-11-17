# Data quality

Status: draft (Phase 1). Findings from the data pulled on 2026-11-17, produced by the checks described below. A full quality assessment (notebook 02, flagged records, rule log) belongs to Phase 2. Variable definitions are in the [data dictionary](data_dictionary.md).

## US Diplomatic Post PM2.5 (OpenAQ, reference-grade)

Main source for the project.

| Check | Result |
|---|---|
| Rows, timestamps | 51,492 hourly rows, 2018-11-27 to 2025-02-25. Timestamps are unique, increasing and on the hour. |
| Empty values | 7,411 rows (14.4%) have no value. By year: 2018 130, 2019 1,521, 2020 351, 2021 552, 2022 3,107, 2023 707, 2024 857, 2025 186. The cause is unknown (instrument downtime or flagged data). |
| Valid hours | 44,081, which is 80.5% of the 54,765 hour span. Share by year: 2018 0.75, 2019 0.78, 2020 0.90, 2021 0.84, 2022 0.61, 2023 0.77, 2024 0.90, 2025 0.98. By month the share ranges from 0.68 (September) to 0.92 (January and June). |
| Gaps | 694 gaps in total. 137 gaps are 6 hours or longer and 91 are 24 hours or longer (together 9,419 hours). 8 gaps are 7 days or longer (6,019 hours). The median gap is 1 hour, the 90th percentile 24 hours. The longest are 2,783 hours (from 2022-07-05), 1,086 hours (2019-04) and 744 hours (2023-02). |
| Daily means | 1,824 local days have at least 18 observed hours. |
| Resolution | Whole numbers only (ug/m3). |
| Zeros | 78 values equal 0 (2024 has 69, mostly in clean spring and summer days, scattered through the day). Probably low values rounded to 0 rather than failures, not confirmed. Kept. |
| High values | 84 hours above 300 ug/m3 and 16 above 500, the maximum 978 (episode of 2021-11-04 and 05). Kept, because they are the events of interest. Not verified against another source. |
| Stuck values | Only 2 runs of 6 consecutive identical readings, none longer. |
| Jumps | 144 hourly changes exceed 100 ug/m3 in absolute value. They are consistent with episodes starting and ending abruptly, not checked individually. |
| Daily profile | In winter (local time) the mean is highest at night (about 61 to 67) and lowest in the afternoon (43 to 47). |
| Licence | Not stated by OpenAQ. To verify. |

Implications: the 2022 outage and the 14% empty hourly values mean models must handle missing history. Winters have usable but uneven coverage (for example winter 2022-23 has about 1,650 to 1,770 usable test hours against 2,100 to 2,500 in other winters).

## Sputnik-4 (AirGradient, low-cost)

| Check | Result |
|---|---|
| Coverage | 3,277 hourly rows. One lone value on 2025-06-29, then a gap of 1,528 hours and continuous data from about September 2025 to 2026-01-19. OpenAQ lists the sensor from 2023-07, but the API returned nothing earlier. |
| Values | PM2.5 minimum 0.008, median 49.4, mean 61.7, maximum 298 ug/m3. Humidity 13.7 to 63.4%, temperature 5.4 to 37.9 degrees C. No empty values. |
| Sensor quality | Low-cost light scattering sensor, so humidity bias is possible. Not quantified. |
| Licence | CC BY 4.0. |

## Mendeley Data TIIAME station

| Check | Result |
|---|---|
| Coverage | 9,546 rows, about 30 minute interval, 2024-02-26 to 2024-09-18. The README reports 96.9% temporal completeness and a longest gap of 2 days 8 hours. No empty cells and no duplicate timestamps. |
| PM2.5 | Minimum 0, median 5, mean 7.5, maximum 119 ug/m3. Summer only, so no winter conditions. |
| Duplicated columns | PM2.5 equals PM10 in 8.1% of rows and equals TSP in 7.8% of rows, which may reflect the sensor's size-bin processing. Not investigated. |
| Format issues | Dates are MM/DD/YYYY, the timestamps are local, the wind direction column name is garbled, and the README describes version 1 while the file is version 2. |
| Licence | CC BY 4.0. |

## ERA5 weather (Open-Meteo)

| Check | Result |
|---|---|
| Core variables | 70,368 hourly rows from 2018-11-01 to 2026-11-10 with no missing values. Ranges are plausible: temperature -26.3 to 44.6 degrees C (the minimum on 2023-01-12), humidity 6 to 100%, pressure 945 to 993 hPa. |
| Boundary layer height | Missing for 4,368 hours, 2024-01-01 to 2024-06-30, in every Open-Meteo model option tried. |
| Representativeness | Coarse grid output, not a station measurement. It does not resolve local inversions or urban effects. |
| Realism for forecasting | Observed weather is more favourable than the forecasts available in real use. |

## Archived forecasts (Open-Meteo Previous Runs)

| Check | Result |
|---|---|
| Coverage | Complete for the downloaded window 2024-01-19 to 2025-03-01 (9,792 hours). Between 0.4% and 0.9% of cells are empty. Before 2024-01-19 only temperature is available. Boundary layer height and snow depth have no archived forecast. |
| Accuracy against ERA5 (daily aggregates, 2 days ahead) | Temperature bias +0.9 degrees C, MAE 1.2, correlation 0.99. Wind speed bias -2.5 km/h, correlation 0.70. Cloud cover bias +5.7 points. |
| Historical forecast API | Returned values identical to ERA5 for the days tested, so it was not used. |

## Tashkent Open Data portal

Download fails with HTTP 500 for datasets 133 and 230 (retested 2026-11-17). No data was assessed. According to the portal's owner, humidity and fog inflate the readings of their sensors.

## Open issues

- The reason for empty hourly values in the US series (downtime or quality flags) is unknown.
- Zeros and extreme values are not validated against another source.
- The hour alignment between OpenAQ and Open-Meteo labels has not been verified.
- Sensor humidity effects are not quantified for any low-cost source.
- No cross-check between the US station and Sputnik-4 or the Mendeley station, which are in different places and periods.
- Licences for the OpenAQ US series, Open-Meteo and the city portal are unconfirmed.
