# Data dictionary

Status: draft (Phase 1). Describes the raw files currently produced by the download scripts in `src/aeron/`. A processed, merged dataset has not been built yet (Phase 2). Raw files are written to `data/raw/` by `python scripts/download_data.py` and are not committed. The subfolders `_months` (OpenAQ) and `_cache` (Open-Meteo) hold the per-block files that make downloads resumable, and the merged files below are rebuilt from them. Retrieval date for everything below: 2026-11-17. Sources, licences and coverage are in [data sources](data_sources.md), and known problems are in [data quality](data_quality.md).

## Conventions

- All timestamps in the raw files are UTC, written as ISO 8601 with a trailing `Z` (except the Mendeley file, see below). Local time (Asia/Tashkent) is UTC+5 all year and is used only for daily aggregation.
- OpenAQ hourly values are labelled with the start of the hour they average (`datetimeFrom`). Open-Meteo values are labelled with the hour. According to the Open-Meteo documentation, state variables are instantaneous at that hour and accumulated variables (precipitation, radiation) cover the preceding hour. A check against ERA5 temperature and humidity at the Sputnik-4 sensor puts the offset between the two label conventions at about a quarter of an hour or less, so no shift is applied (see [data quality](data_quality.md)).
- Missing values are empty cells. No imputation has been applied.

## `data/raw/openaq/<name>_hourly.csv`

Produced by `src/aeron/ingest/openaq.py`. `metadata.json` in the same folder records retrieval time, location and sensor ids.

| File | OpenAQ location | Sensor | Quantity | Unit |
|---|---|---|---|---|
| `us_embassy_pm25_hourly.csv` | 8881 (US Diplomatic Post: Tashkent) | 25916 | PM2.5, reference-grade monitor | ug/m3 |
| `sputnik4_pm25_hourly.csv` | 4902926 (Sputnik-4, AirGradient) | 13465748 | PM2.5, low-cost | ug/m3 |
| `sputnik4_humidity_hourly.csv` | 4902926 | 13465749 | Relative humidity | % |
| `sputnik4_temperature_hourly.csv` | 4902926 | 13465750 | Air temperature | degrees C |

| Column | Type | Meaning |
|---|---|---|
| `datetime_utc` | timestamp (UTC) | Start of the hour averaged |
| `value` | float | Hourly value in the unit above. Empty when OpenAQ returned no value for the hour. |
| `percent_complete` | float | OpenAQ coverage of the hour (100 in every row) |
| `observed` | int | Number of observations in the hour (1 in every row) |
| `expected` | int | Number expected (1) |

Station coordinates: US Diplomatic Post 41.3672 N, 69.2725 E. Sputnik-4 41.2047 N, 69.2325 E.

## `data/raw/openmeteo/era5_tashkent_hourly.csv`

Produced by `src/aeron/ingest/openmeteo.py` from the Open-Meteo historical weather API (ERA5 reanalysis). Location 41.3672 N, 69.2725 E (the nearest grid cell is used, so values are not point measurements). 70,368 hourly rows from 2018-11-01 00:00 to 2026-11-10 23:00, no missing values.

| Column | Unit | Meaning |
|---|---|---|
| `datetime_utc` | UTC | Hour label |
| `temperature_2m` | degrees C | Air temperature at 2 m |
| `relative_humidity_2m` | % | Relative humidity at 2 m |
| `dew_point_2m` | degrees C | Dew point at 2 m |
| `precipitation` | mm | Precipitation in the preceding hour |
| `surface_pressure` | hPa | Pressure at the surface |
| `cloud_cover` | % | Total cloud cover |
| `wind_speed_10m` | km/h | Wind speed at 10 m |
| `wind_direction_10m` | degrees | Direction the wind comes from (0 to 360) |
| `wind_gusts_10m` | km/h | Wind gusts at 10 m |

## `data/raw/openmeteo/era5_extra_tashkent_hourly.csv`

Produced by `src/aeron/ingest/openmeteo.py`, same source and location, 70,368 rows.

| Column | Unit | Meaning | Missing |
|---|---|---|---|
| `boundary_layer_height` | m | Height of the atmospheric boundary layer | 4,368 hours: 2024-01-01 to 2024-06-30 |
| `shortwave_radiation` | W/m2 | Shortwave radiation, preceding hour mean | none |
| `vapour_pressure_deficit` | kPa | Vapour pressure deficit | none |
| `pressure_msl` | hPa | Mean sea-level pressure | none |
| `snow_depth` | m | Snow depth | none |

## `data/raw/openmeteo/forecast_previous_runs_hourly.csv`

Produced by `src/aeron/ingest/openmeteo.py` from the Open-Meteo Previous Runs API. 9,792 hourly rows from 2024-01-19 to 2025-03-01 (UTC) for the same location.

Column names have the form `<variable>_previous_day<N>` for N = 2, 3 and 4. Each is the forecast for that hour that was issued about N days before it. Variables: `temperature_2m`, `relative_humidity_2m`, `precipitation`, `surface_pressure`, `cloud_cover`, `wind_speed_10m` (km/h), `wind_direction_10m`, `wind_gusts_10m` (km/h), `shortwave_radiation` (W/m2), `vapour_pressure_deficit` (kPa), `pressure_msl` (hPa). Units match the ERA5 files. Between 0.4% and 0.9% of cells in each column are empty. They are the first hours of the archive, the same for every variable (see data quality and the [missing data policy](missing_data_policy.md)).

`forecast_previous_runs_metadata.json` records the request.

## `data/raw/mendeley_tashkent/all_sensor.csv`

Downloaded from Mendeley Data (DOI 10.17632/nmpz7jds4f.2, CC BY 4.0), one station at TIIAME (41.322 N, 69.296 E). 9,546 rows, about 30 minute interval, 2024-02-26 11:22 to 2024-09-18 14:47, local time (not UTC).

| Column | Unit | Meaning |
|---|---|---|
| `Date` | MM/DD/YYYY | Local date |
| `Time` | HH:MM:SS | Local time |
| `CO/ppm`, `NO/ppb`, `O3/ppb`, `SO2/ppb` | ppm or ppb | Gases (`NO` is nitric oxide, not NO2) |
| `PM10/ug/m3`, `PM25/ug/m3`, `tsp/ug/m3` | ug/m3 | Particulate matter, light scattering |
| `tvoc/ppm` | ppm | Total volatile organic compounds |
| `Temperature` | degrees C | Air temperature |
| `Humidity/%RH` | % | Relative humidity |
| `wind_speed/m/s` | m/s | Wind speed |
| `wind_degree/Ўг` | degrees | Wind direction (garbled column name in the source) |

Note that this file's wind speed is in m/s, while the Open-Meteo files use km/h.

## `data/interim/openaq/<series>_flagged.csv`

Produced by `python scripts/clean_data.py` for each PM2.5 series (`us_embassy_pm25`, `sputnik4_pm25`), from `src/aeron/cleaning.py`. One row per hour on a continuous hourly grid from the first to the last row of the raw file. Not committed. The rules are in [cleaning log](cleaning_log.md).

| Column | Meaning |
|---|---|
| `datetime_utc` | Start of the hour, UTC |
| `value_raw` | Value from the raw file (empty if missing) |
| `row_present` | 1 if the raw file has a row for this hour, 0 if the hour is absent |
| `missing`, `negative`, `above_max`, `zero`, `spike`, `spike_extreme`, `stuck` | 1 if the rule applies to the hour |
| `value_clean` | `value_raw` with negative, above-limit, extreme-spike and stuck readings set to missing |

## Processed tables (`data/processed/`)

Built by `python scripts/build_dataset.py` (code in `src/aeron/processing.py`) after `download_data.py` and `clean_data.py`. Not committed. `metadata.json` records the build time, row counts and parameters. Nothing is imputed (see the [missing data policy](missing_data_policy.md)). No sample file is committed, because the licence of the US station series is not stated.

### `hourly_us_embassy.csv`

One row per UTC hour on the US station's grid (2018-11-27 21:00 to 2025-03-04 11:00, 54,927 rows, 53 columns). Index column `datetime_utc` is the start of the hour.

| Columns | Meaning |
|---|---|
| `pm25` | Cleaned hourly PM2.5, ug/m3 (empty when missing or removed by a cleaning rule) |
| `pm25_raw` | PM2.5 from the raw file |
| `flag_zero`, `flag_spike`, `flag_spike_extreme`, `flag_stuck` | 1 if the cleaning rule applies (see [cleaning log](cleaning_log.md)) |
| `era5_<variable>` | ERA5 core and extra variables for the hour, same names and units as the raw files (wind in km/h) |
| `fc_d2_<variable>`, `fc_d3_<variable>`, `fc_d4_<variable>` | Archived forecast of the variable for this hour, issued 2, 3 or 4 days earlier. Empty before 2024-01-20 and after 2025-03-01. |

### `daily_us_embassy.csv`

One row per local day (Asia/Tashkent, UTC+5) from the first to the last day with a valid PM2.5 hour (2018-11-28 to 2025-02-25, 2,282 rows, 72 columns). Index column `date` is the local date. Days with no daily mean stay in the table with an empty `pm25_mean`.

| Column | Meaning |
|---|---|
| `pm25_hours` | Number of observed hours in the local day (0 to 24). The first day has only 22 hours of data. |
| `pm25_mean`, `pm25_max` | Mean and maximum of the observed hours, empty if fewer than 18 hours (1,823 days have a mean) |
| `pm25_eve_mean` | Mean over local 18:00 to 23:59, empty if fewer than 4 hours |
| `era5_temp_mean`, `era5_temp_min`, `era5_temp_max` | Temperature, degrees C |
| `era5_rh_mean` | Mean relative humidity, % |
| `era5_wind_mean`, `era5_gust_max` | Mean wind speed and maximum gust, km/h |
| `era5_precip` | Daily precipitation, mm |
| `era5_pres_mean`, `era5_msl_mean`, `era5_msl_chg` | Mean surface pressure, mean sea-level pressure (hPa) and its change from the previous day |
| `era5_cloud_mean` | Mean cloud cover, % |
| `era5_ssr_sum` | Sum of hourly shortwave radiation, W/m2 x h |
| `era5_vpd_mean` | Mean vapour pressure deficit, kPa |
| `era5_snow` | Maximum snow depth, m |
| `era5_rain3` | Precipitation over the day and the two previous days, mm |
| `era5_wind_u`, `era5_wind_v` | Daily mean east and north components of the wind vector, km/h (the wind direction as a vector, so averages are meaningful) |
| `era5_blh_mean`, `era5_blh_min` | Mean and minimum boundary layer height, m (empty for 2024-01-01 to 2024-06-30) |
| `era5_vent_mean` | Mean of boundary layer height times wind speed (m x km/h) |
| `fc_lead1_*`, `fc_lead2_*`, `fc_lead3_*` | The same weather aggregates, including the wind components (without snow, boundary layer height and ventilation) computed from the forecast issued lead + 1 days earlier. A day needs at least 22 forecast hours. Empty before the archive starts. |

Each row holds observations of its own local day. The `fc_lead*` columns are forecasts that existed before that day, which is what a real forecast could use, while the `era5_*` weather columns are the weather that happened (a perfect-forecast scenario, see the [methodology](../research/methodology.md)). A model for lead k must not use `era5_*` weather of the target day as a headline input.

## Derived quantities used in the exploratory scripts

These are computed in code and are not stored. They will be documented again when the processed dataset exists.

| Name | Definition | Code |
|---|---|---|
| Daily mean PM2.5 | Mean of hourly values over a local day, only if at least 18 hours are observed | `daily_experiment.py` |
| Wind components `wind_u`, `wind_v` | From wind speed and direction (direction the wind comes from) | `gbm_experiment.py` |
| PM2.5 lags and rolling statistics | Look backwards from the forecast origin only | `gbm_experiment.py`, `daily_experiment.py` |
| Ventilation proxy | Boundary layer height times wind speed (km/h) | `stagnation_experiment.py` |
| EPA levels | Breakpoints 12.0, 35.4 and 55.4 ug/m3, plus 100 ug/m3 | `error_analysis.py` |

## Not yet documented

- The processed merged dataset (Phase 2.2.4).
- Any cleaned station metadata table.
- Data from the Tashkent Open Data portal (download blocked), including its AQI definition and station list.
