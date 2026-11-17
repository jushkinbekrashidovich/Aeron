"""Download extra ERA5 variables that describe stagnation and inversions.

Usage:
    python -m aeron.openmeteo_extra_download

Same location, period and API as openmeteo_download.py. Output:
data/raw/openmeteo/era5_extra_tashkent_hourly.csv (UTC) and
era5_extra_metadata.json.

Boundary layer height, snow depth and soil variables are available for the
reanalysis but not as archived forecasts in the Previous Runs API (checked
2026-11-17), so models using them can only be backtested with observed weather.
"""

from __future__ import annotations

import csv
import json
import time
import urllib.parse
from datetime import UTC, date, datetime

from aeron.openmeteo_download import (
    API,
    LATITUDE,
    LONGITUDE,
    OUT_DIR,
    START,
    get,
    year_ranges,
)

EXTRA = [
    "boundary_layer_height",
    "shortwave_radiation",
    "vapour_pressure_deficit",
    "pressure_msl",
    "snow_depth",
]


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    end = date.fromordinal(datetime.now(UTC).date().toordinal() - 7)
    rows = []
    for d_from, d_to in year_ranges(START, end):
        query = urllib.parse.urlencode(
            {
                "latitude": LATITUDE,
                "longitude": LONGITUDE,
                "start_date": d_from.isoformat(),
                "end_date": d_to.isoformat(),
                "hourly": ",".join(EXTRA),
                "timezone": "UTC",
            }
        )
        h = get(f"{API}?{query}")["hourly"]
        for i, t in enumerate(h["time"]):
            rows.append([t + ":00Z"] + [h[v][i] for v in EXTRA])
        print(d_from.year, len(h["time"]), flush=True)
        time.sleep(2)
    with (OUT_DIR / "era5_extra_tashkent_hourly.csv").open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["datetime_utc", *EXTRA])
        w.writerows(rows)
    meta = {
        "retrieved_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "source": "Open-Meteo historical weather API (ERA5 reanalysis)",
        "latitude": LATITUDE,
        "longitude": LONGITUDE,
        "start": START.isoformat(),
        "end": end.isoformat(),
        "variables": EXTRA,
        "rows": len(rows),
    }
    (OUT_DIR / "era5_extra_metadata.json").write_text(json.dumps(meta, indent=2))
    print("rows", len(rows))


if __name__ == "__main__":
    main()
