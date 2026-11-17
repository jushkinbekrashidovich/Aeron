"""Build the processed hourly and daily datasets in data/processed/.

Usage:
    python scripts/download_data.py
    python scripts/clean_data.py
    python scripts/build_dataset.py

Needs the raw files (download_data.py) and the flagged PM2.5 series (clean_data.py).
"""

from __future__ import annotations

import json

from aeron.processing import build_all


def main() -> None:
    meta = build_all()
    print(json.dumps({k: meta[k] for k in ("hourly", "daily")}, indent=2))


if __name__ == "__main__":
    main()
