from pathlib import Path

import numpy as np
import pytest

from payload import ImuBatch
from pipeline import Classifier, newest_sample_ms
from predictor import DeviceStreams, Model

MODEL_DIR = Path(__file__).resolve().parents[3] / "ml" / "models"
RNG = np.random.default_rng(0)


class MemoryWriter:
    def __init__(self):
        self.rows = []

    def insert(self, device_id, ts_ms, activity, confidence):
        self.rows.append((device_id, ts_ms, activity, confidence))
        return True


def batch(device="rtspark-01", ts=1_761_800_000_000, rate=5, n=5) -> ImuBatch:
    return ImuBatch(device, ts, rate, RNG.normal(size=(n, 6)).tolist())


@pytest.fixture(scope="module")
def model() -> Model:
    return Model(MODEL_DIR)


def batches_per_window(model: Model) -> int:
    return model.window // 5  # 1-s batches of 5 samples


def test_model_matches_contract(model):
    assert model.window == 20
    assert model.rate_hz == 5
    assert model.labels == ["walk", "run", "idle"]


def test_model_rejects_tampered_file(tmp_path):
    for name in ("model.onnx", "model_meta.json"):
        (tmp_path / name).write_bytes((MODEL_DIR / name).read_bytes())
    (tmp_path / "model.onnx").write_bytes((MODEL_DIR / "model.onnx").read_bytes() + b"x")
    with pytest.raises(ValueError, match="checksum"):
        Model(tmp_path)


def test_prediction_is_a_label_with_confidence(model):
    p = model.predict(RNG.normal(size=(model.window, 6)))
    assert p.activity in model.labels
    assert 1 / len(model.labels) <= p.confidence <= 1.0


def test_first_prediction_after_window_fills(model):
    writer = MemoryWriter()
    classifier = Classifier(model, writer)
    n = batches_per_window(model)
    for t in range(n - 1):
        assert classifier.handle(batch(), now_monotonic=float(t), now_ms=0) is None  # not full
    assert classifier.handle(batch(), now_monotonic=float(n - 1), now_ms=0) is not None
    assert classifier.handle(batch(), now_monotonic=float(n), now_ms=0) is not None
    assert len(writer.rows) == 2


def test_devices_have_separate_windows(model):
    writer = MemoryWriter()
    classifier = Classifier(model, writer)
    n = batches_per_window(model)
    for t in range(n - 1):
        classifier.handle(batch("a"), float(t), 0)
        classifier.handle(batch("b"), float(t), 0)
    assert writer.rows == []
    classifier.handle(batch("a"), float(n - 1), 0)
    assert [row[0] for row in writer.rows] == ["a"]


def test_gap_starts_a_new_window():
    streams = DeviceStreams(window=10, gap_reset_s=3.0)
    assert streams.add("d", [[0.0] * 6] * 5, now=0.0) is None
    assert streams.add("d", [[0.0] * 6] * 5, now=10.0) is None  # gap: old samples dropped
    window = streams.add("d", [[1.0] * 6] * 5, now=11.0)
    assert window.shape == (10, 6)
    assert window[0, 0] == 0.0 and window[-1, 0] == 1.0  # oldest first


def test_window_keeps_only_newest_samples():
    streams = DeviceStreams(window=10)
    streams.add("d", [[float(i)] * 6 for i in range(8)], now=0.0)
    window = streams.add("d", [[float(i)] * 6 for i in range(8, 13)], now=1.0)
    assert window[:, 0].tolist() == [float(i) for i in range(3, 13)]


def test_wrong_rate_is_ignored(model):
    writer = MemoryWriter()
    classifier = Classifier(model, writer)
    for t in range(3):
        assert classifier.handle(batch(rate=50, n=50), float(t), 0) is None
    assert writer.rows == []


def test_timestamp_is_newest_sample_or_arrival_time(model):
    assert newest_sample_ms(batch(ts=1_000_000, rate=5, n=5)) == 1_000_800
    assert newest_sample_ms(batch(ts=0)) is None

    writer = MemoryWriter()
    classifier = Classifier(model, writer)
    n = batches_per_window(model)
    for t in range(n):
        classifier.handle(batch(ts=0), float(t), now_ms=1000 + t)
    assert writer.rows[0][1] == 1000 + n - 1  # arrival of the batch that filled the window


def test_each_stored_prediction_is_published_back(model):
    import json

    sent = []
    classifier = Classifier(model, MemoryWriter(), notify=lambda t, p: sent.append((t, p)))
    n = batches_per_window(model)
    for t in range(n - 1):
        classifier.handle(batch(ts=1_000_000 + 1000 * t), float(t), 0)
    assert sent == []  # window not full yet
    last_ts = 1_000_000 + 1000 * (n - 1)
    prediction = classifier.handle(batch(ts=last_ts), float(n - 1), 0)
    assert len(sent) == 1
    topic, payload = sent[0]
    assert topic == "activity/rtspark-01/prediction"
    body = json.loads(payload)
    assert body == {
        "activity": prediction.activity,
        "confidence": round(prediction.confidence, 4),
        "ts": last_ts + 800,  # newest sample of the batch that filled the window
    }


def test_prediction_message_is_compact_json():
    from pipeline import prediction_message
    from predictor import Prediction

    assert (
        prediction_message(Prediction("run", 0.973456), 1761800000123)
        == '{"activity":"run","confidence":0.9735,"ts":1761800000123}'
    )
