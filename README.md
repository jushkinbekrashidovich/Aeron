# AERON

**Understand tomorrow's air, today.**

AERON is an open research project on urban air pollution in Tashkent, Uzbekistan. It studies historical PM2.5 and weather data, tests forecasting models, and explains what drives the predictions. A web application will present the results once the research supports it.

> **Status: early development (Phase 1, research and feasibility).**
> No data has been collected, no model has been trained, and no application exists yet. Nothing in this repository reports results until they are produced by code committed here.

## Problem statement

Several platforms show current air-quality readings for Tashkent. A current reading does not say how pollution is likely to change, which conditions accompany high pollution, or how reliable a forecast is. AERON investigates whether short-term PM2.5 forecasting is feasible with the data that actually exists for the city, and how well. See [docs/research/problem_statement.md](docs/research/problem_statement.md).

## Research objectives

1. Establish what air-quality and weather data exist for Tashkent, and their coverage and quality.
2. Characterize seasonal, daily and weather-related PM2.5 patterns with statistical analysis.
3. Forecast PM2.5 at 24, 48 and 72 hour horizons, where the data supports them, and compare against simple baselines.
4. Evaluate models chronologically, including during high-pollution episodes.
5. Explain model behavior (for example with SHAP) without claiming causality.

The full list is in [docs/research/research_questions.md](docs/research/research_questions.md).

## Capabilities

| Capability | Status |
|---|---|
| Dataset feasibility assessment | Planned (Phase 1) |
| Data ingestion and validation pipeline | Planned |
| Exploratory and statistical analysis | Planned |
| Baseline and ML forecasting models | Planned |
| Explainability and error analysis | Planned |
| Prediction API (FastAPI) | Planned |
| Web application (Next.js) | Planned |

Nothing is implemented yet.

## Technology stack

Tools are added when they are needed, not in advance.

- **Research and ML:** Python, pandas, NumPy, SciPy, scikit-learn, XGBoost, LightGBM, SHAP, PyTorch (only if justified by the results).
- **Data engineering:** PostgreSQL with PostGIS, Python ingestion scripts; Airflow only if scheduling requires it.
- **Experiment tracking:** MLflow.
- **Backend:** FastAPI, Pydantic, SQLAlchemy.
- **Frontend:** Next.js, TypeScript, Tailwind CSS, Plotly, a map library.
- **Infrastructure:** Docker, GitHub Actions.

## Repository structure

```text
aeron/
├── docs/            Research, dataset and architecture documentation
├── data/            Local data (raw/interim/processed are git-ignored); samples/ holds small shareable files
├── research/        Exploratory notebooks, numbered in research order
├── src/aeron/       Reusable, tested Python package (pipelines, features, models, evaluation)
├── experiments/     Experiment configs and run records
├── models/          Model artifacts (git-ignored; see models/README.md)
├── reports/         Generated figures and written analysis
├── frontend/        Web application (not started)
└── backend/, tests/, scripts/, configs/, docker/, .github/   Added when first needed
```

Notebooks explore; code that is reused moves into `src/aeron/`. The backend will import from `src/aeron/` and not duplicate it.

## Data sources

Candidate sources, not yet assessed. See [docs/datasets/data_sources.md](docs/datasets/data_sources.md).

- [OpenAQ](https://openaq.org/): ground-level air-quality measurements.
- [Open-Meteo](https://open-meteo.com/): historical and forecast weather.
- [NASA Earthdata](https://earthdata.nasa.gov/): satellite aerosol products (a complement to ground data, not a substitute).

Raw data is never committed. Download instructions will be added with the first ingestion script.

## Research methodology

```mermaid
flowchart LR
    A[Data feasibility] --> B[Collection and cleaning]
    B --> C[EDA and statistics]
    C --> D[Baselines]
    D --> E[ML models]
    E --> F[Chronological evaluation]
    F --> G[Explainability and error analysis]
    G --> H[Documentation and application]
```

Baselines come before complex models, splits are chronological, and features may only use information available at forecast time. Details: [docs/research/methodology.md](docs/research/methodology.md).

## Roadmap

| Phase | Focus |
|---|---|
| 1 | Research and dataset feasibility |
| 2 | Data collection and EDA |
| 3 | Baselines and ML experiments |
| 4 | Explainability and error analysis |
| 5 | Backend and deployment |
| 6 | Frontend |
| 7 | Final documentation |

See [docs/development/roadmap.md](docs/development/roadmap.md).

## Installation

There is nothing to run yet. To set up a local environment:

```bash
git clone https://github.com/jushkinbekrashidovich/aeron.git
cd aeron
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Python 3.11 or newer is required. Dependencies will be added to `requirements.txt` and `pyproject.toml` as code is written.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE). Data from third-party sources keeps its own license; see the data documentation.
