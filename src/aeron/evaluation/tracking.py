"""Experiment tracking with MLflow, stored locally under ``mlruns/`` (not committed).

Every run records what is needed to reproduce and compare it:

- parameters: model settings, feature set name, lead time, split scheme and seed
- tags: git commit and whether the working tree had uncommitted changes, a version
  of the processed data (checksums and build time), Python and library versions
- artifacts: the feature list and, if given, the predictions of the run
- metrics: whatever the run reports, with names like ``mae/winter/lead1``

Secrets are never recorded: parameters whose names look like keys or tokens are dropped.
The store is SQLite because MLflow's plain file store is in maintenance mode.
"""

from __future__ import annotations

import hashlib
import json
import math
import platform
import re
import subprocess
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import mlflow
import numpy as np
import pandas as pd
import sklearn

from aeron.config import ROOT

TRACKING_DIR = ROOT / "mlruns"
PROCESSED = ROOT / "data" / "processed"
SECRET_NAME = re.compile(r"key|token|secret|password|credential", re.IGNORECASE)
EXPERIMENT = "aeron"


def scrub(params: dict, prefix: str = "") -> dict[str, str]:
    """Flatten nested parameters to strings and drop anything that looks like a secret."""
    flat: dict[str, str] = {}
    for name, value in params.items():
        full = f"{prefix}{name}"
        if SECRET_NAME.search(full):
            continue
        if isinstance(value, dict):
            flat.update(scrub(value, prefix=f"{full}."))
        else:
            flat[full] = str(value)[:500]
    return flat


def _sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    return hashlib.sha256(path.read_bytes()).hexdigest()[:12]


def data_version(processed_dir: Path = PROCESSED) -> dict[str, str]:
    """Checksums of the processed tables and their build time, as tags."""
    version = {
        "data.daily_sha256": _sha256(processed_dir / "daily_us_embassy.csv")
        or "missing",
        "data.hourly_sha256": _sha256(processed_dir / "hourly_us_embassy.csv")
        or "missing",
    }
    meta = processed_dir / "metadata.json"
    if meta.exists():
        version["data.built_utc"] = json.loads(meta.read_text()).get(
            "built_utc", "unknown"
        )
    return version


def git_state(root: Path = ROOT) -> dict[str, str]:
    """Short commit hash and whether tracked files have uncommitted changes."""

    def run(*args: str) -> str | None:
        try:
            out = subprocess.run(
                ["git", *args], cwd=root, capture_output=True, text=True, check=True
            )
        except (OSError, subprocess.CalledProcessError):
            return None
        return out.stdout.strip()

    commit = run("rev-parse", "--short", "HEAD")
    dirty = run("status", "--porcelain", "--untracked-files=no")
    return {
        "git.commit": commit or "unknown",
        "git.dirty": "unknown" if dirty is None else str(bool(dirty)).lower(),
    }


def environment() -> dict[str, str]:
    return {
        "env.python": platform.python_version(),
        "env.numpy": np.__version__,
        "env.pandas": pd.__version__,
        "env.sklearn": sklearn.__version__,
    }


def setup(tracking_dir: Path = TRACKING_DIR, experiment: str = EXPERIMENT) -> str:
    """Point MLflow at the local SQLite store and make sure the experiment exists."""
    tracking_dir.mkdir(parents=True, exist_ok=True)
    mlflow.set_tracking_uri(f"sqlite:///{tracking_dir / 'mlflow.db'}")
    existing = mlflow.get_experiment_by_name(experiment)
    if existing is not None:
        mlflow.set_experiment(experiment)
        return existing.experiment_id
    experiment_id = mlflow.create_experiment(
        experiment, artifact_location=(tracking_dir / "artifacts").as_uri()
    )
    mlflow.set_experiment(experiment)
    return experiment_id


class Run:
    """Handle for logging results inside ``tracked_run``."""

    def log_metrics(self, metrics: dict, prefix: str = "") -> None:
        """Log numbers, skipping missing values. Names are joined to ``prefix`` with a slash."""
        for name, value in metrics.items():
            if value is None or (isinstance(value, float) and math.isnan(value)):
                continue
            if isinstance(value, bool | np.bool_):
                value = float(value)
            mlflow.log_metric(f"{prefix}/{name}" if prefix else name, float(value))

    def log_predictions(
        self, frame: pd.DataFrame, name: str = "predictions.csv"
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / name
            frame.to_csv(path, index=False)
            mlflow.log_artifact(str(path))


@contextmanager
def tracked_run(
    name: str,
    params: dict,
    seed: int,
    split: dict,
    features: list[str],
    tags: dict | None = None,
    tracking_dir: Path = TRACKING_DIR,
    processed_dir: Path = PROCESSED,
    experiment: str = EXPERIMENT,
) -> Iterator[Run]:
    """Start an MLflow run that records the configuration, data version and code version."""
    setup(tracking_dir, experiment)
    with mlflow.start_run(run_name=name):
        mlflow.log_params(
            {
                **scrub(params),
                "seed": str(seed),
                **scrub(split, prefix="split."),
                "n_features": str(len(features)),
            }
        )
        mlflow.set_tags(
            {
                **git_state(),
                **data_version(processed_dir),
                **environment(),
                **scrub(tags or {}),
            }
        )
        mlflow.log_dict({"features": list(features)}, "features.json")
        yield Run()
