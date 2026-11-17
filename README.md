# AERON

Air pollution analysis and PM2.5 forecasting for Tashkent, Uzbekistan.

**Status:** early development. Phase 1 (research and feasibility) is complete apart from confirming the forecast target. Preliminary, exploratory experiments exist but are not final results.

- What data exists: one usable PM2.5 station for Tashkent (US Diplomatic Post via OpenAQ, 2018 to February 2025) plus complete ERA5 weather and 13 months of archived weather forecasts. See [data sources](docs/datasets/data_sources.md) and [data quality](docs/datasets/data_quality.md).
- What can be forecast: see the [feasibility report](docs/research/feasibility_report.md) and the [methodology](docs/research/methodology.md).
- Every number in the notes comes from code in `src/aeron/` and is labelled preliminary where the sample is small.

## Data sources

- [OpenAQ](https://openaq.org/): air-quality measurements
- [Open-Meteo](https://open-meteo.com/): weather data and archived forecasts
- [Mendeley Data](https://data.mendeley.com/datasets/nmpz7jds4f/2): a summer 2024 station dataset (CC BY 4.0)
- [Tashkent Open Data](https://opendata.tashkent.uz/): city stations (download currently fails)

## Getting the data

```
pip install -e ".[dev]"
cp .env.example .env             # add your free OpenAQ key
python scripts/download_data.py
python scripts/validate_data.py   # checks the raw files
python scripts/clean_data.py      # flags questionable PM2.5 readings
python scripts/build_dataset.py   # hourly and daily tables in data/processed/
```

Downloads are resumable. Settings are in `configs/sources.toml`. Raw data is written to `data/raw/` and is not committed. See [data sources](docs/datasets/data_sources.md).

## License

[MIT](LICENSE)
