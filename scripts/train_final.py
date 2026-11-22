"""Train the headline model for every lead and save it under artifacts/models/.

Usage:
    python scripts/train_final.py

Needs data/processed/daily_us_embassy.csv (scripts/build_dataset.py). Writes
artifacts/models/<version>/lead{1,2,3}.joblib and model_card.json. The artifacts folder
is not committed.
"""

from __future__ import annotations

import json

import pandas as pd

from aeron import forecast
from aeron.config import ROOT

DAILY = ROOT / "data" / "processed" / "daily_us_embassy.csv"
OUT = ROOT / "artifacts" / "models"
EVAL = ROOT / "reports" / "model_evaluation"


def evaluation_summary() -> dict | None:
    """Winter test results of the headline model, read from the committed report tables."""
    path = EVAL / "model_comparison_metrics.csv"
    if not path.exists():
        return None
    table = pd.read_csv(path)
    rows = table[(table["model"] == forecast.MODEL_NAME) & (table["group"] == "winter")]
    out = {}
    for _, r in rows.iterrows():
        out.setdefault(r["view"], {})[f"lead{int(r['lead'])}"] = {
            "n": int(r["n"]),
            "mae": float(r["mae"]),
            "rmse": float(r["rmse"]),
            "bias": float(r["bias"]),
        }
    return {
        "winter_test_error": out,
        "source": "reports/model_evaluation/model_comparison_metrics.csv",
    }


def main() -> None:
    daily = pd.read_csv(DAILY, index_col=0, parse_dates=True)
    models = {lead: forecast.train_final(daily, lead) for lead in forecast.LEADS}
    path = forecast.save(models, OUT, ROOT, DAILY, evaluation_summary())
    card = json.loads((path / "model_card.json").read_text())
    print(f"saved {path}")
    print(
        json.dumps(
            {
                k: card[k]
                for k in ("version", "last_training_target_date", "git_commit")
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
