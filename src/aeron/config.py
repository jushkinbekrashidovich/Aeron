"""Project configuration: paths, source settings and secrets.

Settings that describe the data (stations, dates, request parameters) live in
``configs/sources.toml``. Secrets such as the OpenAQ key are read from the
environment or from an untracked ``.env`` file and are never stored in the
configuration file.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIG_FILE = ROOT / "configs" / "sources.toml"


@dataclass(frozen=True)
class Series:
    """One OpenAQ sensor series to download."""

    name: str
    location_id: int
    sensor_id: int
    parameter: str
    start: str
    quality: str
    primary: bool


def load_config(path: Path = CONFIG_FILE) -> dict:
    """Read the TOML configuration file."""
    with path.open("rb") as fh:
        return tomllib.load(fh)


def openaq_series(config: dict | None = None) -> list[Series]:
    """OpenAQ series defined in the configuration."""
    config = config or load_config()
    return [Series(**entry) for entry in config["openaq"]["series"]]


def read_env_file(path: Path) -> dict[str, str]:
    """Parse simple KEY=VALUE lines of a .env file (comments and blanks ignored)."""
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def get_secret(name: str, root: Path = ROOT) -> str:
    """Return a secret from the environment, else from ``<root>/.env``.

    Raises ``RuntimeError`` (without printing any value) when it is missing or empty.
    """
    value = os.environ.get(name) or read_env_file(root / ".env").get(name)
    if not value:
        raise RuntimeError(
            f"{name} is not set. Add it to the environment or to .env (see .env.example)."
        )
    return value
