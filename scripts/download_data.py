"""Download all raw data to data/raw/ (OpenAQ, ERA5 weather, archived forecasts).

Usage:
    python scripts/download_data.py                      # everything
    python scripts/download_data.py --only openaq        # one source
    python scripts/download_data.py --seed-from-existing # reuse earlier complete downloads

Runs are resumable and idempotent: finished months or blocks are skipped, and the
most recent 45 days are always fetched again. Settings are in configs/sources.toml.
The OpenAQ key is read from OPENAQ_API_KEY (environment or .env).
"""

from __future__ import annotations

import argparse

from aeron.ingest import openaq, openmeteo


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--only",
        choices=["openaq", "era5", "forecast"],
        action="append",
        help="download only this source (repeatable)",
    )
    parser.add_argument(
        "--seed-from-existing",
        action="store_true",
        help="split existing merged files into resumable blocks instead of downloading them again "
        "(only if they came from a complete earlier download)",
    )
    args = parser.parse_args()
    selected = set(args.only or ["openaq", "era5", "forecast"])
    if "openaq" in selected:
        openaq.run(seed=args.seed_from_existing)
    weather = tuple(s for s in ("era5", "forecast") if s in selected)
    if weather:
        openmeteo.run(which=weather, seed=args.seed_from_existing)


if __name__ == "__main__":
    main()
