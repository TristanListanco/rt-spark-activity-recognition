# Interface Contracts

The formats each part of the system relies on: firmware → MQTT → classifier → database → API → app.
If you change anything here, update every consumer in the same commit, bump the version, and add a line to the changelog at the bottom.

Version: **0.7**

Values marked **provisional** are checked during the ML step (M2) and then finalized.

---

## 1. Device identity

| Field | Value |
|---|---|
| `device_id` | `rtspark-01` |
| Wear position | Wrist, fixed orientation (photo in the README) |

## 2. Sensor data: units, rate, axes, window

These must match the Kaggle run-or-walk dataset (https://www.kaggle.com/vmalyi/run-or-walk) so the model sees the same kind of data from the board as it was trained on.

| Item | Value | Evidence (M2, see `docs/ml-report.md`) |
|---|---|---|
| Sample rate `R` | **5 Hz** | Dataset timestamps are H:M:S:nanoseconds; the median step is 0.2000 s (p10–p90: 0.199–0.201 s) |
| Accelerometer unit | **g, gravity included** | Mean \|a\| while walking is 1.08 g. Without gravity it would be near 0; in m/s² it would be near 9.8 |
| Gyroscope unit | **rad/s** | \|ω\| averages 1.9 (walk) / 2.7 (run), max 11. In deg/s these would be in the hundreds |
| Axis mapping | board X/Y/Z → dataset x/y/z | M4 checks with the board on the wrist. In the dataset, gravity lies along −y when the arm hangs down |
| Sample order | `[ax, ay, az, gx, gy, gz]` | fixed |
| Window `W` | **10 samples (2 s)** | M2 compared 10 and 20. 20 is 0.15 points more accurate but reacts about 2 s slower (`docs/ml-report.md`, section 5) |
| Prediction rate | once per second (stride = `R` samples) | fixed |

The firmware converts raw IMU readings to these units **before** publishing; nothing else is done to the data on the board. The cloud cuts the stream into windows with `ml/activity_ml/preprocess.py`. Everything after that (magnitude channels, normalization) is inside the exported ONNX model, so training and the live classifier process data identically.

## 3. MQTT (board → broker)

| Field | Value |
|---|---|
| Broker host | `rtspark-activity-b2093c.eastasia.cloudapp.azure.com` (Azure VM, static IP); the local stack uses the computer's IP |
| Port | `1883` |
| Auth | username/password from `cloud/.env` (never committed) |
| Topic | `activity/<device_id>/imu`, e.g. `activity/rtspark-01/imu` |
| QoS | `1` (RT-Thread's Paho port only supports QoS 1; the classifier subscribes at QoS 0, so the broker delivers to it at QoS 0) |
| Publish interval | once per second |

Payload (JSON, one message per second, containing the last `R` samples):

```json
{
  "device_id": "rtspark-01",
  "ts": 1760000000000,
  "rate_hz": 5,
  "samples": [
    [0.12, -0.98, 0.05, 0.01, -0.02, 0.30],
    [0.15, -0.97, 0.04, 0.02, -0.01, 0.28],
    [0.11, -0.99, 0.06, 0.00, -0.03, 0.31],
    [0.14, -0.96, 0.05, 0.02, -0.02, 0.29],
    [0.13, -0.98, 0.04, 0.01, -0.01, 0.30]
  ]
}
```

- `ts`: Unix time in **milliseconds** of the **first** sample in the batch. If the board has no NTP time, it sends `0`, and the classifier uses the time the message arrived.
- `rate_hz`: the actual sample rate.
- `samples`: length = `rate_hz`; each entry = `[ax, ay, az, gx, gy, gz]` in the units from section 2.

### Predictions back to the board (classifier → board)

After storing each prediction, the classifier also publishes it, so the board can show it on its LCD.

| Field | Value |
|---|---|
| Topic | `activity/<device_id>/prediction`, e.g. `activity/rtspark-01/prediction` |
| QoS | `0`, not retained (a new one arrives every second) |

```json
{ "activity": "run", "confidence": 0.9735, "ts": 1760000000000 }
```

Compact JSON (no spaces), produced by `prediction_message()` in `cloud/classifier/pipeline.py`. `ts` has the same meaning as in the API's `/api/latest`. The firmware parses it with `prediction_parse()` in `firmware/applications/payload.c`, and a host test checks the two against each other.

## 4. Web API (cloud → app)

Base URL: `http://rtspark-activity-b2093c.eastasia.cloudapp.azure.com` (Azure, port 80); `http://<host>:8000` for the local stack (macOS reserves port 5000 for AirPlay). All responses are JSON. Timestamps are Unix **milliseconds**.

Bad query parameters (missing `device_id`, `limit` outside 1–500, malformed `before` or `date`) return `400`.

### `GET /api/health`
```json
{ "status": "ok" }
```
Also checks the database: returns `503` with `{ "error": "database unavailable" }` if it can't be reached. Every other endpoint returns the same `503` during a database outage.

### `GET /api/latest?device_id=rtspark-01`
```json
{ "device_id": "rtspark-01", "activity": "walk", "confidence": 0.93, "ts": 1760000000000 }
```
Returns `404` with `{ "error": "no data" }` if there are no predictions for the device yet. `ts` is the time of the newest sample in the classified window. Compare it with the current time to show "updated N s ago" or to notice that the board went offline.

### `GET /api/history?device_id=rtspark-01&limit=50&before=<ts>`
- `limit`: default `50`, max `500`
- `before`: optional; returns records older than this timestamp (for paging)
- Sorted newest first
```json
[
  { "activity": "run",  "confidence": 0.88, "ts": 1760000005000 },
  { "activity": "walk", "confidence": 0.91, "ts": 1760000004000 }
]
```

### `GET /api/summary?device_id=rtspark-01&date=2026-10-30`
```json
{ "date": "2026-10-30", "seconds": { "walk": 1240, "run": 315 } }
```
`date` defaults to today, as a calendar day in `APP_TIMEZONE` (Asia/Manila). There is one prediction per second, so `seconds` is the number of predictions of each activity that day. Both keys are always present.

### `GET /`
A small live web page (current activity, today's totals, recent predictions) that polls the endpoints above. `/?device=<id>` shows another device.

### Errors
Any error → HTTP 4xx/5xx with `{ "error": "<message>" }`.

## 5. Classifier behaviour

How `cloud/classifier` turns the MQTT stream into predictions:

- It keeps the newest `W` = 10 samples per device. The first prediction comes after 2 messages (2 s); after that there is one per message (per second).
- After a pause longer than 3 s (reconnect, reboot) it starts a fresh window, so a window never joins samples from before and after the pause.
- Messages whose `rate_hz` differs from the model's (5) are ignored and logged, because the model only understands 5 Hz data.
- Invalid messages (wrong topic, bad JSON, wrong shape) are logged and dropped.
- Every stored prediction is also published to `activity/<device_id>/prediction` (section 3).

## 6. Activity labels

| Label | Dataset value |
|---|---|
| `walk` | `activity = 0` |
| `run` | `activity = 1` |

Adding a class (e.g. `idle`) needs a version bump, because the app must know the new label to show its icon and colour.

## 7. Database

```sql
CREATE TABLE predictions (
  id          BIGSERIAL PRIMARY KEY,
  device_id   TEXT        NOT NULL,
  ts          TIMESTAMPTZ NOT NULL,
  activity    TEXT        NOT NULL,
  confidence  REAL        NOT NULL
);
CREATE INDEX predictions_device_ts ON predictions (device_id, ts DESC);
```

---

## Changelog

| Version | Date | Change |
|---|---|---|
| 0.1 | 2026-10-11 | Initial draft (two-person split) |
| 0.2 | 2026-10-30 | Solo project; provisional R = 5 Hz, W = 10, gravity check added |
| 0.3 | 2026-10-31 | Local API port 5000 → 8000; documented 400 cases |
| 0.4 | 2026-10-31 | M2: R = 5 Hz, accel in g with gravity, gyro in rad/s, W = 10 confirmed from the data; no gravity removal |
| 0.5 | 2026-10-31 | M3: classifier behaviour section, 503 on database outage, meaning of `ts` and `seconds`, web page at `/` |
| 0.6 | 2026-10-31 | M4: board publishes with QoS 1 (the only QoS RT-Thread's Paho port supports) |
| 0.7 | 2026-10-31 | Predictions published back to the board on `activity/<device_id>/prediction`, for its LCD |
