"""Open-Meteo downloads: ERA5 reanalysis and archived forecasts (Previous Runs).

Resumable and idempotent in the same way as the OpenAQ ingestion: data are
fetched in blocks (one per year for ERA5, 45 days for forecasts) cached under
``data/raw/openmeteo/_cache/``. Blocks that are old enough are skipped on later
runs, and the merged files are rebuilt from the cache:

- ``era5_tashkent_hourly.csv`` (core variables)
- ``era5_extra_tashkent_hourly.csv`` (extra variables)
- ``forecast_previous_runs_hourly.csv``

Open-Meteo returns wind speed and gusts in km/h. Times are UTC, written as
``YYYY-MM-DDTHH:MM:00Z``.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from aeron.config import ROOT, load_config
from aeron.ingest.files import is_final, read_rows, write_rows
from aeron.ingest.http import Client

OUT_DIR = ROOT / "data" / "raw" / "openmeteo"
TIME = "datetime_utc"


def fetch_hourly(
    client: Client,
    url: str,
    latitude: float,
    longitude: float,
    start: date,
    end: date,
    variables: list[str],
) -> list[list]:
    """Hourly rows [time, value, ...] for the variables, UTC. Empty cells become ''."""
    data = client.get_json(
        url,
        {
            "latitude": latitude,
            "longitude": longitude,
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "hourly": ",".join(variables),
            "timezone": "UTC",
        },
    )
    hourly = data["hourly"]
    rows = []
    for i, stamp in enumerate(hourly["time"]):
        rows.append(
            [stamp + ":00Z"]
            + ["" if hourly[v][i] is None else hourly[v][i] for v in variables]
        )
    return rows


def year_blocks(start: date, end: date) -> list[tuple[date, date]]:
    return [
        (max(start, date(year, 1, 1)), min(end, date(year, 12, 31)))
        for year in range(start.year, end.year + 1)
    ]


def day_blocks(start: date, end: date, days: int) -> list[tuple[date, date]]:
    blocks = []
    first = start
    while first <= end:
        last = min(first + timedelta(days=days - 1), end)
        blocks.append((first, last))
        first = last + timedelta(days=1)
    return blocks


def merge_cache(cache_dir: Path) -> tuple[list[str], list[list]]:
    """Combine cache files into one sorted table without repeated timestamps."""
    header: list[str] = []
    rows: dict[str, list] = {}
    for path in sorted(cache_dir.glob("*.csv")):
        file_header, part = read_rows(path)
        if header and file_header != header:
            raise ValueError(
                f"{path.name} has different columns from the other cache files. "
                f"The variable list changed: delete {cache_dir} and download again."
            )
        header = file_header
        for row in part:
            rows[row[0]] = row
    return header, [rows[key] for key in sorted(rows)]


def write_meta(
    path: Path,
    source: str,
    cfg: dict,
    start: date,
    end: date,
    variables: list[str],
    rows: int,
    fetched: bool,
) -> None:
    previous = json.loads(path.read_text()) if path.exists() else {}
    meta = {
        "retrieved_utc": datetime.now(UTC).isoformat(timespec="seconds")
        if fetched or "retrieved_utc" not in previous
        else previous["retrieved_utc"],
        "source": source,
        "latitude": cfg["openmeteo"]["latitude"],
        "longitude": cfg["openmeteo"]["longitude"],
        "start": start.isoformat(),
        "end": end.isoformat(),
        "variables": variables,
        "rows": rows,
    }
    path.write_text(json.dumps(meta, indent=2))


def download_blocks(
    client: Client,
    url: str,
    cfg: dict,
    blocks: list[tuple[date, date]],
    variables: list[str],
    cache_dir: Path,
    today: date,
    sleep: Callable[[float], None],
    log: Callable[[str], None],
    label: str,
) -> tuple[int, int]:
    om = cfg["openmeteo"]
    fetched = skipped = 0
    header = [TIME, *variables]
    for first, last in blocks:
        path = cache_dir / f"{first.isoformat()}.csv"
        if path.exists() and is_final(last + timedelta(days=1), today):
            skipped += 1
            continue
        rows = fetch_hourly(
            client, url, om["latitude"], om["longitude"], first, last, variables
        )
        write_rows(path, header, rows)
        fetched += 1
        log(f"{label} {first} to {last}: {len(rows)} rows")
        sleep(2)
    return fetched, skipped


def download_era5(
    cfg: dict, client: Client, out_dir: Path, today: date, sleep, log
) -> dict:
    om = cfg["openmeteo"]
    core, extra = om["core_variables"], om["extra_variables"]
    variables = core + extra
    start = date.fromisoformat(om["era5_start"])
    end = today - timedelta(days=om["era5_end_lag_days"])
    cache = out_dir / "_cache" / "era5"
    blocks = [(a, b) for a, b in year_blocks(start, end)]
    # Years are keyed by their first day; a year's cache file name is its start date.
    fetched, skipped = download_blocks(
        client,
        om["archive_url"],
        cfg,
        blocks,
        variables,
        cache,
        today,
        sleep,
        log,
        "era5",
    )
    header, rows = merge_cache(cache)
    index = {name: i for i, name in enumerate(header)}
    for fname, cols, mfile, source in (
        (
            "era5_tashkent_hourly.csv",
            core,
            "metadata.json",
            "Open-Meteo historical weather API (ERA5 reanalysis)",
        ),
        (
            "era5_extra_tashkent_hourly.csv",
            extra,
            "era5_extra_metadata.json",
            "Open-Meteo historical weather API (ERA5 reanalysis)",
        ),
    ):
        part = [[r[0], *[r[index[c]] for c in cols]] for r in rows]
        write_rows(out_dir / fname, [TIME, *cols], part)
        write_meta(
            out_dir / mfile, source, cfg, start, end, cols, len(part), fetched > 0
        )
    return {"blocks_fetched": fetched, "blocks_skipped": skipped, "rows": len(rows)}


def forecast_columns(cfg: dict) -> list[str]:
    fc = cfg["openmeteo"]["forecast"]
    return [
        f"{v}_previous_day{n}" for n in fc["previous_days"] for v in fc["variables"]
    ]


def download_forecasts(
    cfg: dict, client: Client, out_dir: Path, today: date, sleep, log
) -> dict:
    om = cfg["openmeteo"]
    fc = om["forecast"]
    columns = forecast_columns(cfg)
    start = date.fromisoformat(fc["start"])
    end = min(date.fromisoformat(fc["end"]), today)
    cache = out_dir / "_cache" / "forecast"
    blocks = day_blocks(start, end, fc["chunk_days"])
    fetched, skipped = download_blocks(
        client,
        om["previous_runs_url"],
        cfg,
        blocks,
        columns,
        cache,
        today,
        sleep,
        log,
        "forecast",
    )
    header, rows = merge_cache(cache)
    write_rows(out_dir / "forecast_previous_runs_hourly.csv", header, rows)
    meta_cfg = {"openmeteo": om}
    write_meta(
        out_dir / "forecast_previous_runs_metadata.json",
        "Open-Meteo Previous Runs API",
        meta_cfg,
        start,
        end,
        fc["variables"],
        len(rows),
        fetched > 0,
    )
    meta_path = out_dir / "forecast_previous_runs_metadata.json"
    meta = json.loads(meta_path.read_text())
    meta["previous_days"] = fc["previous_days"]
    meta_path.write_text(json.dumps(meta, indent=2))
    return {"blocks_fetched": fetched, "blocks_skipped": skipped, "rows": len(rows)}


def seed_era5(cfg: dict, out_dir: Path, today: date) -> int:
    """Split existing merged ERA5 files into cache blocks (complete earlier download only)."""
    om = cfg["openmeteo"]
    cache = out_dir / "_cache" / "era5"
    core_path = out_dir / "era5_tashkent_hourly.csv"
    extra_path = out_dir / "era5_extra_tashkent_hourly.csv"
    if cache.exists() or not (core_path.exists() and extra_path.exists()):
        return 0
    core_h, core = read_rows(core_path)
    extra_h, extra = read_rows(extra_path)
    extra_by_time = {r[0]: r[1:] for r in extra}
    header = core_h + extra_h[1:]
    by_year: dict[str, list] = {}
    for r in core:
        by_year.setdefault(r[0][:4], []).append(r + extra_by_time[r[0]])
    start = date.fromisoformat(om["era5_start"])
    end = today - timedelta(days=om["era5_end_lag_days"])
    written = 0
    for first, last in year_blocks(start, end):
        if is_final(last + timedelta(days=1), today):
            write_rows(
                cache / f"{first.isoformat()}.csv",
                header,
                by_year.get(str(first.year), []),
            )
            written += 1
    return written


def seed_forecasts(cfg: dict, out_dir: Path, today: date) -> int:
    fc = cfg["openmeteo"]["forecast"]
    path = out_dir / "forecast_previous_runs_hourly.csv"
    cache = out_dir / "_cache" / "forecast"
    if cache.exists() or not path.exists():
        return 0
    header, rows = read_rows(path)
    written = 0
    for first, last in day_blocks(
        date.fromisoformat(fc["start"]),
        min(date.fromisoformat(fc["end"]), today),
        fc["chunk_days"],
    ):
        if is_final(last + timedelta(days=1), today):
            part = [
                r for r in rows if first.isoformat() <= r[0][:10] <= last.isoformat()
            ]
            write_rows(cache / f"{first.isoformat()}.csv", header, part)
            written += 1
    return written


def run(
    cfg: dict | None = None,
    out_dir: Path = OUT_DIR,
    today: date | None = None,
    client: Client | None = None,
    which: tuple[str, ...] = ("era5", "forecast"),
    seed: bool = False,
    sleep: Callable[[float], None] = time.sleep,
    log: Callable[[str], None] = print,
) -> dict:
    cfg = cfg or load_config()
    today = today or datetime.now(UTC).date()
    client = client or Client()
    out_dir.mkdir(parents=True, exist_ok=True)
    result = {}
    if "era5" in which:
        if seed:
            log(f"era5: seeded {seed_era5(cfg, out_dir, today)} year blocks")
        result["era5"] = download_era5(cfg, client, out_dir, today, sleep, log)
    if "forecast" in which:
        if seed:
            log(f"forecast: seeded {seed_forecasts(cfg, out_dir, today)} blocks")
        result["forecast"] = download_forecasts(cfg, client, out_dir, today, sleep, log)
    return result


if __name__ == "__main__":
    run()
