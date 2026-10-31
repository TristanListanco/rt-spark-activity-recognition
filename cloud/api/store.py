"""Read predictions from PostgreSQL (table defined in cloud/db/init.sql).

The classifier stores one prediction per device per second, so the number of
rows for an activity on a day is the number of seconds spent on it.
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta, tzinfo

import psycopg

LABELS = ("walk", "run")


@dataclass(frozen=True)
class Prediction:
    activity: str
    confidence: float
    ts: int  # Unix milliseconds

    def to_json(self) -> dict:
        return {"activity": self.activity, "confidence": self.confidence, "ts": self.ts}


def _prediction(row) -> Prediction:
    activity, confidence, ts = row
    return Prediction(activity, round(float(confidence), 4), round(ts.timestamp() * 1000))


class PostgresStore:
    """One short-lived connection per request; `conninfo` "" means use the PG* variables."""

    def __init__(self, conninfo: str = ""):
        self._conninfo = conninfo

    def _fetch(self, sql: str, params: tuple = ()) -> list[tuple]:
        with psycopg.connect(self._conninfo, connect_timeout=5) as conn:
            return conn.execute(sql, params).fetchall()

    def ping(self) -> None:
        self._fetch("SELECT 1")

    def latest(self, device_id: str) -> Prediction | None:
        rows = self._fetch(
            "SELECT activity, confidence, ts FROM predictions"
            " WHERE device_id = %s ORDER BY ts DESC LIMIT 1",
            (device_id,),
        )
        return _prediction(rows[0]) if rows else None

    def history(self, device_id: str, limit: int, before_ms: int | None = None) -> list[Prediction]:
        """Newest first; only records strictly older than before_ms when given."""
        if before_ms is None:
            rows = self._fetch(
                "SELECT activity, confidence, ts FROM predictions"
                " WHERE device_id = %s ORDER BY ts DESC LIMIT %s",
                (device_id, limit),
            )
        else:
            before = datetime.fromtimestamp(before_ms / 1000, tz=UTC)
            rows = self._fetch(
                "SELECT activity, confidence, ts FROM predictions"
                " WHERE device_id = %s AND ts < %s ORDER BY ts DESC LIMIT %s",
                (device_id, before, limit),
            )
        return [_prediction(row) for row in rows]

    def summary(self, device_id: str, day: date, tz: tzinfo) -> dict[str, int]:
        """Seconds per activity on a calendar day in the given time zone."""
        start = datetime.combine(day, datetime.min.time(), tz)
        end = datetime.combine(day + timedelta(days=1), datetime.min.time(), tz)
        rows = self._fetch(
            "SELECT activity, count(*) FROM predictions"
            " WHERE device_id = %s AND ts >= %s AND ts < %s GROUP BY activity",
            (device_id, start, end),
        )
        seconds = dict.fromkeys(LABELS, 0)
        seconds.update({activity: int(count) for activity, count in rows})
        return seconds
