"""Generated predictions for the M1 API stub.

The device "alternates" between 30 s of walking and 30 s of running, with one
prediction per second of wall-clock time. This gives the Android app changing
data before the board, classifier and database exist. M3 replaces this with a
PostgreSQL-backed store that has the same methods.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta, tzinfo

PERIOD_S = 60  # first half walk, second half run


@dataclass(frozen=True)
class Prediction:
    activity: str
    confidence: float
    ts: int  # Unix milliseconds

    def to_json(self) -> dict:
        return {"activity": self.activity, "confidence": self.confidence, "ts": self.ts}


def _prediction_at(second: int) -> Prediction:
    activity = "run" if second % PERIOD_S >= PERIOD_S // 2 else "walk"
    confidence = 0.75 + 0.24 * ((second * 7919) % 100) / 100
    return Prediction(activity, round(confidence, 2), second * 1000)


def _run_seconds_before(t: int) -> int:
    """Number of seconds labelled "run" in [0, t)."""
    full_periods, rest = divmod(t, PERIOD_S)
    return full_periods * (PERIOD_S // 2) + max(0, rest - PERIOD_S // 2)


class FakeStore:
    def __init__(self, clock: Callable[[], float] = time.time):
        self._clock = clock

    def latest(self, device_id: str) -> Prediction | None:
        return _prediction_at(int(self._clock()))

    def history(self, device_id: str, limit: int, before_ms: int | None = None) -> list[Prediction]:
        """Newest first, only records strictly older than before_ms when given."""
        newest = int(self._clock()) if before_ms is None else (before_ms - 1) // 1000
        return [_prediction_at(s) for s in range(newest, newest - limit, -1) if s >= 0]

    def summary(self, device_id: str, day: date, tz: tzinfo) -> dict[str, int]:
        """Seconds spent per activity on a calendar day in the given time zone."""
        start = int(datetime.combine(day, datetime.min.time(), tz).timestamp())
        next_day = datetime.combine(day + timedelta(days=1), datetime.min.time(), tz)
        end = min(int(next_day.timestamp()), int(self._clock()))
        if end <= start:
            return {"walk": 0, "run": 0}
        run = _run_seconds_before(end) - _run_seconds_before(start)
        return {"walk": end - start - run, "run": run}
