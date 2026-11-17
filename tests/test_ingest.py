import copy
import json
import urllib.error
import urllib.parse
from datetime import date, timedelta
from pathlib import Path

import pytest

from aeron.config import Series
from aeron.ingest import files, openaq, openmeteo
from aeron.ingest.http import Client

FIXTURES = Path(__file__).parent / "fixtures"
SECRET = "SECRET-KEY-123"


def http_error(code, retry_after=None):
    headers = {"Retry-After": str(retry_after)} if retry_after is not None else {}
    return urllib.error.HTTPError("http://x", code, "err", headers, None)


def query(url):
    return {
        k: v[0]
        for k, v in urllib.parse.parse_qs(urllib.parse.urlparse(url).query).items()
    }


# --------------------------------------------------------------------------
# HTTP client
# --------------------------------------------------------------------------
def test_client_retries_then_succeeds_and_honours_retry_after():
    calls, sleeps = [], []
    outcomes = [
        http_error(429, retry_after=2),
        urllib.error.URLError("down"),
        {"ok": 1},
    ]

    def transport(url, headers, timeout):
        calls.append(url)
        outcome = outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    client = Client({"X-API-Key": SECRET}, transport, backoff=5.0, sleep=sleeps.append)
    assert client.get_json("http://x/api", {"a": 1}) == {"ok": 1}
    assert len(calls) == 3
    assert calls[0] == "http://x/api?a=1"
    assert sleeps == [2.0, 10.0]  # Retry-After first, then backoff * attempt number


def test_client_does_not_retry_client_errors():
    def transport(url, headers, timeout):
        raise http_error(401)

    client = Client(transport=transport, sleep=lambda s: None)
    with pytest.raises(urllib.error.HTTPError):
        client.get_json("http://x")
    assert client.requests_made == 1


def test_client_gives_up_without_leaking_headers():
    def transport(url, headers, timeout):
        raise http_error(503)

    client = Client({"X-API-Key": SECRET}, transport, retries=3, sleep=lambda s: None)
    with pytest.raises(RuntimeError) as err:
        client.get_json("http://x")
    assert SECRET not in str(err.value)
    assert client.requests_made == 3


# --------------------------------------------------------------------------
# File helpers
# --------------------------------------------------------------------------
def test_month_ranges_cross_year():
    months = files.month_ranges(date(2024, 11, 15), date(2025, 2, 3))
    assert months[0] == (date(2024, 11, 1), date(2024, 12, 1))
    assert months[1] == (date(2024, 12, 1), date(2025, 1, 1))
    assert months[-1] == (date(2025, 2, 1), date(2025, 3, 1))
    assert len(months) == 4


def test_is_final_refresh_window():
    today = date(2025, 6, 15)
    assert files.is_final(date(2025, 5, 1), today)  # exactly 45 days back
    assert not files.is_final(date(2025, 5, 2), today)


def test_write_rows_is_atomic(tmp_path):
    path = tmp_path / "a" / "x.csv"
    files.write_rows(path, ["a", "b"], [[1, 2]])
    assert files.read_rows(path) == (["a", "b"], [["1", "2"]])
    assert not list(path.parent.glob("*.tmp"))


# --------------------------------------------------------------------------
# OpenAQ
# --------------------------------------------------------------------------
ITEM = json.loads((FIXTURES / "openaq_hours_item.json").read_text())


def make_item(stamp, value):
    item = copy.deepcopy(ITEM)
    item["value"] = value
    item["period"]["datetimeFrom"]["utc"] = stamp
    return item


class FakeOpenAQ:
    """Serves one reading per day at 00:00 UTC within the requested window."""

    def __init__(self, fail_after=None):
        self.calls = []
        self.fail_after = fail_after

    def __call__(self, url, headers, timeout):
        if self.fail_after is not None and len(self.calls) >= self.fail_after:
            raise urllib.error.URLError("connection lost")
        self.calls.append(url)
        q = query(url)
        start = date.fromisoformat(q["datetime_from"][:10])
        end = date.fromisoformat(q["datetime_to"][:10])
        days = [start + timedelta(days=i) for i in range((end - start).days)]
        limit, page = int(q["limit"]), int(q["page"])
        chunk = days[(page - 1) * limit : page * limit]
        results = [
            make_item(
                f"{d.isoformat()}T00:00:00Z", None if d.day == 2 else float(d.day)
            )
            for d in chunk
        ]
        return {"meta": {"page": page, "limit": limit}, "results": results}


CFG = {
    "openaq": {
        "api_url": "https://api.test/v3",
        "page_limit": 10,
        "request_pause_seconds": 0,
    }
}
SERIES = Series("test_pm25", 1, 99, "pm25", "2025-01-01", "reference", True)


def run_series(tmp_path, transport, today=date(2025, 6, 15)):
    client = Client({"X-API-Key": SECRET}, transport, sleep=lambda s: None)
    result = openaq.download_series(
        SERIES, client, CFG, tmp_path, today, sleep=lambda s: None, log=lambda m: None
    )
    return result, client


def test_parse_results_missing_value_is_empty():
    rows = openaq.parse_results(
        [
            make_item("2020-01-01T00:00:00Z", None),
            make_item("2020-01-01T01:00:00Z", 36.0),
        ]
    )
    assert rows[0] == ["2020-01-01T00:00:00Z", "", 100.0, 1, 1]
    assert rows[1][1] == 36.0


def test_fetch_month_follows_pagination():
    fake = FakeOpenAQ()
    client = Client(transport=fake, sleep=lambda s: None)
    rows = openaq.fetch_month(
        client,
        "https://api.test/v3",
        99,
        date(2025, 1, 1),
        date(2025, 2, 1),
        10,
        0,
        lambda s: None,
    )
    assert len(rows) == 31
    assert len(fake.calls) == 4  # pages of 10, 10, 10, 1
    assert [query(c)["page"] for c in fake.calls] == ["1", "2", "3", "4"]


def test_download_series_writes_merged_file(tmp_path):
    result, _ = run_series(tmp_path, FakeOpenAQ())
    header, rows = files.read_rows(tmp_path / "test_pm25_hourly.csv")
    assert header == openaq.COLUMNS
    stamps = [r[0] for r in rows]
    assert stamps == sorted(stamps) and len(stamps) == len(set(stamps))
    assert result["rows"] == len(rows)
    assert rows[1][1] == ""  # 2025-01-02 has a missing value
    assert not list(tmp_path.rglob("*.tmp"))


def test_second_run_only_refreshes_recent_months(tmp_path):
    first, _ = run_series(tmp_path, FakeOpenAQ())
    assert first["months_fetched"] == 6 and first["months_skipped"] == 0
    before = (tmp_path / "test_pm25_hourly.csv").read_text()
    fake = FakeOpenAQ()
    second, _ = run_series(tmp_path, fake)
    # Jan to Apr are final (end on or before 2025-05-01); May and June are refreshed.
    assert second["months_skipped"] == 4 and second["months_fetched"] == 2
    assert (tmp_path / "test_pm25_hourly.csv").read_text() == before  # idempotent


def test_interrupted_run_resumes(tmp_path):
    crashing = FakeOpenAQ(
        fail_after=5
    )  # January needs 4 requests, so February is cut off
    client = Client(transport=crashing, retries=1, sleep=lambda s: None)
    with pytest.raises(RuntimeError):
        openaq.download_series(
            SERIES,
            client,
            CFG,
            tmp_path,
            date(2025, 6, 15),
            lambda s: None,
            lambda m: None,
        )
    done = sorted(p.name for p in (tmp_path / "_months" / "test_pm25").glob("*.csv"))
    assert done == ["2025-01.csv"]  # February was cut off, so no partial file
    healthy = FakeOpenAQ()
    result, _ = run_series(tmp_path, healthy)
    assert result["months_skipped"] == 1 and result["months_fetched"] == 5
    full = tmp_path / "again"
    run_series(full, FakeOpenAQ())
    assert (tmp_path / "test_pm25_hourly.csv").read_text() == (
        full / "test_pm25_hourly.csv"
    ).read_text()


def test_seed_from_existing_skips_final_months(tmp_path):
    run_series(tmp_path, FakeOpenAQ())
    merged = (tmp_path / "test_pm25_hourly.csv").read_text()
    import shutil

    shutil.rmtree(tmp_path / "_months")
    today = date(2025, 6, 15)
    written = openaq.seed_from_existing(SERIES, tmp_path, today)
    assert written == 4  # January to April
    assert openaq.seed_from_existing(SERIES, tmp_path, today) == 0  # not repeated
    fake = FakeOpenAQ()
    result, _ = run_series(tmp_path, fake)
    assert result["months_fetched"] == 2
    assert (tmp_path / "test_pm25_hourly.csv").read_text() == merged


def test_run_updates_metadata(tmp_path):
    cfg = {
        "openaq": CFG["openaq"] | {"series": [SERIES.__dict__]},
    }
    client = Client(transport=FakeOpenAQ(), sleep=lambda s: None)
    meta = openaq.run(
        cfg,
        tmp_path,
        date(2025, 6, 15),
        client,
        sleep=lambda s: None,
        log=lambda m: None,
    )
    assert meta["files"]["test_pm25"]["sensor_id"] == 99
    assert SECRET not in json.dumps(meta)
    assert (tmp_path / "metadata.json").exists()


# --------------------------------------------------------------------------
# Open-Meteo
# --------------------------------------------------------------------------
HOURLY = json.loads((FIXTURES / "openmeteo_hourly.json").read_text())


class FakeOpenMeteo:
    def __init__(self):
        self.calls = []

    def __call__(self, url, headers, timeout):
        self.calls.append(url)
        q = query(url)
        start, end = (
            date.fromisoformat(q["start_date"]),
            date.fromisoformat(q["end_date"]),
        )
        variables = q["hourly"].split(",")
        times = []
        day = start
        while day <= end:
            times += [f"{day.isoformat()}T{h:02d}:00" for h in range(24)]
            day += timedelta(days=1)
        hourly = {"time": times}
        for k, v in enumerate(variables):
            hourly[v] = [
                None if (i == 3 and k == 0) else float(k * 1000 + i)
                for i in range(len(times))
            ]
        return {"hourly": hourly}


OM_CFG = {
    "openmeteo": {
        "latitude": 41.4,
        "longitude": 69.3,
        "archive_url": "https://archive.test/v1/archive",
        "previous_runs_url": "https://runs.test/v1/forecast",
        "era5_start": "2023-11-01",
        "era5_end_lag_days": 7,
        "core_variables": ["temperature_2m", "wind_speed_10m"],
        "extra_variables": ["pressure_msl"],
        "forecast": {
            "start": "2024-01-19",
            "end": "2024-04-30",
            "previous_days": [2, 3],
            "chunk_days": 45,
            "variables": ["temperature_2m", "wind_speed_10m"],
        },
    }
}


def test_fetch_hourly_uses_fixture_shape_and_blanks_nulls():
    client = Client(transport=lambda u, h, t: HOURLY, sleep=lambda s: None)
    rows = openmeteo.fetch_hourly(
        client,
        "http://x",
        41.4,
        69.3,
        date(2020, 1, 1),
        date(2020, 1, 1),
        ["temperature_2m", "wind_speed_10m"],
    )
    assert rows[0] == ["2020-01-01T00:00:00Z", 1.5, 3.0]
    assert rows[1][1] == ""


def test_blocks():
    assert openmeteo.year_blocks(date(2023, 11, 1), date(2025, 2, 3)) == [
        (date(2023, 11, 1), date(2023, 12, 31)),
        (date(2024, 1, 1), date(2024, 12, 31)),
        (date(2025, 1, 1), date(2025, 2, 3)),
    ]
    blocks = openmeteo.day_blocks(date(2024, 1, 19), date(2024, 3, 31), 45)
    assert blocks[0] == (date(2024, 1, 19), date(2024, 3, 3))
    assert blocks[1] == (date(2024, 3, 4), date(2024, 3, 31))


def test_era5_split_into_core_and_extra_and_idempotent(tmp_path):
    today = date(2025, 6, 15)
    fake = FakeOpenMeteo()
    client = Client(transport=fake, sleep=lambda s: None)
    result = openmeteo.run(
        OM_CFG,
        tmp_path,
        today,
        client,
        which=("era5",),
        sleep=lambda s: None,
        log=lambda m: None,
    )
    core_h, core = files.read_rows(tmp_path / "era5_tashkent_hourly.csv")
    extra_h, extra = files.read_rows(tmp_path / "era5_extra_tashkent_hourly.csv")
    assert core_h == ["datetime_utc", "temperature_2m", "wind_speed_10m"]
    assert extra_h == ["datetime_utc", "pressure_msl"]
    assert len(core) == len(extra) == result["era5"]["rows"]
    assert [r[0] for r in core] == [r[0] for r in extra]
    assert core[3][1] == ""  # null stays empty
    assert len(fake.calls) == 3  # 2023, 2024, 2025
    before = (tmp_path / "era5_tashkent_hourly.csv").read_text()
    second = FakeOpenMeteo()
    openmeteo.run(
        OM_CFG,
        tmp_path,
        today,
        Client(transport=second, sleep=lambda s: None),
        which=("era5",),
        sleep=lambda s: None,
        log=lambda m: None,
    )
    assert len(second.calls) == 1  # only the current year is fetched again
    assert (tmp_path / "era5_tashkent_hourly.csv").read_text() == before
    meta = json.loads((tmp_path / "metadata.json").read_text())
    assert meta["variables"] == ["temperature_2m", "wind_speed_10m"]
    assert meta["end"] == "2025-06-08"


def test_forecast_columns_and_merge(tmp_path):
    today = date(2025, 6, 15)
    fake = FakeOpenMeteo()
    openmeteo.run(
        OM_CFG,
        tmp_path,
        today,
        Client(transport=fake, sleep=lambda s: None),
        which=("forecast",),
        sleep=lambda s: None,
        log=lambda m: None,
    )
    header, rows = files.read_rows(tmp_path / "forecast_previous_runs_hourly.csv")
    assert header == [
        "datetime_utc",
        "temperature_2m_previous_day2",
        "wind_speed_10m_previous_day2",
        "temperature_2m_previous_day3",
        "wind_speed_10m_previous_day3",
    ]
    assert (
        rows[0][0] == "2024-01-19T00:00:00Z" and rows[-1][0] == "2024-04-30T23:00:00Z"
    )
    stamps = [r[0] for r in rows]
    assert len(stamps) == len(set(stamps)) == 103 * 24
    assert len(fake.calls) == 3  # 45-day blocks
    second = FakeOpenMeteo()
    openmeteo.run(
        OM_CFG,
        tmp_path,
        today,
        Client(transport=second, sleep=lambda s: None),
        which=("forecast",),
        sleep=lambda s: None,
        log=lambda m: None,
    )
    assert second.calls == []  # all blocks are final


def test_changed_variables_in_cache_are_detected(tmp_path):
    cache = tmp_path / "c"
    files.write_rows(cache / "a.csv", ["datetime_utc", "x"], [["t", 1]])
    files.write_rows(cache / "b.csv", ["datetime_utc", "y"], [["u", 2]])
    with pytest.raises(ValueError):
        openmeteo.merge_cache(cache)


def test_seed_era5_avoids_downloads(tmp_path):
    today = date(2025, 6, 15)
    openmeteo.run(
        OM_CFG,
        tmp_path,
        today,
        Client(transport=FakeOpenMeteo(), sleep=lambda s: None),
        which=("era5",),
        sleep=lambda s: None,
        log=lambda m: None,
    )
    import shutil

    shutil.rmtree(tmp_path / "_cache")
    assert openmeteo.seed_era5(OM_CFG, tmp_path, today) == 2  # 2023 and 2024 are final
    fake = FakeOpenMeteo()
    openmeteo.run(
        OM_CFG,
        tmp_path,
        today,
        Client(transport=fake, sleep=lambda s: None),
        which=("era5",),
        sleep=lambda s: None,
        log=lambda m: None,
    )
    assert len(fake.calls) == 1
