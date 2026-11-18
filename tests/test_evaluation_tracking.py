import json

import pandas as pd
import pytest

pytest.importorskip("mlflow")
import mlflow

from aeron.evaluation import tracking


@pytest.fixture
def workspace(tmp_path):
    processed = tmp_path / "processed"
    processed.mkdir()
    (processed / "daily_us_embassy.csv").write_text("date,pm25_mean\n2024-01-01,10\n")
    (processed / "hourly_us_embassy.csv").write_text(
        "datetime_utc,pm25\n2024-01-01T00:00:00Z,10\n"
    )
    (processed / "metadata.json").write_text(
        json.dumps({"built_utc": "2026-01-01T00:00:00+00:00"})
    )
    yield tmp_path / "mlruns", processed
    mlflow.set_tracking_uri("")  # do not leave the test store active


def fetch(tracking_dir):
    client = mlflow.tracking.MlflowClient()
    experiment = client.get_experiment_by_name(tracking.EXPERIMENT)
    return client, client.search_runs([experiment.experiment_id])


def test_run_records_configuration_code_and_data_versions(workspace):
    tracking_dir, processed = workspace
    with tracking.tracked_run(
        "gbm-lead1",
        params={"model": "gbm", "settings": {"depth": 4, "api_key": "SECRET123"}},
        seed=0,
        split={"scheme": "walk-forward", "gap_days": 1},
        features=["pm_lag1", "wind"],
        tags={"note": "test"},
        tracking_dir=tracking_dir,
        processed_dir=processed,
    ) as run:
        run.log_metrics(
            {"mae": 15.5, "rmse": float("nan"), "n": 120}, prefix="winter/lead1"
        )
    client, runs = fetch(tracking_dir)
    assert len(runs) == 1
    r = runs[0]
    assert r.data.params["model"] == "gbm" and r.data.params["settings.depth"] == "4"
    assert r.data.params["seed"] == "0" and r.data.params["split.gap_days"] == "1"
    assert r.data.params["n_features"] == "2"
    assert (
        "SECRET123" not in json.dumps(r.data.params)
        and "settings.api_key" not in r.data.params
    )
    assert r.data.metrics["winter/lead1/mae"] == 15.5
    assert "winter/lead1/rmse" not in r.data.metrics  # missing values are not logged
    for tag in (
        "git.commit",
        "git.dirty",
        "data.daily_sha256",
        "data.built_utc",
        "env.python",
        "env.sklearn",
        "note",
    ):
        assert tag in r.data.tags
    assert r.data.tags["data.built_utc"] == "2026-01-01T00:00:00+00:00"
    artifacts = [a.path for a in client.list_artifacts(r.info.run_id)]
    assert "features.json" in artifacts


def test_predictions_are_saved_as_an_artifact(workspace):
    tracking_dir, processed = workspace
    frame = pd.DataFrame({"target_day": ["2024-01-02"], "y": [10.0], "pred": [12.0]})
    with tracking.tracked_run(
        "r", {}, 1, {}, [], tracking_dir=tracking_dir, processed_dir=processed
    ) as run:
        run.log_predictions(frame)
    client, runs = fetch(tracking_dir)
    assert "predictions.csv" in [
        a.path for a in client.list_artifacts(runs[0].info.run_id)
    ]


def test_data_version_changes_when_data_changes(workspace):
    _, processed = workspace
    before = tracking.data_version(processed)
    (processed / "daily_us_embassy.csv").write_text("date,pm25_mean\n2024-01-01,11\n")
    after = tracking.data_version(processed)
    assert before["data.daily_sha256"] != after["data.daily_sha256"]
    assert before["data.hourly_sha256"] == after["data.hourly_sha256"]
    assert (
        tracking.data_version(processed / "nowhere")["data.daily_sha256"] == "missing"
    )


def test_scrub_drops_secrets_and_flattens():
    out = tracking.scrub(
        {
            "a": 1,
            "nested": {"b": 2, "openaq_api_key": "x", "Token": "y"},
            "password": "z",
        }
    )
    assert out == {"a": "1", "nested.b": "2"}


def test_experiment_is_created_once(workspace):
    tracking_dir, _ = workspace
    first = tracking.setup(tracking_dir)
    second = tracking.setup(tracking_dir)
    assert first == second
