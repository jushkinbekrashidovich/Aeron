# Data sources

All entries below are **candidates that have not yet been assessed**. Fields marked *to verify* are filled in during Phase 1 from the source's own documentation and from real queries, not from assumption. Do not treat this page as evidence that complete data exists for Tashkent.

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

### OpenAQ (air quality)

- URL: https://openaq.org/
- Expected content: PM2.5, PM10, NO2, SO2, CO, O3 with station coordinates and timestamps, aggregated from multiple providers.
- Coverage for Tashkent: *to verify* (stations, providers, date ranges).
- License: *to verify*; terms can differ per data provider.
- Access: API; whether a key is required *to verify*. Keys, if needed, go in an untracked `.env` file.
- Concerns to examine: low-cost sensor versus reference-grade instruments, gaps, duplicated stations.

### Open-Meteo (weather)

- URL: https://open-meteo.com/
- Expected content: temperature, humidity, wind speed and direction, pressure, precipitation, cloud cover; historical and forecast.
- Coverage and resolution: *to verify*.
- License and terms, including non-commercial restrictions and attribution: *to verify*.
- Concerns to examine: historical values come from reanalysis or model output, not station observations. Using observed or reanalysis weather as an input during evaluation is more favorable than the forecast weather available in real use. See the leakage rule in [methodology](../research/methodology.md).

### NASA Earthdata (satellite)

- URL: https://earthdata.nasa.gov/
- Expected content: aerosol optical depth and related products.
- Coverage, resolution, access: *to verify*.
- Concern: aerosol optical depth is not ground-level PM2.5. It may be useful as a complementary feature, not as a substitute target. Cloud cover causes gaps.

### Other sources

Other reputable sources (for example, government monitoring networks or other reanalysis products) will be investigated in Phase 1 and added here with the same template.

## Reproducible download

Download scripts will be added with the first ingestion code, writing to `data/raw/` with the retrieval date. Raw data is not committed.
