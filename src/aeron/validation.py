"""Schema and sanity validation of the raw data files.

The checks read files in ``data/raw/`` and report problems. They never change
the data: cleaning and flagging rules are a separate step (task 2.2.2).

Levels
------
error  the file cannot be used as is (wrong columns, duplicate or unordered
       timestamps, values outside physical limits, too many missing values,
       a time grid that should be regular but is not)
warn   unusual but possible values or known quality issues worth flagging
info   facts reported for the record (counts of zeros, gaps)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd

from aeron.config import ROOT, load_config

RAW = ROOT / "data" / "raw"
TIME = "datetime_utc"


@dataclass(frozen=True)
class Column:
    """Expected properties of one value column."""

    low: float  # hard physical limit: values below are errors
    high: float  # hard physical limit: values above are errors
    max_missing: float = 0.0  # allowed share of empty cells
    warn_above: float | None = None  # unusual but possible: reported as a warning
    unit: str = ""


@dataclass(frozen=True)
class FileSpec:
    columns: dict[str, Column]
    regular_hourly: bool  # error if the time grid is not strictly hourly
    check_stuck: bool = False  # warn on long runs of identical values
    extra_columns: tuple[str, ...] = ()  # columns checked only for presence/order


@dataclass
class Issue:
    level: str  # "error" | "warn" | "info"
    code: str
    message: str
    count: int = 0


@dataclass
class Report:
    file: str
    rows: int = 0
    issues: list[Issue] = field(default_factory=list)

    def add(self, level: str, code: str, message: str, count: int = 0) -> None:
        self.issues.append(Issue(level, code, message, count))

    @property
    def status(self) -> str:
        levels = {i.level for i in self.issues}
        return "ERROR" if "error" in levels else "WARN" if "warn" in levels else "OK"


# --- Physical limits ---------------------------------------------------------
# Hard limits are generous bounds for Tashkent: a value outside them is an error.
PM25 = Column(0, 2000, max_missing=0.25, warn_above=500, unit="ug/m3")
HUMIDITY = Column(0, 100, unit="%")
TEMPERATURE = Column(-60, 60, unit="degrees C")

# Limits for every Open-Meteo variable used. The variable lists per file come from
# configs/sources.toml, so this table and the downloader cannot drift apart.
LIMITS = {
    "temperature_2m": Column(-60, 60, unit="degrees C"),
    "relative_humidity_2m": Column(0, 100, unit="%"),
    "dew_point_2m": Column(-80, 40, unit="degrees C"),
    "precipitation": Column(0, 200, unit="mm"),
    "surface_pressure": Column(500, 1100, unit="hPa"),
    "cloud_cover": Column(0, 100, unit="%"),
    "wind_speed_10m": Column(0, 250, unit="km/h"),
    "wind_direction_10m": Column(0, 360, unit="degrees"),
    "wind_gusts_10m": Column(0, 400, unit="km/h"),
    # Boundary layer height is missing for 2024-01-01 to 2024-06-30 (6.2% of hours).
    "boundary_layer_height": Column(0, 6000, max_missing=0.07, unit="m"),
    "shortwave_radiation": Column(0, 1500, unit="W/m2"),
    "vapour_pressure_deficit": Column(0, 20, unit="kPa"),
    "pressure_msl": Column(850, 1100, unit="hPa"),
    "snow_depth": Column(0, 5, unit="m"),
}
FORECAST_MISSING = 0.02  # archived forecasts have 0.4% to 0.9% empty cells


def weather_columns(names: list[str]) -> dict[str, Column]:
    return {name: LIMITS[name] for name in names}


def forecast_columns(cfg: dict) -> dict[str, Column]:
    fc = cfg["openmeteo"]["forecast"]
    cols = {}
    for n in fc["previous_days"]:
        for name in fc["variables"]:
            base = LIMITS[name]
            cols[f"{name}_previous_day{n}"] = Column(
                base.low, base.high, FORECAST_MISSING, base.warn_above, base.unit
            )
    return cols


def openaq_columns(value: Column) -> dict[str, Column]:
    return {
        "value": value,
        "percent_complete": Column(0, 100, unit="%"),
        "observed": Column(0, 1000),
        "expected": Column(1, 1000),
    }


def build_specs(cfg: dict | None = None) -> dict[str, FileSpec]:
    cfg = cfg or load_config()
    om = cfg["openmeteo"]
    return {
        "openaq/us_embassy_pm25_hourly.csv": FileSpec(
            openaq_columns(PM25), False, check_stuck=True
        ),
        "openaq/sputnik4_pm25_hourly.csv": FileSpec(
            openaq_columns(PM25), False, check_stuck=True
        ),
        "openaq/sputnik4_humidity_hourly.csv": FileSpec(
            openaq_columns(HUMIDITY), False
        ),
        "openaq/sputnik4_temperature_hourly.csv": FileSpec(
            openaq_columns(TEMPERATURE), False
        ),
        "openmeteo/era5_tashkent_hourly.csv": FileSpec(
            weather_columns(om["core_variables"]), True
        ),
        "openmeteo/era5_extra_tashkent_hourly.csv": FileSpec(
            weather_columns(om["extra_variables"]), True
        ),
        "openmeteo/forecast_previous_runs_hourly.csv": FileSpec(
            forecast_columns(cfg), True
        ),
    }


def check_columns(df: pd.DataFrame, spec: FileSpec, report: Report) -> bool:
    expected = [TIME, *spec.columns]
    if list(df.columns) != expected:
        missing = [c for c in expected if c not in df.columns]
        extra = [c for c in df.columns if c not in expected]
        report.add(
            "error",
            "columns",
            f"expected columns {expected}; missing {missing}, unexpected {extra}",
        )
        return False
    return True


def check_time(
    df: pd.DataFrame, spec: FileSpec, report: Report, today: datetime
) -> pd.Series | None:
    try:
        stamps = pd.to_datetime(df[TIME], format="%Y-%m-%dT%H:%M:%SZ", utc=True)
    except (ValueError, TypeError) as err:
        report.add(
            "error", "time_format", f"{TIME} is not ISO 8601 with a trailing Z: {err}"
        )
        return None
    dup = int(stamps.duplicated().sum())
    if dup:
        report.add("error", "duplicate_timestamps", "repeated timestamps", dup)
    unordered = int((stamps.diff().dropna() <= pd.Timedelta(0)).sum())
    if unordered:
        report.add(
            "error",
            "unordered_timestamps",
            "timestamps not strictly increasing",
            unordered,
        )
    off_hour = int(((stamps.dt.minute != 0) | (stamps.dt.second != 0)).sum())
    if off_hour:
        report.add("error", "off_hour", "timestamps not on the hour", off_hour)
    future = int((stamps > pd.Timestamp(today + timedelta(days=1))).sum())
    if future:
        report.add("error", "future_timestamps", "timestamps after tomorrow", future)
    steps = stamps.diff().dropna()
    irregular = int((steps != pd.Timedelta(hours=1)).sum())
    if irregular:
        longest = steps.max()
        level = "error" if spec.regular_hourly else "info"
        report.add(
            level,
            "gaps" if not spec.regular_hourly else "irregular_steps",
            f"time steps other than 1 h (longest {longest})",
            irregular,
        )
    return stamps


def check_values(df: pd.DataFrame, spec: FileSpec, report: Report) -> None:
    allowed_missing: dict[int, list[str]] = {}  # empty-cell count -> column names
    for name, col in spec.columns.items():
        numeric = pd.to_numeric(df[name], errors="coerce")
        bad_text = int(
            (
                numeric.isna()
                & df[name].notna()
                & (df[name].astype(str).str.strip() != "")
            ).sum()
        )
        if bad_text:
            report.add("error", "non_numeric", f"{name}: non-numeric entries", bad_text)
        n_missing = int(numeric.isna().sum())
        missing_share = n_missing / len(df) if len(df) else 0.0
        if missing_share > col.max_missing:
            report.add(
                "error",
                "missing",
                f"{name}: {missing_share:.1%} empty, allowed {col.max_missing:.1%}",
                n_missing,
            )
        elif n_missing:
            allowed_missing.setdefault(n_missing, []).append(name)
        out = int(((numeric < col.low) | (numeric > col.high)).sum())
        if out:
            report.add(
                "error",
                "range",
                f"{name}: outside [{col.low}, {col.high}] {col.unit}",
                out,
            )
        if col.warn_above is not None:
            high = int((numeric > col.warn_above).sum())
            if high:
                report.add(
                    "warn",
                    "high_values",
                    f"{name}: above {col.warn_above} {col.unit}",
                    high,
                )
        if name == "value":
            zeros = int((numeric == 0).sum())
            if zeros:
                report.add("info", "zeros", f"{name}: exactly zero", zeros)
    # Columns with the same number of empty cells are reported together.
    for n_missing, names in sorted(allowed_missing.items(), reverse=True):
        share = n_missing / len(df)
        label = (
            names[0] if len(names) == 1 else f"{len(names)} columns ({names[0]}, ...)"
        )
        suffix = " each" if len(names) > 1 else ""
        report.add("info", "missing", f"{label}: {share:.1%} empty{suffix}", n_missing)


def check_stuck(
    df: pd.DataFrame, stamps: pd.Series, report: Report, min_run: int = 24
) -> None:
    """Warn on runs of identical consecutive hourly readings."""
    valid = pd.DataFrame(
        {"t": stamps, "v": pd.to_numeric(df["value"], errors="coerce")}
    ).dropna()
    adjacent = valid["t"].diff() == pd.Timedelta(hours=1)
    same = (valid["v"].diff() == 0) & adjacent
    run_id = (~same).cumsum()
    longest = int(valid.groupby(run_id).size().max()) if len(valid) else 0
    if longest >= min_run:
        report.add(
            "warn", "stuck", f"{longest} identical consecutive hourly readings", longest
        )


def check_openaq_consistency(df: pd.DataFrame, report: Report) -> None:
    observed = pd.to_numeric(df["observed"], errors="coerce")
    expected = pd.to_numeric(df["expected"], errors="coerce")
    bad = int((observed > expected).sum())
    if bad:
        report.add("error", "coverage", "observed count exceeds expected count", bad)


def validate_file(path: Path, spec: FileSpec, today: datetime | None = None) -> Report:
    today = today or datetime.now(UTC)
    report = Report(file=path.name)
    if not path.exists():
        report.add("error", "missing_file", "file not found")
        return report
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    report.rows = len(df)
    if len(df) == 0:
        report.add("error", "empty", "no rows")
        return report
    if not check_columns(df, spec, report):
        return report
    stamps = check_time(df, spec, report, today)
    check_values(df, spec, report)
    if "observed" in df.columns:
        check_openaq_consistency(df, report)
    if spec.check_stuck and stamps is not None:
        check_stuck(df, stamps, report)
    return report


def validate_all(
    raw_dir: Path = RAW,
    specs: dict[str, FileSpec] | None = None,
    today: datetime | None = None,
) -> list[Report]:
    specs = specs or build_specs()
    reports = []
    for rel, spec in specs.items():
        report = validate_file(raw_dir / rel, spec, today)
        report.file = rel
        reports.append(report)
    return reports


def format_reports(reports: list[Report]) -> str:
    lines = []
    for r in reports:
        lines.append(f"{r.status:5s} {r.file} ({r.rows} rows)")
        for issue in r.issues:
            count = f" [{issue.count}]" if issue.count else ""
            lines.append(f"      {issue.level:5s} {issue.code}: {issue.message}{count}")
    return "\n".join(lines)
