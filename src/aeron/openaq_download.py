"""Download hourly OpenAQ v3 sensor data to data/raw/openaq/ (standard library only).

Usage:
    python -m aeron.openaq_download

The API key is read from the OPENAQ_API_KEY environment variable or from an
untracked .env file in the repository root. Each output file is a CSV with the
UTC period start, value, and OpenAQ coverage fields. A metadata JSON records the
retrieval time and sensor ids.
"""

from __future__ import annotations

import csv
import json
import os
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

API = "https://api.openaq.org/v3"
ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "data" / "raw" / "openaq"

# (name, location_id, sensor_id, parameter, start date)
SENSORS = [
    ("us_embassy_pm25", 8881, 25916, "pm25", "2018-11-01"),
    ("sputnik4_pm25", 4902926, 13465748, "pm25", "2023-07-01"),
    ("sputnik4_humidity", 4902926, 13465749, "relativehumidity", "2023-07-01"),
    ("sputnik4_temperature", 4902926, 13465750, "temperature", "2023-07-01"),
]
PAGE_LIMIT = 200  # smaller pages respond faster; 1000 often times out


def load_key() -> str:
    key = os.environ.get("OPENAQ_API_KEY")
    env_file = ROOT / ".env"
    if not key and env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith("OPENAQ_API_KEY="):
                key = line.split("=", 1)[1].strip()
    if not key:
        raise SystemExit("OPENAQ_API_KEY is not set (environment or .env).")
    return key


def ssl_context() -> ssl.SSLContext:
    """Verify TLS. python.org builds on macOS lack CA certs, so fall back to the
    system bundle when it exists."""
    system_bundle = Path("/etc/ssl/cert.pem")
    if system_bundle.exists():
        return ssl.create_default_context(cafile=str(system_bundle))
    return ssl.create_default_context()


CONTEXT = ssl_context()


def get(url: str, key: str) -> dict:
    """GET with simple retry for rate limits (429) and transient errors."""
    last: Exception | None = None
    for attempt in range(6):
        req = urllib.request.Request(url, headers={"X-API-Key": key})
        try:
            with urllib.request.urlopen(req, timeout=120, context=CONTEXT) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as err:
            if err.code in (429, 500, 502, 503, 504):
                time.sleep(5 * (attempt + 1))
                continue
            raise
        except (urllib.error.URLError, TimeoutError, ConnectionError) as err:
            last = err
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"Giving up on {url}: {last}")


def month_starts(start: str):
    """Yield (from, to) ISO strings for consecutive calendar months until now."""
    y, m = int(start[:4]), int(start[5:7])
    now = datetime.now(UTC)
    while (y, m) <= (now.year, now.month):
        ny, nm = (y + 1, 1) if m == 12 else (y, m + 1)
        yield f"{y:04d}-{m:02d}-01T00:00:00Z", f"{ny:04d}-{nm:02d}-01T00:00:00Z"
        y, m = ny, nm


def download_sensor(name: str, sensor_id: int, start: str, key: str) -> int:
    """Fetch one month per request; a wide range makes the API time out."""
    rows = {}
    for dt_from, dt_to in month_starts(start):
        page = 1
        while True:
            query = urllib.parse.urlencode(
                {
                    "datetime_from": dt_from,
                    "datetime_to": dt_to,
                    "limit": PAGE_LIMIT,
                    "page": page,
                }
            )
            data = get(f"{API}/sensors/{sensor_id}/hours?{query}", key)
            results = data.get("results", [])
            for r in results:
                cov = r.get("coverage") or {}
                ts = r["period"]["datetimeFrom"]["utc"]
                rows[ts] = (
                    ts,
                    r["value"],
                    cov.get("percentComplete"),
                    cov.get("observedCount"),
                    cov.get("expectedCount"),
                )
            print(name, dt_from[:7], page, len(results), flush=True)
            time.sleep(1.1)  # stay under 60 requests per minute
            if len(results) < PAGE_LIMIT:
                break
            page += 1
    path = OUT_DIR / f"{name}_hourly.csv"
    with path.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(
            ["datetime_utc", "value", "percent_complete", "observed", "expected"]
        )
        w.writerows(rows[k] for k in sorted(rows))
    return len(rows)


def main() -> None:
    key = load_key()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    meta = {
        "retrieved_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "source": "OpenAQ API v3, /sensors/{id}/hours",
        "files": {},
    }
    for name, loc, sensor, param, start in SENSORS:
        n = download_sensor(name, sensor, start, key)
        meta["files"][name] = {
            "location_id": loc,
            "sensor_id": sensor,
            "parameter": param,
            "rows": n,
        }
        print(f"{name}: {n} rows")
    (OUT_DIR / "metadata.json").write_text(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
