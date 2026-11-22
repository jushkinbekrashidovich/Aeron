# Live data and storage: decision (task 5.2)

Decided by the project owner on 2026-11-21: **option A, historical replay.**

## Problem

The model needs yesterday's PM2.5 daily mean as an input. The US Diplomatic Post series ends on 2025-02-25, so no current forecast can be made from it.

## Options considered

| Option | Verdict |
|---|---|
| A. Historical replay: the service answers "what would the model have forecast on origin day X", for days in 2024-01 to 2025-02, using stored PM2.5, observed weather and the archived forecasts that existed then | **Chosen.** Stays inside what was tested. |
| B. Live OpenAQ from another Tashkent sensor (for example Sputnik-4, about 3,277 hours from 2025-09) | Not done. The model was trained on a reference-grade monitor, a low-cost sensor read about 40% as high in the one overlap checked, and four months of data cannot validate or recalibrate it. Future work. |
| C. City open-data portal | Not possible: the download returns HTTP 500. |

## How replay stays honest

- A separate **replay model** is trained only on targets up to 2024-01-19, the day before archived forecasts begin. Every replayed origin day (2024-01-20 to 2025-02-22) is therefore out-of-sample for it, and the weather input is the real archived forecast, as in the "real forecast" test view. The production model, trained on all data to 2025-02-25, is not used for replay because it has seen those days.
- The replay model is one fixed model applied for 13 months. In the evaluation, models were refitted at the start of every season, so replay numbers can differ slightly from the walk-forward numbers.
- Every API response and every page says that it is a replay of historical data, shows the observed value that followed, and never presents a replayed forecast as current.
- Replay runs only for origin days whose three target days all have observed PM2.5 (so the forecast can be compared with what happened).

## Storage

Files only. One station and a few thousand daily rows do not justify PostgreSQL or PostGIS. The service reads `data/processed/daily_us_embassy.csv` (not committed, licence of the series not stated) from a path set by an environment variable and the model artifacts from `artifacts/models/`. Without the data file the service starts but answers forecast requests with an explicit error.

## Scheduled refresh

Not needed: replay has nothing to refresh. A scheduler (cron or GitHub Actions) becomes relevant only with a live source (option B or C).

## Check of the replay model (2026-11-22)

Running the API over all 340 replayable origin days (2024-01-21 to 2025-02-22) with the replay model (trained to 2024-01-19 only), 137 of them in winter:

| Lead | Winter MAE, replay model | Winter MAE, persistence | Winter MAE in the walk-forward evaluation (real forecasts) | Winter coverage of the 90% interval |
|---|---|---|---|---|
| 1 day | 17.5 | 24.4 | 17.1 | 85% |
| 2 days | 21.7 | 32.8 | 20.9 | 84% |
| 3 days | 21.2 | 35.7 | 22.0 | 85% |

Over all 340 days the 90% interval covered 78% to 79% of observations (all seasons). The numbers are in line with the evaluation, which is expected because the days and weather inputs are the same, only the model refits differ.
