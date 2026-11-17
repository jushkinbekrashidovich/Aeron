"""Flagging rules for hourly PM2.5 series.

Rules flag first. A value is replaced by missing in ``value_clean`` only when the
reading is physically impossible or is an isolated spike that no neighbouring
reading supports. The raw value is always kept next to the clean one. Zeros are
flagged but kept, because a reference monitor that reports whole numbers can
show 0 in clean air.

Time convention: OpenAQ labels each hourly value with the start of the hour in
UTC, and nothing is shifted. Against ERA5 at the Sputnik-4 sensor the best match
is at lag 0 for both temperature and humidity (interpolated offsets +0.15 h and
-0.24 h), so the OpenAQ and Open-Meteo labels are aligned without a shift (see
notebook 02, section 6).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

from aeron.config import ROOT, load_config, openaq_series

INTERIM = ROOT / "data" / "interim" / "openaq"

PM25_MAX = 2000.0  # ug/m3, above this a reading is not physical for ambient air
SPIKE_MIN = 300.0  # only readings at or above this can be flagged as spikes
SPIKE_EXTREME_MIN = 800.0  # flagged spikes at or above this are set to missing
SPIKE_RATIO = 8.0  # spike: at least this many times the typical value on both sides
SPIKE_MAX_RUN = 2  # longest run of consecutive hours that can be a spike
SPIKE_WINDOW = 4  # hours looked at on each side
SPIKE_MIN_NEIGHBOURS = 2  # valid readings needed on each side
STUCK_MIN_RUN = 24  # identical consecutive hourly readings


@dataclass(frozen=True)
class Rule:
    id: str
    name: str
    description: str
    action: str  # what happens to value_clean


RULES = [
    Rule(
        "missing",
        "Missing value",
        "No value for the hour (empty in the file or no row at all).",
        "stays missing",
    ),
    Rule(
        "negative",
        "Negative value",
        "PM2.5 below 0 ug/m3 is not possible.",
        "set to missing",
    ),
    Rule(
        "above_max",
        f"Above {PM25_MAX:g} ug/m3",
        "Above the physical limit for ambient air.",
        "set to missing",
    ),
    Rule(
        "zero",
        "Zero",
        "Exactly 0 ug/m3. Possible in clean air with whole-number resolution.",
        "flag only, value kept",
    ),
    Rule(
        "spike",
        "Isolated spike",
        f"A run of at most {SPIKE_MAX_RUN} consecutive hours at or above {SPIKE_MIN:g} ug/m3 that is at least "
        f"{SPIKE_RATIO:g} times the median of the {SPIKE_MIN_NEIGHBOURS}+ valid readings within {SPIKE_WINDOW} h "
        "before it and the same after it. Smooth episodes (gradual rise or decay) do not qualify. "
        "Short real plumes can look like this, so the value is kept unless it is extreme.",
        "flag only, value kept",
    ),
    Rule(
        "spike_extreme",
        "Extreme isolated spike",
        f"A flagged spike whose readings are all at or above {SPIKE_EXTREME_MIN:g} ug/m3, jumping from and back to "
        "readings at least 8 times lower within two hours. Such a jump is not supported by any neighbouring hour and "
        "is treated as a sensor artefact (the November 2021 episode reaches 978 but rises and falls over many hours).",
        "set to missing",
    ),
    Rule(
        "stuck",
        "Stuck sensor",
        f"{STUCK_MIN_RUN} or more identical consecutive hourly readings.",
        "set to missing",
    ),
]
FLAG_COLUMNS = [r.id for r in RULES]


def load_series(path: Path) -> pd.DataFrame:
    """Hourly grid from the first to the last row of the file.

    ``row_present`` tells apart hours with a row (possibly empty) from absent hours.
    """
    raw = pd.read_csv(path, parse_dates=["datetime_utc"])
    raw = raw.set_index("datetime_utc")
    grid = pd.date_range(raw.index.min(), raw.index.max(), freq="h")
    out = pd.DataFrame(index=grid)
    out["value_raw"] = raw["value"].reindex(grid)
    out["row_present"] = grid.isin(raw.index)
    return out


def find_spikes(values: pd.Series) -> pd.Series:
    """Boolean flags for isolated high spikes on a regular hourly grid."""
    v = values.to_numpy(dtype=float)
    n = len(v)
    high = np.nan_to_num(v, nan=-1.0) >= SPIKE_MIN
    flags = np.zeros(n, dtype=bool)
    i = 0
    while i < n:
        if not high[i]:
            i += 1
            continue
        j = i
        while j + 1 < n and high[j + 1]:
            j += 1
        run = v[i : j + 1]
        if len(run) <= SPIKE_MAX_RUN:
            before = v[max(0, i - SPIKE_WINDOW) : i]
            after = v[j + 1 : j + 1 + SPIKE_WINDOW]
            before, after = before[~np.isnan(before)], after[~np.isnan(after)]
            if (
                len(before) >= SPIKE_MIN_NEIGHBOURS
                and len(after) >= SPIKE_MIN_NEIGHBOURS
            ):
                low = run.min()
                if low >= SPIKE_RATIO * np.median(
                    before
                ) and low >= SPIKE_RATIO * np.median(after):
                    flags[i : j + 1] = True
        i = j + 1
    return pd.Series(flags, index=values.index)


def find_stuck(values: pd.Series, min_run: int = STUCK_MIN_RUN) -> pd.Series:
    """Flags runs of identical consecutive hourly readings (missing hours break a run)."""
    valid = values.notna()
    same_as_previous = values.eq(values.shift()) & valid & valid.shift(fill_value=False)
    run_id = (~same_as_previous).cumsum()
    run_length = values.groupby(run_id).transform("size")
    return (
        same_as_previous.groupby(run_id).transform("any")
        & (run_length >= min_run)
        & valid
    )


def flag_pm25(series: pd.DataFrame) -> pd.DataFrame:
    """Add flag columns and ``value_clean`` to a frame with ``value_raw``."""
    out = series.copy()
    raw = out["value_raw"]
    out["missing"] = raw.isna()
    out["negative"] = raw < 0
    out["above_max"] = raw > PM25_MAX
    out["zero"] = raw == 0
    out["spike"] = find_spikes(raw.where(~(out["negative"] | out["above_max"])))
    out["spike_extreme"] = out["spike"] & (raw >= SPIKE_EXTREME_MIN)
    out["stuck"] = find_stuck(raw)
    drop = out["negative"] | out["above_max"] | out["spike_extreme"] | out["stuck"]
    out["value_clean"] = raw.where(~drop)
    return out


def summarise(flagged: pd.DataFrame) -> dict:
    return {
        "rows_in_file": int(flagged["row_present"].sum()),
        "hours_on_grid": len(flagged),
        "first": flagged.index.min().isoformat(),
        "last": flagged.index.max().isoformat(),
        **{r.id: int(flagged[r.id].sum()) for r in RULES},
        "absent_hours": int((~flagged["row_present"]).sum()),
        "valid_raw": int(flagged["value_raw"].notna().sum()),
        "valid_clean": int(flagged["value_clean"].notna().sum()),
    }


def write_flagged(flagged: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    out = flagged.copy()
    out.index.name = "datetime_utc"
    out.index = out.index.strftime("%Y-%m-%dT%H:%M:%SZ")
    for col in FLAG_COLUMNS + ["row_present"]:
        out[col] = out[col].astype(int)
    out.to_csv(path)


def spike_hours(flagged: pd.DataFrame) -> list[tuple[str, float, bool]]:
    """Flagged spike hours as (time, raw value, set to missing)."""
    rows = flagged[flagged["spike"]]
    return [
        (
            t.strftime("%Y-%m-%dT%H:%M:%SZ"),
            float(r["value_raw"]),
            bool(r["spike_extreme"]),
        )
        for t, r in rows.iterrows()
    ]


def clean_all(
    raw_dir: Path | None = None, out_dir: Path = INTERIM, cfg: dict | None = None
) -> dict:
    """Flag every PM2.5 series in the config and write files plus a log."""
    cfg = cfg or load_config()
    raw_dir = raw_dir or ROOT / "data" / "raw" / "openaq"
    log = {
        "created_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "rules": [r.__dict__ for r in RULES],
        "parameters": {
            "pm25_max": PM25_MAX,
            "spike_min": SPIKE_MIN,
            "spike_extreme_min": SPIKE_EXTREME_MIN,
            "spike_ratio": SPIKE_RATIO,
            "spike_max_run": SPIKE_MAX_RUN,
            "spike_window_hours": SPIKE_WINDOW,
            "spike_min_neighbours": SPIKE_MIN_NEIGHBOURS,
            "stuck_min_run": STUCK_MIN_RUN,
        },
        "series": {},
    }
    for series in openaq_series(cfg):
        if series.parameter != "pm25":
            continue
        flagged = flag_pm25(load_series(raw_dir / f"{series.name}_hourly.csv"))
        write_flagged(flagged, out_dir / f"{series.name}_flagged.csv")
        log["series"][series.name] = summarise(flagged) | {
            "spikes": spike_hours(flagged)
        }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "cleaning_log.json").write_text(json.dumps(log, indent=2))
    return log


def render_log(log: dict) -> str:
    """Markdown summary of a cleaning log."""
    names = list(log["series"])
    lines = [
        "# Cleaning log",
        "",
        (
            f"Generated by `python scripts/clean_data.py` ({log['created_utc']}) from `data/raw/openaq/`. "
            "Flags are written to `data/interim/openaq/<series>_flagged.csv` with the raw value, the clean value and one 0/1 column per rule. "
            "Raw files are never changed."
        ),
        "",
        "## Rules",
        "",
        "| Rule | What it flags | Effect on `value_clean` |",
        "|---|---|---|",
    ]
    for r in log["rules"]:
        lines.append(
            f"| `{r['id']}` {r['name']} | {r['description']} | {r['action']} |"
        )
    lines += [
        "",
        "## Records affected",
        "",
        "| Count | " + " | ".join(names) + " |",
        "|---|" + "---|" * len(names),
    ]
    rows = [
        ("rows in file", "rows_in_file"),
        ("hours on the hourly grid", "hours_on_grid"),
        ("hours with no row (absent)", "absent_hours"),
        ("missing (empty or absent)", "missing"),
        ("negative", "negative"),
        ("above limit", "above_max"),
        ("zero (kept)", "zero"),
        ("spike (flagged, kept unless extreme)", "spike"),
        ("extreme spike (set to missing)", "spike_extreme"),
        ("stuck", "stuck"),
        ("valid before cleaning", "valid_raw"),
        ("valid after cleaning", "valid_clean"),
    ]
    for label, key in rows:
        lines.append(
            f"| {label} | "
            + " | ".join(f"{log['series'][n][key]:,}" for n in names)
            + " |"
        )
    lines += ["", "## Hours flagged as spikes", ""]
    for n in names:
        spikes = log["series"][n]["spikes"]
        lines.append(
            f"- `{n}`: "
            + (
                ", ".join(
                    f"{t} ({v:g}{', removed' if removed else ''})"
                    for t, v, removed in spikes
                )
                or "none"
            )
        )
    lines += [
        "",
        "Parameters: "
        + ", ".join(f"`{k}` = {v}" for k, v in log["parameters"].items())
        + ".",
    ]
    return "\n".join(lines) + "\n"
