"""Flask Web API for activity predictions (docs/CONTRACTS.md, section 4).

Run in Docker with gunicorn ("server:create_app()"). In M1 the data comes from
FakeStore; M3 passes a PostgreSQL-backed store with the same methods.
"""

import os
import time
from collections.abc import Callable
from datetime import date, datetime
from zoneinfo import ZoneInfo

from flask import Flask, abort, jsonify, request
from werkzeug.exceptions import HTTPException

from fake_data import FakeStore

HISTORY_DEFAULT_LIMIT = 50
HISTORY_MAX_LIMIT = 500


def create_app(store=None, clock: Callable[[], float] = time.time) -> Flask:
    app = Flask(__name__)
    tz = ZoneInfo(os.environ.get("APP_TIMEZONE", "Asia/Manila"))
    store = store or FakeStore(clock)

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    @app.get("/api/latest")
    def latest():
        device_id = _device_id_arg()
        prediction = store.latest(device_id)
        if prediction is None:
            abort(404, description="no data")
        return {"device_id": device_id, **prediction.to_json()}

    @app.get("/api/history")
    def history():
        device_id = _device_id_arg()
        limit = _int_arg("limit", HISTORY_DEFAULT_LIMIT, minimum=1, maximum=HISTORY_MAX_LIMIT)
        before = _int_arg("before", None, minimum=0)
        rows = store.history(device_id, limit=limit, before_ms=before)
        return jsonify([row.to_json() for row in rows])

    @app.get("/api/summary")
    def summary():
        device_id = _device_id_arg()
        day = _date_arg("date", datetime.fromtimestamp(clock(), tz).date())
        return {"date": day.isoformat(), "seconds": store.summary(device_id, day, tz)}

    @app.errorhandler(HTTPException)
    def http_error(error: HTTPException):
        return jsonify(error=error.description), error.code

    return app


def _device_id_arg() -> str:
    device_id = request.args.get("device_id", "").strip()
    if not device_id:
        abort(400, description="device_id is required")
    return device_id


def _int_arg(name: str, default: int | None, minimum: int, maximum: int | None = None):
    raw = request.args.get(name, "")
    if raw == "":
        return default
    try:
        value = int(raw)
    except ValueError:
        abort(400, description=f"{name} must be an integer")
    if value < minimum or (maximum is not None and value > maximum):
        upper = f" and at most {maximum}" if maximum is not None else ""
        abort(400, description=f"{name} must be at least {minimum}{upper}")
    return value


def _date_arg(name: str, default: date) -> date:
    raw = request.args.get(name, "")
    if raw == "":
        return default
    try:
        return date.fromisoformat(raw)
    except ValueError:
        abort(400, description=f"{name} must be a date in YYYY-MM-DD format")
