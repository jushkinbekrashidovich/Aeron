# Data sources

Entries are marked **Assessed** (checked with a real download or query on the retrieval date given) or **Candidate** (not yet checked). Fields marked *to verify* are filled in during Phase 1 from the source's own documentation and from real queries, not from assumption. Do not treat this page as evidence that complete data exists for Tashkent.

## Assessment template

| Field | Description |
|---|---|
| Source and URL | |
| License and terms of use | Including redistribution and attribution |
| Access method | API, bulk download, key required |
| Historical coverage | First and last timestamp per station |
| Temporal resolution | |
| Geographic coverage | Stations or grid, for Tashkent |
| Missing observations | Share missing, gap lengths |
| Measurement quality | Sensor type, calibration, known biases |
| Known limitations | |
| Retrieval date | |

## Candidates

### Tashkent Open Data portal (air quality) - Assessed, download blocked

- URL: https://opendata.tashkent.uz/eng/data/133 ("Tashkent Air Quality Monitoring") and https://opendata.tashkent.uz/eng/data/230 ("Dynamics of changes in air quality").
- Owner: Department of Digital Development under the Khokimiyat of Tashkent city. Network: locally made OXUS-WS stations (10 installed Nov-Dec 2022 per Gazeta.uz, March 2024; the reference paper reports 16 stations).
- Content (from the API description): 133 has Date, Time, Station, AQI, Humidity, Temperature, Precipitation, PM2.5. 230 has Date, Time, Humidity, Temperature, PM2.5, Fog, with no station column.
- Coverage (from portal metadata): 133 first posted 2024-03-18, last updated 2026-02-12. 230 first and last published 2025-02-20, although listed as updated daily.
- Access: GET without key or parameters, formats xlsx, csv, xls, json. **On 2026-11-17 `https://opendata-back.tashkent.uz/en/api/data/all/{133,230}/download/` returned HTTP 500 for every variant tried.** No data has been retrieved, so coverage, gaps and units are unverified.
- License: none stated in the portal metadata. *To verify* by asking the data owner.
- Concerns: the portal owner says humidity and fog inflate PM readings on its sensors. Fields and station count must be confirmed on a real pull.
- Next step: ask the Department of Digital Development for a bulk export and the license, or retry the download.

### Mendeley Data: Tashkent Air Quality dataset - Assessed

- URL: https://data.mendeley.com/datasets/nmpz7jds4f/2 (DOI 10.17632/nmpz7jds4f.2), Asqarov and Mamatov, TIIAME.
- License: CC BY 4.0. Cite as Asqarov (2026), Mendeley Data V2.
- Content: one station (41.322 N, 69.296 E, Henanoceanus AQM-09, about 3 m high). PM2.5, PM10, TSP, CO, NO, O3, SO2, TVOC, temperature, humidity, wind speed and direction.
- Coverage: 2024-02-26 to 2024-09-18, 9,546 rows at about 30 minutes, 96.9% complete per the README. No empty cells. Longest gap 2 d 8 h.
- Access: public file download, no key. Raw file in `data/raw/mendeley_tashkent/` (not committed). SHA-256 matches the published hash.
- Limitations: **no winter**. PM2.5 median 5 and mean 7.5 ug/m3, maximum 119. One station. Light-scattering PM sensor, so humidity bias is possible. Wind direction column name is garbled (`wind_degree/Ўг`), dates are MM/DD/YYYY. README describes version 1, the dataset is version 2.
- Retrieval date: 2026-11-17.
- Use: development and pipeline testing, not evidence of winter forecast skill.

### OpenAQ (air quality) - Assessed

- URL: https://openaq.org/ ; API v3 with a free key (`OPENAQ_API_KEY` in the untracked `.env`). Downloader: `src/aeron/openaq_download.py`, output in `data/raw/openaq/` (not committed) with `metadata.json`.
- Locations within 25 km of central Tashkent: two.
  - **US Diplomatic Post: Tashkent** (location 8881, sensor 25916, 41.367 N, 69.273 E). Reference-grade monitor, PM2.5 and O3 only. Hourly values from 2018-11-27 to 2025-02-25. 51,492 hourly rows, of which 7,411 have an empty value, leaving 44,081 valid hours (80.5% of the span). 91 gaps of 24 h or more, longest 2,783 h (from 2022-07-05), then 1,086 h (2019-04) and 744 h (2023-02). PM2.5 mean 40.4, median 29, maximum 978 ug/m3 (check outliers). 78 values are 0 or negative. Monthly means: January 57, December 67, November 61, May 22. License not stated by OpenAQ.
  - **Sputnik-4** (AirGradient low-cost sensor, location 4902926, sensors 13465748 PM2.5, 13465749 humidity, 13465750 temperature, 41.205 N, 69.233 E). License CC BY 4.0. Continuous hourly data only from about 2025-09 to 2026-01-19 (3,277 rows, one lone point on 2025-06-29 and a 1,528 h gap before September). PM2.5 mean 61.7, median 49, maximum 298 ug/m3. OpenAQ lists the sensor from 2023-07, but the API returned nothing before 2025-06-29.
- Retrieval date: 2026-11-17.
- Concerns: the US station stops in February 2025, so it cannot support a live or recent evaluation. One point source, no spatial coverage. Low-cost sensor accuracy and humidity bias for Sputnik-4. The empty values in the US series must be checked (instrument flags or missing readings).
- Use: the only source found so far that covers several winters (2019 to 2024) for one point in Tashkent.

### Open-Meteo (weather) - Assessed (historical reanalysis only)

- URL: https://open-meteo.com/ ; historical weather API `archive-api.open-meteo.com/v1/archive` (ERA5 reanalysis). No key. Downloader: `src/aeron/openmeteo_download.py`, output in `data/raw/openmeteo/` (not committed) with `metadata.json`.
- Pulled for the US Diplomatic Post coordinates (41.367 N, 69.273 E), UTC, hourly, 2018-11-01 to 2026-11-10: 70,368 rows with no missing values.
- Variables: temperature 2 m, relative humidity, dew point, precipitation, surface pressure, cloud cover, wind speed and direction at 10 m, wind gusts.
- Value ranges look plausible (temperature -26.3 to 44.6 C, with the minimum on 2023-01-12, humidity 6 to 100%, pressure 945 to 993 hPa).
- Retrieval date: 2026-11-17.
- License and terms, including non-commercial restrictions and attribution: *to verify* on the Open-Meteo terms page before any publication or commercial use.
- Concerns: ERA5 is model output on a coarse grid, not a station observation, and it is not the forecast weather available in real use. Using it as an input in evaluation is more favorable than operation. See the leakage rule in [methodology](../research/methodology.md). The archive also provides boundary layer height, shortwave radiation, vapour pressure deficit, mean sea-level pressure and snow depth, downloaded to `data/raw/openmeteo/era5_extra_tashkent_hourly.csv` (`src/aeron/openmeteo_extra_download.py`, retrieved 2026-11-17). Boundary layer height is missing for 2024-01-01 to 2024-06-30 (4,368 hours) and is not available as an archived forecast in the Previous Runs API. Shortwave radiation, vapour pressure deficit and pressure are available there. Pressure-level temperatures and winds returned no data.
- Forecast weather (checked 2026-11-17): the historical forecast API returned values identical to ERA5 for the days tested, so it is not usable as lead-specific forecast weather. The Previous Runs API (`previous-runs-api.open-meteo.com`, variables such as `temperature_2m_previous_day1`) does return forecasts issued 1 to 3 days earlier. Coverage at the US Embassy coordinates: temperature from 2022-01 or earlier, but relative humidity, precipitation, pressure, cloud cover and wind only from 2024-01-19 (about 51% of hours between 2023-01 and 2025-02). Realistic forecast-weather experiments are therefore limited to roughly Jan 2024 to Feb 2025, and the earlier years can only use ERA5. Downloaded 2026-11-17 for 2024-01-19 to 2025-03-01 (forecasts issued 2, 3 and 4 days ahead, `src/aeron/openmeteo_forecast_download.py`, `data/raw/openmeteo/forecast_previous_runs_hourly.csv`). Against ERA5 at the station: temperature MAE 1.7 to 2.0 C, humidity MAE 9 to 10 points, wind speed MAE 3.5 to 3.8 m/s with a bias of about -2.5.

### NASA Earthdata (satellite) - Candidate

- URL: https://earthdata.nasa.gov/
- Expected content: aerosol optical depth and related products.
- Coverage, resolution, access: *to verify*.
- Concern: aerosol optical depth is not ground-level PM2.5. It may be useful as a complementary feature, not as a substitute target. Cloud cover causes gaps.

### Other sources

Other reputable sources (for example, government monitoring networks or other reanalysis products) will be investigated in Phase 1 and added here with the same template.

## Reproducible download

Download scripts will be added with the first ingestion code, writing to `data/raw/` with the retrieval date. Raw data is not committed.
