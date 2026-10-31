import os
from datetime import UTC, datetime
from pathlib import Path

import psycopg
import pytest

from store import PredictionWriter

DATABASE_URL = os.environ.get("DATABASE_URL")
INIT_SQL = (Path(__file__).resolve().parents[2] / "db" / "init.sql").read_text()

pytestmark = pytest.mark.skipif(not DATABASE_URL, reason="needs DATABASE_URL (PostgreSQL)")


@pytest.fixture
def db():
    with psycopg.connect(DATABASE_URL, autocommit=True) as conn:
        conn.execute("DROP TABLE IF EXISTS predictions")
        conn.execute(INIT_SQL)
        yield conn


def test_insert_stores_row(db):
    writer = PredictionWriter(DATABASE_URL)
    assert writer.insert("rtspark-01", 1_761_800_000_123, "run", 0.97)
    row = db.execute("SELECT device_id, ts, activity, confidence FROM predictions").fetchone()
    assert row[0] == "rtspark-01"
    assert row[1] == datetime(2025, 10, 30, 4, 53, 20, 123000, tzinfo=UTC)
    assert row[2] == "run"
    assert row[3] == pytest.approx(0.97)


def test_reconnects_after_connection_loss(db):
    writer = PredictionWriter(DATABASE_URL)
    writer.insert("rtspark-01", 1, "walk", 0.9)
    writer._conn.close()  # simulate the database dropping the connection
    assert writer.insert("rtspark-01", 2, "walk", 0.9)
    assert db.execute("SELECT count(*) FROM predictions").fetchone()[0] == 2


def test_unreachable_database_returns_false():
    writer = PredictionWriter("host=127.0.0.1 port=1 connect_timeout=1")
    assert writer.insert("rtspark-01", 1, "walk", 0.9) is False
