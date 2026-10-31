import os
from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import psycopg
import pytest

from server import create_app
from store import PostgresStore

DATABASE_URL = os.environ.get("DATABASE_URL")
INIT_SQL = (Path(__file__).resolve().parents[2] / "db" / "init.sql").read_text()
MANILA = ZoneInfo("Asia/Manila")
NOW = datetime(2026, 10, 31, 12, 0, 0, tzinfo=MANILA)  # fixed clock for "today"

needs_db = pytest.mark.skipif(not DATABASE_URL, reason="needs DATABASE_URL (PostgreSQL)")


def ms(dt: datetime) -> int:
    return round(dt.timestamp() * 1000)


@pytest.fixture
def db():
    with psycopg.connect(DATABASE_URL, autocommit=True) as conn:
        conn.execute("DROP TABLE IF EXISTS predictions")
        conn.execute(INIT_SQL)
        yield conn


def insert(db, device: str, when: datetime, activity: str, confidence: float = 0.9) -> None:
    db.execute(
        "INSERT INTO predictions (device_id, ts, activity, confidence) VALUES (%s, %s, %s, %s)",
        (device, when, activity, confidence),
    )


@pytest.fixture
def client(db):
    app = create_app(store=PostgresStore(DATABASE_URL), clock=NOW.timestamp)
    return app.test_client()


@needs_db
def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_database_down_returns_503():
    app = create_app(store=PostgresStore("host=127.0.0.1 port=1 connect_timeout=1"))
    client = app.test_client()
    for path in ("/api/health", "/api/latest?device_id=x"):
        response = client.get(path)
        assert response.status_code == 503
        assert response.get_json() == {"error": "database unavailable"}


@needs_db
def test_latest_404_without_data(client):
    response = client.get("/api/latest?device_id=rtspark-01")
    assert response.status_code == 404
    assert response.get_json() == {"error": "no data"}


@needs_db
def test_latest_returns_newest_for_device(client, db):
    t = datetime(2026, 10, 31, 4, 0, 0, 250_000, tzinfo=UTC)
    insert(db, "rtspark-01", t, "walk", 0.81)
    insert(db, "rtspark-01", t.replace(second=1), "run", 0.97)
    insert(db, "other", t.replace(second=5), "walk")
    body = client.get("/api/latest?device_id=rtspark-01").get_json()
    assert body == {
        "device_id": "rtspark-01",
        "activity": "run",
        "confidence": 0.97,
        "ts": ms(t.replace(second=1)),
    }


@needs_db
def test_history_newest_first_with_limit_and_before(client, db):
    base = datetime(2026, 10, 31, 4, 0, 0, tzinfo=UTC)
    for s in range(10):
        insert(db, "rtspark-01", base.replace(second=s), "walk" if s < 5 else "run")
    rows = client.get("/api/history?device_id=rtspark-01&limit=3").get_json()
    assert [r["ts"] for r in rows] == [ms(base.replace(second=s)) for s in (9, 8, 7)]
    assert all(set(r) == {"activity", "confidence", "ts"} for r in rows)

    before = rows[-1]["ts"]  # next page starts strictly before the last row shown
    page = client.get(f"/api/history?device_id=rtspark-01&limit=3&before={before}").get_json()
    assert [r["ts"] for r in page] == [ms(base.replace(second=s)) for s in (6, 5, 4)]


@needs_db
def test_history_default_limit_is_50(client, db):
    base = datetime(2026, 10, 31, 4, 0, 0, tzinfo=UTC)
    for s in range(60):
        insert(db, "rtspark-01", base.replace(minute=s // 60, second=s % 60), "walk")
    assert len(client.get("/api/history?device_id=rtspark-01").get_json()) == 50


@needs_db
def test_summary_counts_seconds_within_the_local_day(client, db):
    day_start = datetime(2026, 10, 31, 0, 0, 0, tzinfo=MANILA)
    insert(db, "rtspark-01", day_start.replace(day=30, hour=23, minute=59, second=59), "run")
    insert(db, "rtspark-01", day_start, "walk")
    insert(db, "rtspark-01", day_start.replace(hour=8), "walk")
    insert(db, "rtspark-01", day_start.replace(hour=9), "run")
    insert(db, "rtspark-01", day_start.replace(day=31, hour=23, minute=59, second=59), "run")
    insert(db, "rtspark-01", day_start.replace(month=11, day=1), "walk")
    insert(db, "other", day_start.replace(hour=10), "walk")

    body = client.get("/api/summary?device_id=rtspark-01&date=2026-10-31").get_json()
    assert body == {"date": "2026-10-31", "seconds": {"walk": 2, "run": 2}}


@needs_db
def test_summary_defaults_to_today_and_reports_zeros(client):
    body = client.get("/api/summary?device_id=rtspark-01").get_json()
    assert body == {"date": NOW.date().isoformat(), "seconds": {"walk": 0, "run": 0}}


@needs_db
@pytest.mark.parametrize(
    "path",
    [
        "/api/latest",
        "/api/history",
        "/api/summary",
        "/api/history?device_id=d&limit=0",
        "/api/history?device_id=d&limit=501",
        "/api/history?device_id=d&limit=abc",
        "/api/history?device_id=d&before=-1",
        "/api/history?device_id=d&before=x",
        "/api/summary?device_id=d&date=31-10-2026",
    ],
)
def test_bad_requests_return_400(client, path):
    response = client.get(path)
    assert response.status_code == 400
    assert "error" in response.get_json()


@needs_db
def test_unknown_route_returns_json_error(client):
    response = client.get("/api/nope")
    assert response.status_code == 404
    assert "error" in response.get_json()


@needs_db
def test_index_page_is_served(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.mimetype == "text/html"
    assert b"/api/latest" in response.data
