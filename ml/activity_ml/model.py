"""The walk/run model: a small temporal 1D-CNN.

Input is a batch of raw windows (N, W, 6) in contract units. The model adds
|accel| and |gyro| channels, standardizes all 8 channels with training-set
statistics stored as buffers, and runs two 1D convolutions over time. Keeping
the feature steps inside the network means the exported ONNX file is the whole
pipeline: the classifier only has to feed it raw windows.
"""

import numpy as np
import torch
from torch import nn

CHANNELS = ("ax", "ay", "az", "gx", "gy", "gz", "|a|", "|g|")


def add_magnitudes(windows: np.ndarray) -> np.ndarray:
    """(M, W, 6) → (M, W, 8): append |accel| and |gyro| (numpy twin of the model's features)."""
    acc = np.linalg.norm(windows[..., :3], axis=-1, keepdims=True)
    gyr = np.linalg.norm(windows[..., 3:], axis=-1, keepdims=True)
    return np.concatenate([windows, acc, gyr], axis=-1)


def channel_stats(windows: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Per-channel mean and std over all samples of the training windows."""
    flat = add_magnitudes(windows).reshape(-1, len(CHANNELS))
    return flat.mean(axis=0), flat.std(axis=0) + 1e-6


class ActivityNet(nn.Module):
    def __init__(self, mean: np.ndarray, std: np.ndarray, width: int = 16, kernel: int = 3):
        super().__init__()
        self.register_buffer("mean", torch.as_tensor(mean, dtype=torch.float32))
        self.register_buffer("std", torch.as_tensor(std, dtype=torch.float32))
        self.net = nn.Sequential(
            nn.Conv1d(len(CHANNELS), width, kernel, padding=kernel // 2),
            nn.ReLU(),
            nn.Conv1d(width, width, kernel, padding=kernel // 2),
            nn.ReLU(),
            nn.AdaptiveAvgPool1d(1),
            nn.Flatten(),
            nn.Linear(width, 2),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """(N, W, 6) raw windows → (N, 2) logits."""
        acc = torch.linalg.vector_norm(x[..., :3], dim=-1, keepdim=True)
        gyr = torch.linalg.vector_norm(x[..., 3:], dim=-1, keepdim=True)
        features = (torch.cat([x, acc, gyr], dim=-1) - self.mean) / self.std
        return self.net(features.transpose(1, 2))


class WithSoftmax(nn.Module):
    """Wrapper used for export: outputs class probabilities instead of logits."""

    def __init__(self, model: nn.Module):
        super().__init__()
        self.model = model

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return torch.softmax(self.model(x), dim=-1)


def parameter_count(model: nn.Module) -> int:
    return sum(p.numel() for p in model.parameters())
