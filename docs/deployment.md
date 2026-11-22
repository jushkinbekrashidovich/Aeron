# Deployment and operations

## Decision (task 7.1.1)

**No hosted deployment and no containers.** The project runs locally on a developer machine. Reasons:

- The service only replays 2024 to 2025 data from a series whose licence is not stated, so the data file cannot be published or shipped in a public image.
- Nothing needs a scheduled refresh: there is no live source (`docs/research/live_data_decision.md`).
- A public site that looks like an air quality service could be misread as a current forecast.
- Docker was planned but removed by the project owner on 2026-11-22: it would add nothing to a research project that is run locally, and the files could not be tested.

A hosted demo would need the data owner's permission and a host that can mount a private data folder. If that is ever wanted, packaging the API in a container is the usual route (the release `v0.1.0` still contains an untested Dockerfile). That is future work.

## Run locally

```
python scripts/train_final.py --cutoff 2024-01-19 --tag replay
uvicorn aeron.api.app:create_app --factory --port 8000
cd frontend && npm run dev
```

## Configuration and secrets

| Variable | Used by | Default |
|---|---|---|
| `AERON_DAILY_CSV` | API | `data/processed/daily_us_embassy.csv` |
| `AERON_MODEL_DIR` | API | newest folder with `replay` in its name under the models root |
| `AERON_MODELS_ROOT` | API | `artifacts/models` |
| `AERON_CORS_ORIGINS` | API | `http://localhost:3000` (comma-separated) |
| `NEXT_PUBLIC_API_URL` | web app | `http://localhost:8000` |
| `OPENAQ_API_KEY` | download script only | in untracked `.env` (see `.env.example`) |

The service itself needs no secret. `.env`, data, `mlruns/` and `artifacts/` are never committed.

## Health checks

`GET /health` returns `ok` when data and model are loaded and `degraded` with a list of problems otherwise. In `degraded` state the forecast and history endpoints answer 503 with the same list.

## Update and roll back

1. Train: `python scripts/train_final.py --cutoff 2024-01-19 --tag replay`. Each run writes a new folder `artifacts/models/<date>-replay-<data checksum>/` and never overwrites an older one.
2. The API picks the newest replay folder. To pin a version, set `AERON_MODEL_DIR` to that folder and restart.
3. **Roll back** by setting `AERON_MODEL_DIR` to the previous folder (or deleting the newest folder) and restarting the API. Each folder holds its own `model_card.json` with the code commit, data checksum, training period and known limits.
4. For code, check out a git tag or commit.
5. Check `/health` and `/api/v1/model` (the model version) after any change.

## Monitoring

Not set up. With a replay service on a fixed dataset there is no drift to monitor. A live service would need input checks (missing PM2.5), coverage tracking of the intervals and a retraining schedule.
