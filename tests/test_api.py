import pandas as pd
import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient

from aeron import forecast
from aeron.api.app import create_app
from aeron.api.settings import Settings
from aeron.config import ROOT
from tests.test_forecast import small_forest
from tests.test_models_baselines import synthetic_daily

CUTOFF = "2024-12-31"


@pytest.fixture(scope="module")
def paths(tmp_path_factory):
    base = tmp_path_factory.mktemp("api")
    daily = synthetic_daily(n=1700)
    csv = base / "daily.csv"
    daily.to_csv(csv)
    models = {
        lead: forecast.train_final(daily, lead, small_forest, cutoff=CUTOFF)
        for lead in forecast.LEADS
    }
    model_dir = forecast.save(
        models, base / "models", ROOT, csv, tag="replay", cutoff=CUTOFF
    )
    return daily, csv, model_dir


@pytest.fixture(scope="module")
def client(paths):
    _, csv, model_dir = paths
    app = create_app(Settings(daily_csv=csv, model_dir=model_dir))
    with TestClient(app) as c:
        yield c


def test_health_and_station(client):
    h = client.get("/health").json()
    assert h == {
        "status": "ok",
        "data_loaded": True,
        "model_loaded": True,
        "detail": [],
    }
    s = client.get("/api/v1/station").json()
    assert s["openaq_location_id"] == 8881 and "reference" in s["quality"]


def test_replay_range_starts_after_the_training_cutoff(client):
    r = client.get("/api/v1/replay/range").json()
    assert r["mode"] == "replay"
    assert r["first_origin"] == "2025-01-01"
    assert pd.Timestamp(r["last_origin"]) > pd.Timestamp(r["first_origin"])


def test_forecast_shape_and_labelling(client):
    r = client.get("/api/v1/forecast", params={"origin": "2025-03-01"})
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] == "replay" and "not a current forecast" in body["notice"]
    assert [f["lead_days"] for f in body["forecasts"]] == [1, 2, 3]
    for f in body["forecasts"]:
        lo, hi = f["interval_90"]
        assert lo <= f["forecast"] <= hi
        assert f["observed"] is not None
        assert f["observed_inside_90"] == (lo <= f["observed"] <= hi)
        assert 0 <= f["probability_at_least_55_5"]["conformal"] <= 1
    assert body["forecasts"][0]["target_date"] == "2025-03-02"


def test_origins_outside_the_replay_range_are_refused(client):
    for day in ("2024-12-31", "2019-01-01", "2030-01-01"):
        r = client.get("/api/v1/forecast", params={"origin": day})
        assert r.status_code == 404
        assert "first_origin" in r.json()["detail"]


def test_bad_input_gets_422(client):
    assert (
        client.get("/api/v1/forecast", params={"origin": "tomorrow"}).status_code == 422
    )
    assert client.get("/api/v1/forecast").status_code == 422
    assert (
        client.get(
            "/api/v1/history", params={"start": "2025-02-01", "end": "2025-01-01"}
        ).status_code
        == 422
    )
    assert (
        client.get(
            "/api/v1/history", params={"start": "2020-01-01", "end": "2025-01-01"}
        ).status_code
        == 422
    )


def test_history_returns_values_and_nulls(client, paths):
    daily, _, _ = paths
    r = client.get(
        "/api/v1/history", params={"start": "2025-01-01", "end": "2025-01-05"}
    ).json()
    assert len(r["points"]) == 5 and r["unit"] == "ug/m3"
    assert r["points"][0]["pm25_mean"] == pytest.approx(
        daily.loc["2025-01-01", "pm25_mean"], abs=0.06
    )
    far = client.get(
        "/api/v1/history", params={"start": "2035-01-01", "end": "2035-01-02"}
    ).json()
    assert [p["pm25_mean"] for p in far["points"]] == [None, None]


def test_model_info_has_card_and_limits(client):
    card = client.get("/api/v1/model").json()
    assert card["training_cutoff"] == CUTOFF
    assert card["known_limits"]


def test_forecast_does_not_depend_on_data_after_the_origin(paths, tmp_path):
    daily, csv, model_dir = paths
    changed = daily.copy()
    changed.loc[changed.index > "2025-03-01", "pm25_mean"] = 777.0
    csv2 = tmp_path / "changed.csv"
    changed.to_csv(csv2)
    values = []
    for path in (csv, csv2):
        with TestClient(create_app(Settings(daily_csv=path, model_dir=model_dir))) as c:
            r = c.get("/api/v1/forecast", params={"origin": "2025-03-01"}).json()
            values.append(
                [(f["forecast"], tuple(f["interval_90"])) for f in r["forecasts"]]
            )
    assert values[0] == values[1]


def test_service_reports_missing_data_and_model(tmp_path):
    app = create_app(
        Settings(
            daily_csv=tmp_path / "nope.csv",
            model_dir=tmp_path / "nomodel",
            models_root=tmp_path,
        )
    )
    with TestClient(app) as c:
        h = c.get("/health").json()
        assert h["status"] == "degraded" and len(h["detail"]) == 2
        r = c.get("/api/v1/forecast", params={"origin": "2025-03-01"})
        assert r.status_code == 503
        assert (
            c.get(
                "/api/v1/history", params={"start": "2025-01-01", "end": "2025-01-02"}
            ).status_code
            == 503
        )
        assert c.get("/openapi.json").status_code == 200
