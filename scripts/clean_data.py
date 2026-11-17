"""Flag questionable PM2.5 readings and write the cleaning log.

Usage:
    python scripts/clean_data.py

Reads data/raw/openaq/, writes data/interim/openaq/<series>_flagged.csv and
cleaning_log.json, and refreshes docs/datasets/cleaning_log.md. Raw files are
never modified.
"""

from __future__ import annotations

from aeron.cleaning import clean_all, render_log
from aeron.config import ROOT


def main() -> None:
    log = clean_all()
    doc = ROOT / "docs" / "datasets" / "cleaning_log.md"
    doc.write_text(render_log(log))
    for name, s in log["series"].items():
        print(
            f"{name}: valid {s['valid_raw']:,} -> {s['valid_clean']:,}; spikes {s['spike']}, "
            f"stuck {s['stuck']}, negative {s['negative']}, zeros {s['zero']}, missing {s['missing']:,}"
        )
    print(f"wrote {doc.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
