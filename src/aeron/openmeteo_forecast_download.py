"""Download archived Open-Meteo forecasts issued 2 to 4 days before the valid time.

Usage:
    python -m aeron.openmeteo_forecast_download

Uses the Open-Meteo Previous Runs API (no key). The variable
``<name>_previous_dayN`` is the forecast for a given hour that was issued about
N days earlier. Output: data/raw/openmeteo/forecast_previous_runs_hourly.csv
(UTC) with columns ``<name>_previous_dayN``, and metadata.json updated alongside.

Why days 2 to 4: for a forecast origin t and lead h = 24, 48, 72 h, the weather
forecast for t + h must already exist at t. A forecast issued N days before the
valid time is available 24*N - h hours before t. Model runs are published a few
hours after their nominal start, so day N = h/24 + 1 leaves at least a day of
margin, while day N = h/24 would be available only around t itself.
"""

from __future__ import annotations

import csv
import json
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

API = "https://previous-runs-api.open-meteo.com/v1/forecast"
ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "data" / "raw" / "openmeteo"

LATITUDE, LONGITUDE = 41.3672, 69.2725
START = date(2024, 1, 19)  # first day with the non-temperature variables
END = date(2025, 3, 1)
VARIABLES = [
    "temperature_2m",
    "relative_humidity_2m",
    "precipitation",
    "surface_pressure",
    "cloud_cover",
    "wind_speed_10m",
    "wind_direction_10m",
    "wind_gusts_10m",
    "shortwave_radiation",
    "vapour_pressure_deficit",
    "pressure_msl",
]
DAYS = (2, 3, 4)
CHUNK_DAYS = 45


def ssl_context() -> ssl.SSLContext:
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


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    columns = [f"{v}_previous_day{n}" for n in DAYS for v in VARIABLES]
    rows = []
    d = START
    while d <= END:
        d_to = min(d + timedelta(days=CHUNK_DAYS - 1), END)
        query = urllib.parse.urlencode(
            {
                "latitude": LATITUDE,
                "longitude": LONGITUDE,
                "start_date": d.isoformat(),
                "end_date": d_to.isoformat(),
                "hourly": ",".join(columns),
                "timezone": "UTC",
            }
        )
        h = get(f"{API}?{query}")["hourly"]
        for i, t in enumerate(h["time"]):
            rows.append([t + ":00Z"] + [h[c][i] for c in columns])
        print(d, d_to, len(h["time"]), flush=True)
        d = d_to + timedelta(days=1)
        time.sleep(2)
    with (OUT_DIR / "forecast_previous_runs_hourly.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["datetime_utc", *columns])
        w.writerows(rows)
    meta = {
        "retrieved_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "source": "Open-Meteo Previous Runs API",
        "latitude": LATITUDE,
        "longitude": LONGITUDE,
        "start": START.isoformat(),
        "end": END.isoformat(),
        "previous_days": list(DAYS),
        "variables": VARIABLES,
        "rows": len(rows),
    }
    (OUT_DIR / "forecast_previous_runs_metadata.json").write_text(
        json.dumps(meta, indent=2)
    )
    print("rows", len(rows))


if __name__ == "__main__":
    main()
