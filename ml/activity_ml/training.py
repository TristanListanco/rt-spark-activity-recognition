"""Training loop, augmentation and the feature baseline."""

import numpy as np
import torch
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from torch import nn

from activity_ml.model import ActivityNet, add_magnitudes, channel_stats

AUGMENTATIONS = ("none", "mirror", "rotate")
# Training windows overlap heavily at stride 1; every 2nd window trains just as well
# in half the time. Used by both evaluate.py and train.py.
TRAIN_STRIDE = 2

# Reflection across the body's mid-plane (left wrist ↔ right wrist). Acceleration
# is a polar vector: (-ax, ay, az). Angular rate is an axial vector, so it picks up
# an extra sign flip under a reflection: (gx, -gy, -gz).
MIRROR = torch.tensor([-1.0, 1.0, 1.0, 1.0, -1.0, -1.0])


def random_rotations(n: int, generator: torch.Generator) -> torch.Tensor:
    """n uniformly random 3D rotation matrices (QR of Gaussian matrices)."""
    q, r = torch.linalg.qr(torch.randn(n, 3, 3, generator=generator))
    q = q * torch.sign(torch.diagonal(r, dim1=-2, dim2=-1)).unsqueeze(-2)
    flip = torch.det(q) < 0
    q[flip, :, 0] = -q[flip, :, 0]
    return q


def augment(x: torch.Tensor, mode: str, generator: torch.Generator) -> torch.Tensor:
    """Augment a batch of raw windows (B, W, 6).

    mirror: swap wrist for a random half of the batch.
    rotate: mirror, then rotate accel and gyro by the same random rotation, so the
            model cannot rely on how the device is oriented on the wrist.
    """
    if mode == "none":
        return x
    mirror = torch.rand(len(x), generator=generator) < 0.5
    x = torch.where(mirror[:, None, None], x * MIRROR, x)
    if mode == "mirror":
        return x
    rot = random_rotations(len(x), generator)  # (B, 3, 3)
    acc = torch.einsum("bij,bwj->bwi", rot, x[..., :3])
    gyr = torch.einsum("bij,bwj->bwi", rot, x[..., 3:])
    return torch.cat([acc, gyr], dim=-1)


def fit_cnn(
    windows: np.ndarray,
    labels: np.ndarray,
    augmentation: str = "none",
    epochs: int = 8,
    batch_size: int = 512,
    lr: float = 5e-3,
    width: int = 16,
    seed: int = 0,
) -> ActivityNet:
    if augmentation not in AUGMENTATIONS:
        raise ValueError(f"augmentation must be one of {AUGMENTATIONS}")
    torch.manual_seed(seed)
    generator = torch.Generator().manual_seed(seed)

    mean, std = channel_stats(windows)
    model = ActivityNet(mean, std, width=width)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)
    loss_fn = nn.CrossEntropyLoss()

    x_all = torch.as_tensor(windows, dtype=torch.float32)
    y_all = torch.as_tensor(labels, dtype=torch.int64)
    model.train()
    for _ in range(epochs):
        order = torch.randperm(len(x_all), generator=generator)
        for start in range(0, len(order), batch_size):
            idx = order[start : start + batch_size]
            x = augment(x_all[idx], augmentation, generator)
            optimizer.zero_grad()
            loss_fn(model(x), y_all[idx]).backward()
            optimizer.step()
        scheduler.step()
    model.eval()
    return model


@torch.no_grad()
def predict_proba(model: nn.Module, windows: np.ndarray, batch_size: int = 4096) -> np.ndarray:
    x = torch.as_tensor(windows, dtype=torch.float32)
    batches = (x[i : i + batch_size] for i in range(0, len(x), batch_size))
    return torch.cat([torch.softmax(model(b), dim=-1) for b in batches]).numpy()


def window_features(windows: np.ndarray) -> np.ndarray:
    """Order-free summary of each window: mean, std, min, max of the 8 channels."""
    f = add_magnitudes(windows)
    return np.concatenate([f.mean(1), f.std(1), f.min(1), f.max(1)], axis=1)


def fit_baseline(windows: np.ndarray, labels: np.ndarray):
    """Logistic regression on window statistics: ignores the order of samples in time."""
    model = make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000))
    return model.fit(window_features(windows), labels)
