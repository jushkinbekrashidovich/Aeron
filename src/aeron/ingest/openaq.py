"""OpenAQ v3 hourly downloads: paginated, rate-limited, resumable and idempotent.

Each series is fetched one calendar month at a time into
``data/raw/openaq/_months/<series>/<YYYY-MM>.csv``. Months that are old enough
are skipped on later runs, an interrupted run resumes where it stopped, and the
per-series file ``<series>_hourly.csv`` is rebuilt from the month files.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path

from aeron.config import ROOT, Series, get_secret, load_config, openaq_series
from aeron.ingest.files import is_final, month_ranges, read_rows, write_rows
from aeron.ingest.http import Client

COLUMNS = ["datetime_utc", "value", "percent_complete", "observed", "expected"]
OUT_DIR = ROOT / "data" / "raw" / "openaq"


def parse_results(results: list[dict]) -> list[list]:
    """Convert API items to CSV rows. A missing value becomes an empty string."""
    rows = []
    for item in results:
        coverage = item.get("coverage") or {}
        value = item.get("value")
        rows.append(
            [
                item["period"]["datetimeFrom"]["utc"],
                "" if value is None else value,
                coverage.get("percentComplete"),
                coverage.get("observedCount"),
                coverage.get("expectedCount"),
            ]
        )
    return rows


def fetch_month(
    client: Client,
    api_url: str,
    sensor_id: int,
    first: date,
    nxt: date,
    page_limit: int,
    pause: float,
    sleep: Callable[[float], None] = time.sleep,
) -> list[list]:
    """All hourly rows for one sensor in [first, nxt), following pagination."""
    rows: list[list] = []
    page = 1
    while True:
        data = client.get_json(
            f"{api_url}/sensors/{sensor_id}/hours",
            {
                "datetime_from": f"{first.isoformat()}T00:00:00Z",
                "datetime_to": f"{nxt.isoformat()}T00:00:00Z",
                "limit": page_limit,
                "page": page,
            },
        )
        results = data.get("results", [])
        rows.extend(parse_results(results))
        sleep(pause)
        if len(results) < page_limit:
            return rows
        page += 1


def month_file(out_dir: Path, name: str, first: date) -> Path:
    return out_dir / "_months" / name / f"{first:%Y-%m}.csv"


def merge_months(out_dir: Path, name: str) -> int:
    """Rebuild ``<name>_hourly.csv`` from its month files. Returns the row count."""
    rows: dict[str, list] = {}
    for path in sorted((out_dir / "_months" / name).glob("*.csv")):
        for row in read_rows(path)[1]:
            rows[row[0]] = row  # a repeated timestamp keeps the latest copy
    ordered = [rows[key] for key in sorted(rows)]
    write_rows(out_dir / f"{name}_hourly.csv", COLUMNS, ordered)
    return len(ordered)


def download_series(
    series: Series,
    client: Client,
    cfg: dict,
    out_dir: Path,
    today: date,
    sleep: Callable[[float], None] = time.sleep,
    log: Callable[[str], None] = print,
) -> dict:
    api = cfg["openaq"]
    fetched = skipped = 0
    for first, nxt in month_ranges(date.fromisoformat(series.start), today):
        path = month_file(out_dir, series.name, first)
        if path.exists() and is_final(nxt, today):
            skipped += 1
            continue
        rows = fetch_month(
            client,
            api["api_url"],
            series.sensor_id,
            first,
            nxt,
            api["page_limit"],
            api["request_pause_seconds"],
            sleep,
        )
        write_rows(path, COLUMNS, rows)
        fetched += 1
        log(f"{series.name} {first:%Y-%m}: {len(rows)} rows")
    total = merge_months(out_dir, series.name)
    return {
        "location_id": series.location_id,
        "sensor_id": series.sensor_id,
        "parameter": series.parameter,
        "start": series.start,
        "rows": total,
        "months_fetched": fetched,
        "months_skipped": skipped,
    }


def seed_from_existing(series: Series, out_dir: Path, today: date) -> int:
    """Split an existing ``<name>_hourly.csv`` into month files.

    Use only when that file came from a complete earlier download of the same
    series, so the months need not be fetched again. Months that are not yet
    final are left out and will be downloaded. Returns the months written.
    """
    merged = out_dir / f"{series.name}_hourly.csv"
    if not merged.exists() or (out_dir / "_months" / series.name).exists():
        return 0
    by_month: dict[str, list] = {}
    for row in read_rows(merged)[1]:
        by_month.setdefault(row[0][:7], []).append(row)
    written = 0
    for first, nxt in month_ranges(date.fromisoformat(series.start), today):
        if not is_final(nxt, today):
            continue
        write_rows(
            month_file(out_dir, series.name, first),
            COLUMNS,
            by_month.get(f"{first:%Y-%m}", []),
        )
        written += 1
    return written


def run(
    cfg: dict | None = None,
    out_dir: Path = OUT_DIR,
    today: date | None = None,
    client: Client | None = None,
    only: list[str] | None = None,
    seed: bool = False,
    sleep: Callable[[float], None] = time.sleep,
    log: Callable[[str], None] = print,
) -> dict:
    cfg = cfg or load_config()
    today = today or datetime.now(UTC).date()
    client = client or Client({"X-API-Key": get_secret("OPENAQ_API_KEY")})
    selected = [s for s in openaq_series(cfg) if not only or s.name in only]
    files = {}
    for series in selected:
        if seed:
            log(
                f"{series.name}: seeded {seed_from_existing(series, out_dir, today)} months"
            )
        files[series.name] = download_series(
            series, client, cfg, out_dir, today, sleep, log
        )
    meta_path = out_dir / "metadata.json"
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {"files": {}}
    meta["source"] = "OpenAQ API v3, /sensors/{id}/hours"
    meta["files"].update(files)
    if any(f["months_fetched"] for f in files.values()):
        meta["retrieved_utc"] = datetime.now(UTC).isoformat(timespec="seconds")
    meta.setdefault("retrieved_utc", datetime.now(UTC).isoformat(timespec="seconds"))
    out_dir.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(json.dumps(meta, indent=2))
    return meta


if __name__ == "__main__":
    run()
