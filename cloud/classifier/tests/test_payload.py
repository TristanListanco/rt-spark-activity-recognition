import json

import pytest

from payload import PayloadError, device_id_from_topic, parse_imu_message

TOPIC = "activity/rtspark-01/imu"


def message(**overrides) -> bytes:
    body = {
        "device_id": "rtspark-01",
        "ts": 1_761_800_000_000,
        "rate_hz": 5,
        "samples": [[0.1, -0.9, 0.05, 0.01, -0.02, 0.3]] * 5,
    }
    body.update(overrides)
    return json.dumps(body).encode()


def test_valid_message():
    batch = parse_imu_message(TOPIC, message())
    assert batch.device_id == "rtspark-01"
    assert batch.rate_hz == 5
    assert len(batch.samples) == 5
    assert batch.samples[0] == [0.1, -0.9, 0.05, 0.01, -0.02, 0.3]


def test_ts_zero_is_allowed_without_clock():
    assert parse_imu_message(TOPIC, message(ts=0)).ts == 0


def test_integer_readings_are_converted_to_float():
    batch = parse_imu_message(TOPIC, message(samples=[[0, -1, 0, 0, 0, 0]]))
    assert batch.samples == [[0.0, -1.0, 0.0, 0.0, 0.0, 0.0]]


@pytest.mark.parametrize(
    "topic", ["activity/rtspark-01", "sensors/rtspark-01/imu", "activity//imu", "a/b/c/d"]
)
def test_rejects_unexpected_topics(topic):
    with pytest.raises(PayloadError):
        device_id_from_topic(topic)


@pytest.mark.parametrize(
    "payload",
    [
        b"not json",
        b"\xff\xfe",
        b"[1, 2, 3]",
        message(device_id="other-board"),
        message(ts=-1),
        message(ts="now"),
        message(rate_hz=0),
        message(rate_hz=True),
        message(samples=[]),
        message(samples="lots"),
        message(samples=[[0.1, 0.2, 0.3]]),
        message(samples=[[0.1, 0.2, 0.3, 0.4, 0.5, "x"]]),
        message(samples=[[0.1, 0.2, 0.3, 0.4, 0.5, None]]),
        message(samples=[[0.1] * 6] * 1001),
    ],
)
def test_rejects_invalid_payloads(payload):
    with pytest.raises(PayloadError):
        parse_imu_message(TOPIC, payload)


def test_rejects_non_finite_numbers():
    # Python's json accepts the non-standard NaN literal, so it must be rejected here
    payload = (
        b'{"device_id": "rtspark-01", "ts": 0, "rate_hz": 5,'
        b' "samples": [[NaN, 0, 0, 0, 0, 0]]}'
    )
    with pytest.raises(PayloadError):
        parse_imu_message(TOPIC, payload)
