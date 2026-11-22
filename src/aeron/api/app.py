"""FastAPI application: replays what the model would have forecast on past days."""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from datetime import date
from typing import Annotated

import pandas as pd
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware

from aeron.api import schemas
from aeron.api.settings import Settings
from aeron.forecast import LEADS, ForecastService, known_at

MAX_HISTORY_DAYS = 800


class State:
    """Data and model loaded at start-up. Missing pieces are reported, not hidden."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.daily: pd.DataFrame | None = None
        self.service: ForecastService | None = None
        self.problems: list[str] = []
        self.first_origin: pd.Timestamp | None = None
        self.last_origin: pd.Timestamp | None = None
        self._load()

    def _load(self) -> None:
        path = self.settings.daily_csv
        if path.exists():
            self.daily = pd.read_csv(path, index_col=0, parse_dates=True)
            self.daily.index = pd.DatetimeIndex(self.daily.index)
        else:
            self.problems.append(f"daily data file not found: {path}")
        model_dir = self.settings.resolve_model_dir()
        if model_dir is not None and (model_dir / "model_card.json").exists():
            self.service = ForecastService.load(model_dir)
        else:
            self.problems.append("no trained model found (run scripts/train_final.py)")
        if self.daily is not None and self.service is not None:
            self._replay_range()

    def _replay_range(self) -> None:
        """Origin days after the training cutoff whose three target days have an observed mean."""
        card = self.service.card
        cutoff = card.get("training_cutoff")
        pm = self.daily["pm25_mean"]
        first_forecast = (
            self.daily.filter(like="fc_lead1_").dropna(how="all").index.min()
        )
        start = (
            pd.Timestamp(cutoff) + pd.Timedelta(days=1) if cutoff else first_forecast
        )
        start = max(start, first_forecast)
        ok = (
            pm.notna()
            & pm.shift(-1).notna()
            & pm.shift(-2).notna()
            & pm.shift(-3).notna()
        )
        days = [d for d in pm.index[ok] if d >= start]
        if days:
            self.first_origin, self.last_origin = days[0], days[-1]
            self._origins = set(days)
        else:
            self.problems.append("no replayable origin days")

    def require_ready(self) -> None:
        if self.daily is None or self.service is None or self.first_origin is None:
            raise HTTPException(
                status_code=503,
                detail={"error": "service not ready", "problems": self.problems},
            )


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.aeron = State(settings)
        yield

    app = FastAPI(
        title="AERON replay API",
        version="0.1.0",
        description=(
            "PM2.5 forecasts for Tashkent (US Diplomatic Post station), 1 to 3 days ahead, with "
            "prediction intervals and exceedance probabilities. **Replay mode only:** every forecast "
            "is a historical one, made with information available on its origin day. The PM2.5 series "
            "ends on 2025-02-25, so no current forecast is possible."
        ),
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_methods=["GET"],
        allow_headers=[],
    )

    def state(request: Request) -> State:
        return request.app.state.aeron

    @app.get("/health", response_model=schemas.Health, tags=["service"])
    def health(request: Request):
        st = state(request)
        ready = st.daily is not None and st.service is not None
        return schemas.Health(
            status="ok" if ready else "degraded",
            data_loaded=st.daily is not None,
            model_loaded=st.service is not None,
            detail=st.problems,
        )

    @app.get("/api/v1/station", response_model=schemas.Station, tags=["data"])
    def station():
        return schemas.Station(
            name="US Diplomatic Post, Tashkent",
            provider="OpenAQ",
            openaq_location_id=8881,
            openaq_sensor_id=25916,
            parameter="PM2.5, hourly, daily mean over the local day (UTC+5)",
            quality="reference-grade monitor",
            local_time_zone="Asia/Tashkent",
            series_first_valid="2018-11-27",
            series_last_valid="2025-02-25",
            note="The only station with a multi-year series. Nothing here describes other parts of the city.",
        )

    @app.get(
        "/api/v1/replay/range", response_model=schemas.ReplayRange, tags=["forecast"]
    )
    def replay_range(request: Request):
        st = state(request)
        st.require_ready()
        return schemas.ReplayRange(
            first_origin=str(st.first_origin.date()),
            last_origin=str(st.last_origin.date()),
            origins=len(st._origins),
        )

    @app.get(
        "/api/v1/forecast", response_model=schemas.ForecastResponse, tags=["forecast"]
    )
    def forecast(
        request: Request,
        origin: Annotated[
            date,
            Query(
                description="Origin day (YYYY-MM-DD), the day the forecast is issued"
            ),
        ],
    ):
        st = state(request)
        st.require_ready()
        day = pd.Timestamp(origin)
        if day not in st._origins:
            raise HTTPException(
                status_code=404,
                detail={
                    "error": "origin day is not available for replay",
                    "first_origin": str(st.first_origin.date()),
                    "last_origin": str(st.last_origin.date()),
                },
            )
        result = st.service.forecast(known_at(st.daily, day), day)
        pm = st.daily["pm25_mean"]
        origin_value = pm.get(day)
        items = []
        for lead in LEADS:
            f = result["forecasts"].get(lead)
            if f is None:
                continue
            target = pd.Timestamp(f["target_date"])
            observed = pm.get(target)
            observed = None if pd.isna(observed) else round(float(observed), 1)
            lo, hi = f["interval_90"]
            items.append(
                schemas.LeadForecast(
                    lead_days=lead,
                    target_date=f["target_date"],
                    forecast=f["forecast"],
                    interval_80=tuple(f["interval_80"]),
                    interval_90=(lo, hi),
                    probability_at_least_55_5=f["probability_at_least_55_5"],
                    probability_at_least_35_5=f["probability_at_least_35_5"],
                    persistence=None
                    if pd.isna(origin_value)
                    else round(float(origin_value), 1),
                    observed=observed,
                    observed_inside_90=None
                    if observed is None
                    else lo <= observed <= hi,
                    missing_input_share=f["missing_input_share"],
                )
            )
        return schemas.ForecastResponse(
            origin_date=result["origin_date"],
            model_version=result["model_version"],
            forecasts=items,
            problems=result["problems"],
        )

    @app.get("/api/v1/history", response_model=schemas.HistoryResponse, tags=["data"])
    def history(
        request: Request,
        start: Annotated[date, Query(description="First day (YYYY-MM-DD)")],
        end: Annotated[date, Query(description="Last day (YYYY-MM-DD)")],
    ):
        st = state(request)
        if st.daily is None:
            raise HTTPException(
                503, detail={"error": "service not ready", "problems": st.problems}
            )
        if end < start:
            raise HTTPException(422, detail="end must not be before start")
        if (end - start).days + 1 > MAX_HISTORY_DAYS:
            raise HTTPException(
                422, detail=f"at most {MAX_HISTORY_DAYS} days per request"
            )
        days = pd.date_range(start, end, freq="D")
        series = st.daily["pm25_mean"].reindex(days)
        return schemas.HistoryResponse(
            start=str(start),
            end=str(end),
            points=[
                schemas.HistoryPoint(
                    date=str(d.date()),
                    pm25_mean=None if pd.isna(v) else round(float(v), 1),
                )
                for d, v in series.items()
            ],
        )

    @app.get("/api/v1/model", tags=["model"])
    def model_info(request: Request):
        st = state(request)
        if st.service is None:
            raise HTTPException(
                503, detail={"error": "no model", "problems": st.problems}
            )
        card = json.loads(json.dumps(st.service.card, default=str))
        return card

    return app
