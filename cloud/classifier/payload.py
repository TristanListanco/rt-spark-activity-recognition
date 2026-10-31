"""Parse and validate IMU messages from the board (docs/CONTRACTS.md, section 3)."""

import json
import math
from dataclasses import dataclass

AXES = 6  # ax, ay, az, gx, gy, gz
MAX_SAMPLES = 1000  # reject absurdly large batches


class PayloadError(ValueError):
    """The message does not follow the contract."""


@dataclass(frozen=True)
class ImuBatch:
    device_id: str
    ts: int  # Unix ms of the first sample, or 0 if the board has no clock
    rate_hz: int
    samples: list[list[float]]


def device_id_from_topic(topic: str) -> str:
    parts = topic.split("/")
    if len(parts) != 3 or parts[0] != "activity" or parts[2] != "imu" or not parts[1]:
        raise PayloadError(f"unexpected topic {topic!r}")
    return parts[1]


def parse_imu_message(topic: str, payload: bytes) -> ImuBatch:
    topic_device = device_id_from_topic(topic)
    try:
        data = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PayloadError(f"not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise PayloadError("payload must be a JSON object")

    device_id = data.get("device_id")
    if device_id != topic_device:
        raise PayloadError(f"device_id {device_id!r} does not match topic ({topic_device!r})")

    ts = data.get("ts")
    if not _is_int(ts) or ts < 0:
        raise PayloadError("ts must be a non-negative integer (Unix ms)")

    rate_hz = data.get("rate_hz")
    if not _is_int(rate_hz) or rate_hz <= 0:
        raise PayloadError("rate_hz must be a positive integer")

    samples = data.get("samples")
    if not isinstance(samples, list) or not 0 < len(samples) <= MAX_SAMPLES:
        raise PayloadError(f"samples must be a non-empty list of at most {MAX_SAMPLES} rows")
    for i, row in enumerate(samples):
        if not isinstance(row, list) or len(row) != AXES or not all(map(_is_number, row)):
            raise PayloadError(f"samples[{i}] must be a list of {AXES} finite numbers")

    return ImuBatch(device_id, ts, rate_hz, [[float(v) for v in row] for row in samples])


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool) and math.isfinite(value)
