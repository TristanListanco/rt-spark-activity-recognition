from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from fake_data import FakeStore
from server import create_app

NOW_S = 1_761_800_000  # fixed clock so results are deterministic
MANILA = ZoneInfo("Asia/Manila")


def fixed_clock() -> float:
    return NOW_S


@pytest.fixture
def client():
    app = create_app(store=FakeStore(fixed_clock), clock=fixed_clock)
    return app.test_client()


def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_latest_matches_contract(client):
    body = client.get("/api/latest?device_id=rtspark-01").get_json()
    assert set(body) == {"device_id", "activity", "confidence", "ts"}
    assert body["device_id"] == "rtspark-01"
    assert body["activity"] in {"walk", "run"}
    assert 0.0 <= body["confidence"] <= 1.0
    assert body["ts"] == NOW_S * 1000


def test_device_id_is_required(client):
    for path in ("/api/latest", "/api/history", "/api/summary"):
        response = client.get(path)
        assert response.status_code == 400
        assert response.get_json() == {"error": "device_id is required"}


def test_history_default_limit_newest_first(client):
    rows = client.get("/api/history?device_id=rtspark-01").get_json()
    assert len(rows) == 50
    assert all(set(row) == {"activity", "confidence", "ts"} for row in rows)
    timestamps = [row["ts"] for row in rows]
    assert timestamps == sorted(timestamps, reverse=True)
    assert timestamps[0] == NOW_S * 1000


def test_history_before_is_exclusive(client):
    before = (NOW_S - 10) * 1000
    rows = client.get(f"/api/history?device_id=rtspark-01&limit=5&before={before}").get_json()
    assert len(rows) == 5
    assert all(row["ts"] < before for row in rows)
    assert rows[0]["ts"] == before - 1000


@pytest.mark.parametrize("query", ["limit=0", "limit=501", "limit=abc", "before=-1", "before=x"])
def test_history_rejects_bad_params(client, query):
    response = client.get(f"/api/history?device_id=rtspark-01&{query}")
    assert response.status_code == 400
    assert "error" in response.get_json()


def test_summary_full_past_day(client):
    body = client.get("/api/summary?device_id=rtspark-01&date=2025-01-15").get_json()
    assert body == {"date": "2025-01-15", "seconds": {"walk": 43200, "run": 43200}}


def test_summary_today_counts_up_to_now(client):
    today = datetime.fromtimestamp(NOW_S, MANILA).date()
    body = client.get("/api/summary?device_id=rtspark-01").get_json()
    midnight = datetime.combine(today, datetime.min.time(), MANILA).timestamp()
    assert body["date"] == today.isoformat()
    assert sum(body["seconds"].values()) == NOW_S - int(midnight)


def test_summary_rejects_bad_date(client):
    response = client.get("/api/summary?device_id=rtspark-01&date=31-10-2026")
    assert response.status_code == 400


def test_unknown_route_returns_json_error(client):
    response = client.get("/api/nope")
    assert response.status_code == 404
    assert "error" in response.get_json()
