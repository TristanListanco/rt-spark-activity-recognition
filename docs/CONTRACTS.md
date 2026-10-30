# Interface Contracts

The formats each part of the system relies on: firmware → MQTT → classifier → database → API → app.
If you change anything here, update every consumer in the same commit, bump the version, and add a line to the changelog at the bottom.

Version: **0.2**

Values marked **provisional** are checked during the ML step (M2) and then finalized.

---

## 1. Device identity

| Field | Value |
|---|---|
| `device_id` | `rtspark-01` |
| Wear position | Wrist, fixed orientation (photo in the README) |

## 2. Sensor data: units, rate, axes, window

These must match the Kaggle run-or-walk dataset (https://www.kaggle.com/vmalyi/run-or-walk) so the model sees the same kind of data from the board as it was trained on.

| Item | Value | Status |
|---|---|---|
| Sample rate `R` | 5 Hz (the dataset is about 5.4 Hz) | provisional, M2 measures it from the dataset timestamps |
| Accelerometer unit | g (assumed) | provisional, M2 checks the magnitude: ≈1 → g, ≈9.8 → m/s² |
| Gyroscope unit | rad/s (assumed) | provisional, M2 checks the value ranges |
| Gravity in accel | unknown | M2 checks whether the dataset's accelerometer data includes gravity. If not, the classifier removes gravity from the board's data |
| Axis mapping | board X/Y/Z → dataset x/y/z | M4 checks with the board on the wrist |
| Sample order | `[ax, ay, az, gx, gy, gz]` | fixed |
| Window `W` | 10 samples (≈2 s) | provisional |
| Prediction rate | once per second (stride = `R` samples) | fixed |

The firmware converts raw IMU readings to these units **before** publishing. Any other preprocessing (gravity removal, normalization) lives in `ml/activity_ml/preprocess.py`, which training and the live classifier both use.

## 3. MQTT (board → broker)

| Field | Value |
|---|---|
| Broker host | local Mac IP during development, Azure VM static IP after M6 |
| Port | `1883` |
| Auth | username/password from `cloud/.env` (never committed) |
| Topic | `activity/<device_id>/imu`, e.g. `activity/rtspark-01/imu` |
| QoS | `0` |
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

## 4. Web API (cloud → app)

Base URL: `http://<host>:5000` locally, `http://<vm-ip>` on Azure. All responses are JSON. Timestamps are Unix **milliseconds**.

### `GET /api/health`
```json
{ "status": "ok" }
```

### `GET /api/latest?device_id=rtspark-01`
```json
{ "device_id": "rtspark-01", "activity": "walk", "confidence": 0.93, "ts": 1760000000000 }
```
Returns `404` with `{ "error": "no data" }` if there are no predictions for the device yet.

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

### Errors
Any error → HTTP 4xx/5xx with `{ "error": "<message>" }`.

## 5. Activity labels

| Label | Dataset value |
|---|---|
| `walk` | `activity = 0` |
| `run` | `activity = 1` |

Adding a class (e.g. `idle`) needs a version bump, because the app must know the new label to show its icon and colour.

## 6. Database

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
