"""Load the exported model and keep a sliding window of samples per device.

The model (ml/models/model.onnx, see docs/ml-report.md) takes raw windows
(batch, W, 6) in contract units and returns [walk, run] probabilities. The
feature steps are inside the ONNX file, so this only has to supply the newest
W samples in order.
"""

import hashlib
import json
from collections import deque
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import onnxruntime as ort

# A pause longer than this means the stream was interrupted (reconnect, reboot);
# start a fresh window instead of joining samples from before and after the gap,
# just as training windows never cross a recording-session boundary.
GAP_RESET_S = 3.0


@dataclass(frozen=True)
class Prediction:
    activity: str
    confidence: float


class Model:
    def __init__(self, model_dir: Path):
        meta = json.loads((model_dir / "model_meta.json").read_text())
        data = (model_dir / meta["model_file"]).read_bytes()
        if hashlib.sha256(data).hexdigest() != meta["sha256"]:
            raise ValueError(f"{meta['model_file']} does not match the checksum in model_meta.json")
        self.window: int = meta["window"]
        self.rate_hz: int = meta["rate_hz"]
        self.labels: list[str] = meta["output"]["labels"]
        self._input = meta["input"]["name"]
        self._session = ort.InferenceSession(data, providers=["CPUExecutionProvider"])

    def predict(self, window: np.ndarray) -> Prediction:
        """window: (W, 6) samples, oldest first."""
        x = np.asarray(window, dtype=np.float32)[np.newaxis]
        probs = self._session.run(None, {self._input: x})[0][0]
        best = int(probs.argmax())
        return Prediction(self.labels[best], float(probs[best]))


class DeviceStreams:
    """The newest `window` samples of each device."""

    def __init__(self, window: int, gap_reset_s: float = GAP_RESET_S):
        self.window = window
        self.gap_reset_s = gap_reset_s
        self._samples: dict[str, deque] = {}
        self._last_seen: dict[str, float] = {}

    def add(self, device_id: str, samples: list[list[float]], now: float) -> np.ndarray | None:
        """Append a batch (arriving at monotonic time `now`); return a full window if ready."""
        buffer = self._samples.setdefault(device_id, deque(maxlen=self.window))
        last = self._last_seen.get(device_id)
        if last is not None and now - last > self.gap_reset_s:
            buffer.clear()
        self._last_seen[device_id] = now
        buffer.extend(samples)
        if len(buffer) < self.window:
            return None
        return np.asarray(buffer, dtype=np.float32)
