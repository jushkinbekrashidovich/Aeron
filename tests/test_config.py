import pytest

from aeron import config


def test_config_loads_and_has_primary_series():
    series = config.openaq_series()
    primary = [s for s in series if s.primary]
    assert len(primary) == 1
    assert primary[0].name == "us_embassy_pm25"
    assert primary[0].sensor_id == 25916
    assert all(s.start >= "2018-01-01" for s in series)


def test_target_settings():
    cfg = config.load_config()
    assert cfg["target"]["lead_days"] == [1, 2, 3]
    assert (
        cfg["target"]["primary_threshold_ugm3"]
        in cfg["target"]["event_thresholds_ugm3"]
    )
    assert cfg["time"]["utc_offset_hours"] == 5


def test_series_names_and_ids_are_unique():
    series = config.openaq_series()
    assert len({s.name for s in series}) == len(series)
    assert len({s.sensor_id for s in series}) == len(series)


def test_forecast_variables_have_leads_covering_all_target_days():
    cfg = config.load_config()
    leads = cfg["target"]["lead_days"]
    previous = cfg["openmeteo"]["forecast"]["previous_days"]
    assert previous == [
        k + 1 for k in leads
    ]  # lead k uses the forecast issued k + 1 days earlier


def test_secret_from_environment(monkeypatch, tmp_path):
    monkeypatch.setenv("AERON_TEST_KEY", "from-env")
    assert config.get_secret("AERON_TEST_KEY", root=tmp_path) == "from-env"


def test_secret_from_env_file(monkeypatch, tmp_path):
    monkeypatch.delenv("AERON_TEST_KEY", raising=False)
    (tmp_path / ".env").write_text("# comment\nAERON_TEST_KEY='from-file'\n")
    assert config.get_secret("AERON_TEST_KEY", root=tmp_path) == "from-file"


def test_missing_secret_raises_without_leaking(monkeypatch, tmp_path):
    monkeypatch.delenv("AERON_TEST_KEY", raising=False)
    with pytest.raises(RuntimeError) as err:
        config.get_secret("AERON_TEST_KEY", root=tmp_path)
    assert "AERON_TEST_KEY" in str(err.value)


def test_empty_secret_is_treated_as_missing(monkeypatch, tmp_path):
    monkeypatch.delenv("AERON_TEST_KEY", raising=False)
    (tmp_path / ".env").write_text("AERON_TEST_KEY=\n")
    with pytest.raises(RuntimeError):
        config.get_secret("AERON_TEST_KEY", root=tmp_path)


def test_env_example_has_no_secret_values():
    values = config.read_env_file(config.ROOT / ".env.example")
    assert "OPENAQ_API_KEY" in values
    assert values["OPENAQ_API_KEY"] == ""
