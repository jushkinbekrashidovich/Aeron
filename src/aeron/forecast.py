"""Final model packaging and inference (task 5.1).

``train_final`` fits the headline model for one lead on every row that has a target,
with the same calibration scheme as ``aeron.uncertainty``. ``save`` and ``load`` store the
fitted models and a model card. ``ForecastService.forecast`` is a pure function of the
recent daily table: it returns the forecast, intervals and exceedance probabilities for
the target day of every available lead, and a list of problems with the input.

Artifacts are written with joblib, so only load files that this project produced.

The daily table passed to ``forecast`` has the layout of ``data/processed/daily_*.csv``:
an index of local dates, ``pm25_*`` columns up to the origin day, observed weather
(``era5_*``) up to the origin day, and the archived weather forecast
(``fc_lead{k}_*``) on the target days up to origin + 3.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from aeron.evaluation.splits import train_validation_split
from aeron.features import build_features, observed_as_forecast
from aeron.models import trees
from aeron.models.baselines import Context
from aeron.uncertainty import CALIBRATION_DAYS, MIN_FIT_DAYS, IntervalCalibrator

LEADS = (1, 2, 3)
MODEL_NAME = "lgbm_forecast_weather"
FEATURE_SET = "forecast"
ALERT_LEVEL = 55.5  # ug/m3, daily mean
SECONDARY_LEVEL = 35.5


def headline_model() -> trees.TreeModel:
    """The headline model chosen in task 3.4.5 (LightGBM on the forecast feature set)."""
    return trees.lightgbm_model(FEATURE_SET, MODEL_NAME)


@dataclass
class LeadModel:
    lead: int
    model: trees.TreeModel
    calibrator: IntervalCalibrator
    last_target_date: pd.Timestamp
    n_train: int
    n_calibration: int


def train_final(
    daily: pd.DataFrame,
    lead: int,
    make_model=headline_model,
    cutoff: str | pd.Timestamp | None = None,
) -> LeadModel:
    """Fit the model and the interval calibrator for one lead on rows with a target.

    With ``cutoff`` only rows whose target day is on or before it are used. A replay of
    later days is then out-of-sample for this model.
    """
    table = build_features(daily, lead)
    rows = table[table["y"].notna() & table["y_origin"].notna()]
    if cutoff is not None:
        rows = rows[rows["target_date"] <= pd.Timestamp(cutoff)]
    rows = rows.reset_index(drop=True)
    series = daily["pm25_mean"].copy()
    series.index = pd.DatetimeIndex(series.index)
    last_target = pd.Timestamp(rows["target_date"].max())
    context = Context(
        lead=lead, test_start=last_target + pd.Timedelta(days=1), daily_mean=series
    )
    fit_idx, cal_idx = train_validation_split(
        rows["target_date"], CALIBRATION_DAYS, lead
    )
    if len(fit_idx) < MIN_FIT_DAYS:
        raise ValueError("not enough history to fit and calibrate the model")
    calibration_model = make_model().fit(rows.iloc[fit_idx], context)
    cal_rows = observed_as_forecast(rows.iloc[cal_idx])
    calibrator = IntervalCalibrator().fit(
        calibration_model.predict(cal_rows, context), cal_rows["y"]
    )
    model = make_model().fit(rows, context)
    return LeadModel(lead, model, calibrator, last_target, len(rows), len(cal_idx))


def _sha256(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:12] if path.exists() else None


def _git(root: Path, *args: str) -> str | None:
    try:
        out = subprocess.run(
            ["git", *args], cwd=root, capture_output=True, text=True, check=True
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return out.stdout.strip()


def version_id(daily_path: Path | None, tag: str = "") -> str:
    """Version string from the build date, an optional tag and the data checksum."""
    checksum = (_sha256(daily_path) if daily_path else None) or "nodata"
    middle = f"-{tag}" if tag else ""
    return f"{datetime.now(UTC):%Y%m%d}{middle}-{checksum}"


def model_card(
    models: dict[int, LeadModel], version: str, root: Path, daily_path, cutoff=None
) -> dict:
    first = next(iter(models.values()))
    commit = _git(root, "rev-parse", "--short", "HEAD")
    dirty = _git(root, "status", "--porcelain", "--untracked-files=no")
    return {
        "version": version,
        "model": MODEL_NAME,
        "feature_set": FEATURE_SET,
        "target": "daily mean PM2.5 (ug/m3) of the local day (Asia/Tashkent), issued at the end of the origin day",
        "leads_days": sorted(models),
        "alert_levels": {"primary": ALERT_LEVEL, "secondary": SECONDARY_LEVEL},
        "built_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "git_commit": commit or "unknown",
        "git_dirty": "unknown" if dirty is None else bool(dirty),
        "data_daily_sha256": _sha256(daily_path) if daily_path else None,
        "last_training_target_date": str(first.last_target_date.date()),
        "training_cutoff": None if cutoff is None else str(pd.Timestamp(cutoff).date()),
        "per_lead": {
            str(lead): {
                "training_rows": m.n_train,
                "calibration_rows": m.n_calibration,
                "chosen_settings": m.model.chosen,
                "n_inputs": len(m.model._columns),
                "interval_quantiles": {
                    str(level): {k: [round(x, 4) for x in v] for k, v in q.items()}
                    for level, q in m.calibrator.quantiles.items()
                },
            }
            for lead, m in models.items()
        },
        "known_limits": [
            "One station (US Diplomatic Post). The training series ends on 2025-02-25.",
            "Winter coverage of the 90% interval was 80-86% with perfect-forecast weather and 87-93% with real forecasts in testing; March to October 2024 coverage was 74%.",
            "Days at or above 100 ug/m3 are underpredicted by 24 to 59 ug/m3 on average.",
            "Probabilities from real forecasts: prefer the conformal probability over the Platt one.",
            "Associations learned from one station's data; no causal reading.",
        ],
    }


def save(
    models: dict[int, LeadModel],
    directory: Path,
    root: Path,
    daily_path: Path | None = None,
    evaluation: dict | None = None,
    tag: str = "",
    cutoff=None,
) -> Path:
    """Write models and the model card under ``directory/<version>/`` and return that path."""
    version = version_id(daily_path, tag)
    target = directory / version
    target.mkdir(parents=True, exist_ok=True)
    for lead, m in models.items():
        joblib.dump(m, target / f"lead{lead}.joblib", compress=3)
    card = model_card(models, version, root, daily_path, cutoff)
    if evaluation:
        card["evaluation"] = evaluation
    (target / "model_card.json").write_text(json.dumps(card, indent=2, default=str))
    return target


def known_at(daily: pd.DataFrame, origin) -> pd.DataFrame:
    """The daily table as it was known at the end of ``origin``.

    PM2.5 and observed weather after the origin are removed. The archived weather
    forecasts (``fc_lead*`` columns) on the target days, up to three days later, are kept
    because they were issued before the origin.
    """
    origin = pd.Timestamp(origin).normalize()
    out = daily.copy()
    out.index = pd.DatetimeIndex(out.index)
    out = out.loc[: origin + pd.Timedelta(days=max(LEADS))].copy()
    after = out.index > origin
    for column in out.columns:
        if not column.startswith("fc_lead"):
            out.loc[after, column] = np.nan
    return out


class ForecastService:
    """Loaded models, ready to forecast."""

    def __init__(self, models: dict[int, LeadModel], card: dict) -> None:
        self.models = models
        self.card = card

    @classmethod
    def load(cls, path: Path) -> ForecastService:
        card = json.loads((path / "model_card.json").read_text())
        models = {
            int(lead): joblib.load(path / f"lead{lead}.joblib")
            for lead in card["leads_days"]
        }
        return cls(models, card)

    def forecast(self, daily: pd.DataFrame, origin: date | str | pd.Timestamp) -> dict:
        """Forecasts issued at the end of ``origin`` for every lead whose input is available."""
        origin = pd.Timestamp(origin).normalize()
        daily = daily.copy()
        daily.index = pd.DatetimeIndex(daily.index)
        problems = []
        if origin not in daily.index or pd.isna(daily.loc[origin, "pm25_mean"]):
            problems.append(f"no PM2.5 daily mean for the origin day {origin.date()}")
        result = {}
        for lead, m in sorted(self.models.items()):
            target = origin + pd.Timedelta(days=lead)
            if target not in daily.index:
                problems.append(
                    f"no row for the target day {target.date()} (lead {lead})"
                )
                continue
            table = build_features(daily, lead)
            row = table[table["origin_date"] == origin]
            if row.empty:
                continue
            columns = m.model._columns
            missing = [c for c in columns if row[c].isna().any()]
            share = len(missing) / max(len(columns), 1)
            series = daily["pm25_mean"]
            context = Context(lead=lead, test_start=origin, daily_mean=series)
            point = float(m.model.predict(row, context)[0])
            intervals = m.calibrator.intervals([point]).iloc[0]
            probs = m.calibrator.probabilities([point]).iloc[0]
            result[lead] = {
                "target_date": str(target.date()),
                "forecast": round(point, 1),
                "interval_90": [
                    round(float(intervals["lo90_scaled"]), 1),
                    round(float(intervals["hi90_scaled"]), 1),
                ],
                "interval_80": [
                    round(float(intervals["lo80_scaled"]), 1),
                    round(float(intervals["hi80_scaled"]), 1),
                ],
                "probability_at_least_55_5": {
                    "conformal": round(float(probs["p55.5_conformal"]), 3),
                    "platt": round(float(probs["p55.5_platt"]), 3),
                },
                "probability_at_least_35_5": {
                    "conformal": round(float(probs["p35.5_conformal"]), 3),
                    "platt": round(float(probs["p35.5_platt"]), 3),
                },
                "missing_inputs": missing,
                "missing_input_share": round(share, 3),
            }
            if share > 0.25:
                problems.append(
                    f"lead {lead}: {len(missing)} of {len(columns)} inputs are missing and were filled with training medians"
                )
        return {
            "origin_date": str(origin.date()),
            "model_version": self.card["version"],
            "forecasts": result,
            "problems": problems,
        }
