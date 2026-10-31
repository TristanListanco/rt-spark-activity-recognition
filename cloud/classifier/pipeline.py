"""From a validated IMU batch to a stored (and announced) prediction."""

import json
import logging
from collections.abc import Callable
from typing import Protocol

from payload import ImuBatch
from predictor import DeviceStreams, Model, Prediction

log = logging.getLogger("classifier")

PREDICTION_TOPIC = "activity/{device_id}/prediction"


class Writer(Protocol):
    def insert(self, device_id: str, ts_ms: int, activity: str, confidence: float) -> bool: ...


def newest_sample_ms(batch: ImuBatch) -> int | None:
    """Time of the batch's last sample, or None if the board sent no clock (ts = 0)."""
    if batch.ts == 0:
        return None
    return batch.ts + round((len(batch.samples) - 1) * 1000 / batch.rate_hz)


def prediction_message(prediction: Prediction, ts_ms: int) -> str:
    """The message sent back to the device (docs/CONTRACTS.md, section 3)."""
    body = {
        "activity": prediction.activity,
        "confidence": round(prediction.confidence, 4),
        "ts": ts_ms,
    }
    return json.dumps(body, separators=(",", ":"))


class Classifier:
    def __init__(
        self,
        model: Model,
        writer: Writer,
        notify: Callable[[str, str], None] | None = None,
    ):
        """`notify(topic, payload)` publishes each prediction back over MQTT, if given."""
        self.model = model
        self.writer = writer
        self.notify = notify
        self.streams = DeviceStreams(model.window)

    def handle(self, batch: ImuBatch, now_monotonic: float, now_ms: int) -> Prediction | None:
        """Add the batch to its device's window; predict and store once the window is full."""
        if batch.rate_hz != self.model.rate_hz:
            log.warning(
                "ignoring %s: rate %d Hz, model expects %d Hz",
                batch.device_id,
                batch.rate_hz,
                self.model.rate_hz,
            )
            return None
        window = self.streams.add(batch.device_id, batch.samples, now_monotonic)
        if window is None:
            return None

        prediction = self.model.predict(window)
        ts_ms = newest_sample_ms(batch) or now_ms
        stored = self.writer.insert(
            batch.device_id, ts_ms, prediction.activity, prediction.confidence
        )
        if self.notify is not None:
            self.notify(
                PREDICTION_TOPIC.format(device_id=batch.device_id),
                prediction_message(prediction, ts_ms),
            )
        log.info(
            "device=%s activity=%s confidence=%.2f%s",
            batch.device_id,
            prediction.activity,
            prediction.confidence,
            "" if stored else " (NOT STORED)",
        )
        return prediction
