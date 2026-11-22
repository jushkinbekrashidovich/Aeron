"""Response models of the API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

NOTICE = (
    "Replay of historical data. This is what the model would have forecast on the origin "
    "day, using only information available then. It is not a current forecast."
)


class Probabilities(BaseModel):
    conformal: float = Field(
        ge=0,
        le=1,
        description="Recommended. Share of calibration errors that would reach the level; "
        "better calibrated than Platt when the input is a real weather forecast.",
    )
    platt: float = Field(
        ge=0,
        le=1,
        description="Platt-scaled logistic probability. Kept for comparison; overconfident with real forecasts.",
    )


class LeadForecast(BaseModel):
    lead_days: int
    target_date: str
    forecast: float = Field(description="Daily mean PM2.5, ug/m3")
    interval_80: tuple[float, float]
    interval_90: tuple[float, float]
    probability_at_least_55_5: Probabilities
    probability_at_least_35_5: Probabilities
    persistence: float | None = Field(
        description="Baseline: the daily mean of the origin day, ug/m3"
    )
    observed: float | None = Field(
        description="What happened on the target day (None if missing), ug/m3"
    )
    observed_inside_90: bool | None
    missing_input_share: float


class ForecastResponse(BaseModel):
    mode: Literal["replay"] = "replay"
    notice: str = NOTICE
    origin_date: str
    model_version: str
    forecasts: list[LeadForecast]
    problems: list[str]


class ReplayRange(BaseModel):
    mode: Literal["replay"] = "replay"
    notice: str = NOTICE
    first_origin: str
    last_origin: str
    origins: int


class HistoryPoint(BaseModel):
    date: str
    pm25_mean: float | None


class HistoryResponse(BaseModel):
    unit: str = "ug/m3"
    start: str
    end: str
    points: list[HistoryPoint]


class Station(BaseModel):
    name: str
    provider: str
    openaq_location_id: int
    openaq_sensor_id: int
    parameter: str
    quality: str
    local_time_zone: str
    series_first_valid: str
    series_last_valid: str
    note: str


class Health(BaseModel):
    status: Literal["ok", "degraded"]
    data_loaded: bool
    model_loaded: bool
    detail: list[str]
