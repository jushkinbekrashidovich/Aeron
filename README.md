# About
AERON is a machine learning project that forecasts the daily mean PM2.5 concentration in Tashkent, Uzbekistan. 24h, 48h and 72h ahead. 
The project is planned to build in three stages (versions)
### Stage 1 (completed). 
I built a forecasting model using hourly PM2.5 data from the US Embassy station, from November 2018 to 25. February 2025, together with weather data. The model was tested season by season, from November 2020 to February 2025. The most realistic test used the weather forecasts that were available at the time, from January 2024 to February 2025. The model's predictions were compared with the measured PM2.5 values and with simple reference forecasts.

### Stage 2 (planned) 
I will include industrial construction in the hypothesis tests and extend the model with this information,
  to show how industrial development in Tashkent is related to PM2.5 levels.
### Stage 3 (planned) 
I will collect current PM2.5 data from the Tashkent opendata and adapt the model to forecast air quality in real time.

## Stage 1 ( data from November 2020 to February 2025 )
- Forecasts the **daily mean PM2.5** (local day, UTC+5) at one station, the US Diplomatic Post (OpenAQ location 8881), at 1, 2 and 3 days ahead, issued at the end of each day.
- Gives a 90% and 80% **prediction range** (conformal intervals) and the **probability** (conformal, better calibrated than Platt scaling with real forecasts) that the daily mean reaches 55.5 µg/m³ (the start of the EPA "Unhealthy" category) or 35.5.
- Serves historical **replays** through an API and a web app: pick a past day, see what the model would have predicted using only information available then, and what was measured.

## Main results

Average absolute error in µg/m³ on **winter** days, tested on real archived weather forecasts (about 140 days from two winters, so differences of 1 to 2 µg/m³ are within noise). Details: [model comparison](reports/model_evaluation/comparison.md).

| Model | 1 day | 2 days | 3 days |
|---|---|---|---|
| Tomorrow equals today | 24.1 | 32.4 | 35.1 |
| Typical value for the time of year | 25.9 | 25.7 | 25.8 |
| Ridge regression with forecast weather | 18.2 | 22.4 | 23.6 |
| **LightGBM with forecast weather** (chosen) | **17.1** | **20.9** | **22.0** |

- Weather inputs matter more than the choice of model. Ridge, random forest, XGBoost and LightGBM are within about 1 to 2 µg/m³ of each other.
- The 90% range held for 80% to 86% of winter days with perfect-forecast weather and 87% to 93% with real forecasts. Misses come in runs of days. See [uncertainty](reports/model_evaluation/uncertainty.md).
- The highest days (daily mean at or above 100 µg/m³) are underpredicted by 24 to 59 µg/m³ on average, although the alert level is usually reached. See [error analysis](reports/model_evaluation/error_analysis.md).
- What the model uses, and how stable that is across winters: [explainability](reports/model_evaluation/explainability.md). These are associations, not causes.

## Limits in one paragraph

One station, five winters of testing, real weather forecasts for only 13 months, a data series that ends in February 2025, and wide prediction ranges (60 to 130 µg/m³ in winter). No spatial claims, no hourly forecasts, no live data. Full list: [limitations](docs/research/limitations.md).

## Repository map

| Path | Contents |
|---|---|
| `src/aeron/` | Ingestion, cleaning, features, evaluation framework, models, uncertainty, explanations, packaging, API |
| `notebooks/` | 01 to 09, executed with outputs (data, EDA, statistics, features, baselines, model comparison, error analysis, explainability, uncertainty) |
| `reports/model_evaluation/` | Written reports and result tables |
| `docs/research/` | Methodology, research questions, hypotheses, feasibility report, limitations, decisions |
| `docs/` | [Architecture](docs/architecture.md), [deployment and operations](docs/deployment.md), dataset documentation |
| `frontend/` | Next.js web app (Dashboard, Forecast, Research) |
| `scripts/` | Data pipeline and `train_final.py` |

## Getting started

Python 3.11 or newer. On macOS, XGBoost and LightGBM need `brew install libomp`.

```
pip install -e ".[dev,tracking,trees,api,notebooks]"
cp .env.example .env              # add your free OpenAQ key
python scripts/download_data.py
python scripts/validate_data.py   # checks the raw files
python scripts/clean_data.py      # flags questionable PM2.5 readings
python scripts/build_dataset.py   # hourly and daily tables in data/processed/
```

Downloads are resumable. Settings are in `configs/sources.toml`. Raw and processed data are not committed: the licence of the US series is not stated. Because of this, the notebooks cannot be re-run from a clone without downloading the data, and the outputs saved in them are the reference results.

Run the checks:

```
ruff check . && ruff format --check . && pytest
cd frontend && npm install && npm test && npm run lint && npm run build
```

### Train and serve the replay

```
python scripts/train_final.py --cutoff 2024-01-19 --tag replay   # replay model (out-of-sample for the replayed days)
python scripts/train_final.py                                    # production model on all data
uvicorn aeron.api.app:create_app --factory --port 8000           # API, docs at /docs
cd frontend && npm run dev                                       # web app at http://localhost:3000
```

There is no Docker setup: the project is a research study that runs locally (see [deployment](docs/deployment.md)). Step-by-step browser check: [manual checks](docs/manual_checks.md).

## Data sources

- [OpenAQ](https://openaq.org/): air-quality measurements
- [Open-Meteo](https://open-meteo.com/): ERA5 weather and archived forecasts
- [Mendeley Data](https://data.mendeley.com/datasets/nmpz7jds4f/2): a summer 2024 station dataset (CC BY 4.0), used only for a cross-check
- [Tashkent Open Data](https://opendata.tashkent.uz/): city stations (download currently fails)

See [data sources](docs/datasets/data_sources.md) and [data quality](docs/datasets/data_quality.md).

## Not a health service

This is research code. Currently it is not an air quality warning system and not health advice.

## Cite

See [CITATION.cff](CITATION.cff).

## License

[MIT](LICENSE)
