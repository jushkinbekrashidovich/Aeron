"""Validate the raw data files in data/raw/ (schema, units, ranges, time grid).

Usage:
    python scripts/validate_data.py

Exits with status 1 if any file has an error. Warnings and notes do not fail the
run. The script only reads data and never modifies it.
"""

from __future__ import annotations

import sys

from aeron.validation import format_reports, validate_all


def main() -> int:
    reports = validate_all()
    print(format_reports(reports))
    errors = sum(1 for r in reports if r.status == "ERROR")
    warns = sum(1 for r in reports if r.status == "WARN")
    print(f"\n{len(reports)} files: {errors} with errors, {warns} with warnings")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
