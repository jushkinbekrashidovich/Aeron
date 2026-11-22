"""Where the service finds its data and model. Overridable with environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from aeron.config import ROOT

DEFAULT_DAILY = ROOT / "data" / "processed" / "daily_us_embassy.csv"
DEFAULT_MODELS = ROOT / "artifacts" / "models"


@dataclass(frozen=True)
class Settings:
    daily_csv: Path = DEFAULT_DAILY
    model_dir: Path | None = (
        None  # one model version folder; None picks the latest replay model
    )
    models_root: Path = DEFAULT_MODELS
    cors_origins: tuple[str, ...] = ("http://localhost:3000",)

    @classmethod
    def from_env(cls) -> Settings:
        daily = Path(os.environ.get("AERON_DAILY_CSV", DEFAULT_DAILY))
        model = os.environ.get("AERON_MODEL_DIR")
        root = Path(os.environ.get("AERON_MODELS_ROOT", DEFAULT_MODELS))
        origins = os.environ.get("AERON_CORS_ORIGINS", "http://localhost:3000")
        cors = tuple(o.strip() for o in origins.split(",") if o.strip())
        return cls(daily, Path(model) if model else None, root, cors)

    def resolve_model_dir(self) -> Path | None:
        """The model folder to load: the one named, else the newest replay model."""
        if self.model_dir is not None:
            return self.model_dir
        if not self.models_root.exists():
            return None
        candidates = sorted(
            p for p in self.models_root.iterdir() if p.is_dir() and "replay" in p.name
        )
        return candidates[-1] if candidates else None
