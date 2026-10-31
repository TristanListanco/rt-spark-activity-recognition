"""Write predictions to PostgreSQL (table defined in cloud/db/init.sql)."""

import logging
from datetime import UTC, datetime

import psycopg

log = logging.getLogger(__name__)

INSERT = "INSERT INTO predictions (device_id, ts, activity, confidence) VALUES (%s, %s, %s, %s)"


class PredictionWriter:
    """Keeps one connection open and reconnects once after an error (e.g. a database restart).

    `conninfo` is a libpq connection string; an empty string means "use the PG* environment
    variables" (PGHOST, PGUSER, ...), which is how Docker Compose configures it.
    """

    def __init__(self, conninfo: str = ""):
        self._conninfo = conninfo
        self._conn: psycopg.Connection | None = None

    def insert(self, device_id: str, ts_ms: int, activity: str, confidence: float) -> bool:
        ts = datetime.fromtimestamp(ts_ms / 1000, tz=UTC)
        for attempt in (1, 2):
            try:
                if self._conn is None or self._conn.closed:
                    self._conn = psycopg.connect(self._conninfo, autocommit=True, connect_timeout=5)
                self._conn.execute(INSERT, (device_id, ts, activity, confidence))
                return True
            except psycopg.OperationalError as exc:
                log.warning("database write failed (attempt %d): %s", attempt, exc)
                self.close()
        return False

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None
