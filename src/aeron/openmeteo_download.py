"""Download hourly historical weather for Tashkent from Open-Meteo (standard library only).

Usage:
    python -m aeron.openmeteo_download

Uses the Open-Meteo historical weather API (ERA5 reanalysis), which needs no key.
Output: data/raw/openmeteo/era5_tashkent_hourly.csv (UTC timestamps) and
metadata.json. Reanalysis is not the forecast weather available in real use, so
models trained on it look better in evaluation than they will in operation.
"""

from __future__ import annotations

import csv
import json
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, date, datetime
from pathlib import Path

API = "https://archive-api.open-meteo.com/v1/archive"
ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "data" / "raw" / "openmeteo"

# US Diplomatic Post monitor, the longest PM2.5 series found (see data_sources.md).
LATITUDE, LONGITUDE = 41.3672, 69.2725
START = date(2018, 11, 1)
HOURLY = [
    "temperature_2m",
    "relative_humidity_2m",
    "dew_point_2m",
    "precipitation",
    "surface_pressure",
    "cloud_cover",
    "wind_speed_10m",
    "wind_direction_10m",
    "wind_gusts_10m",
]


def ssl_context() -> ssl.SSLContext:
    """python.org builds on macOS lack CA certs, so use the system bundle."""
    bundle = Path("/etc/ssl/cert.pem")
    if bundle.exists():
        return ssl.create_default_context(cafile=str(bundle))
    return ssl.create_default_context()


CONTEXT = ssl_context()


def get(url: str) -> dict:
    last: Exception | None = None
    for attempt in range(6):
        try:
            with urllib.request.urlopen(url, timeout=120, context=CONTEXT) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as err:
            if err.code in (429, 500, 502, 503, 504):
                last = err
                time.sleep(15 * (attempt + 1))
                continue
            raise
        except (urllib.error.URLError, TimeoutError, ConnectionError) as err:
            last = err
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"Giving up on {url}: {last}")


def year_ranges(start: date, end: date):
    for year in range(start.year, end.year + 1):
        yield max(start, date(year, 1, 1)), min(end, date(year, 12, 31))


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    # The archive lags real time by several days; stop a week before today.
    end = date.fromordinal(datetime.now(UTC).date().toordinal() - 7)
    rows = []
    for d_from, d_to in year_ranges(START, end):
        query = urllib.parse.urlencode(
            {
                "latitude": LATITUDE,
                "longitude": LONGITUDE,
                "start_date": d_from.isoformat(),
                "end_date": d_to.isoformat(),
                "hourly": ",".join(HOURLY),
                "timezone": "UTC",
            }
        )
        data = get(f"{API}?{query}")
        h = data["hourly"]
        for i, t in enumerate(h["time"]):
            rows.append([t + ":00Z"] + [h[v][i] for v in HOURLY])
        print(d_from.year, len(h["time"]), flush=True)
        time.sleep(2)
    path = OUT_DIR / "era5_tashkent_hourly.csv"
    with path.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["datetime_utc", *HOURLY])
        w.writerows(rows)
    meta = {
        "retrieved_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "source": "Open-Meteo historical weather API (ERA5 reanalysis)",
        "latitude": LATITUDE,
        "longitude": LONGITUDE,
        "start": START.isoformat(),
        "end": end.isoformat(),
        "variables": HOURLY,
        "rows": len(rows),
    }
    (OUT_DIR / "metadata.json").write_text(json.dumps(meta, indent=2))
    print("rows", len(rows))


if __name__ == "__main__":
    main()
