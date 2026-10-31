"""Windowing shared by training and the live classifier.

Numpy only, so the classifier image needs neither pandas nor PyTorch. A sample
is one row [ax, ay, az, gx, gy, gz]: acceleration in g (gravity included) and
angular rate in rad/s, at RATE_HZ (docs/CONTRACTS.md, section 2). Everything
else (magnitudes, normalization) happens inside the exported ONNX model, so
training and serving cannot drift apart.
"""

import numpy as np

AXES = ("ax", "ay", "az", "gx", "gy", "gz")
RATE_HZ = 5


def sliding_windows(samples: np.ndarray, window: int, stride: int = 1) -> np.ndarray:
    """Cut (N, 6) samples into (M, window, 6) overlapping windows, oldest first.

    Returns an empty (0, window, 6) array when there are fewer than `window` samples.
    """
    samples = np.asarray(samples, dtype=np.float32)
    if samples.ndim != 2 or samples.shape[1] != len(AXES):
        raise ValueError(f"expected samples of shape (N, {len(AXES)}), got {samples.shape}")
    if window < 1 or stride < 1:
        raise ValueError("window and stride must be positive")
    if len(samples) < window:
        return np.empty((0, window, len(AXES)), dtype=np.float32)
    views = np.lib.stride_tricks.sliding_window_view(samples, window, axis=0)  # (M, 6, window)
    return np.ascontiguousarray(views[::stride].transpose(0, 2, 1))
