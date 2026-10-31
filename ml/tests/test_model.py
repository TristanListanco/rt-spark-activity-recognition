import numpy as np
import pytest
import torch

from activity_ml.model import CHANNELS, ActivityNet, add_magnitudes, channel_stats
from activity_ml.training import MIRROR, augment, random_rotations

RNG = np.random.default_rng(0)


def windows(n: int = 32, w: int = 10) -> np.ndarray:
    return RNG.normal(size=(n, w, 6)).astype(np.float32)


@pytest.mark.parametrize("w", [10, 20])
def test_forward_shape_any_window_length(w):
    x = windows(w=w)
    model = ActivityNet(*channel_stats(x))
    assert model(torch.as_tensor(x)).shape == (32, 2)


def test_magnitude_channels():
    x = windows()
    f = add_magnitudes(x)
    assert f.shape[-1] == len(CHANNELS)
    np.testing.assert_allclose(f[..., 6], np.linalg.norm(x[..., :3], axis=-1), rtol=1e-6)
    np.testing.assert_allclose(f[..., 7], np.linalg.norm(x[..., 3:], axis=-1), rtol=1e-6)


def test_model_standardizes_with_stored_stats():
    x = windows(256)
    mean, std = channel_stats(x)
    np.testing.assert_allclose(
        (add_magnitudes(x).reshape(-1, 8) - mean).std(0) / std, np.ones(8), rtol=1e-3
    )


def test_random_rotations_are_proper():
    r = random_rotations(500, torch.Generator().manual_seed(0))
    identity = torch.eye(3).expand(500, 3, 3)
    torch.testing.assert_close(r @ r.transpose(1, 2), identity, atol=1e-5, rtol=0)
    torch.testing.assert_close(torch.det(r), torch.ones(500), atol=1e-5, rtol=0)


def test_rotate_augmentation_keeps_magnitudes():
    x = torch.as_tensor(windows())
    y = augment(x, "rotate", torch.Generator().manual_seed(1))
    torch.testing.assert_close(x[..., :3].norm(dim=-1), y[..., :3].norm(dim=-1))
    torch.testing.assert_close(x[..., 3:].norm(dim=-1), y[..., 3:].norm(dim=-1))


def test_mirror_is_a_reflection():
    x = torch.as_tensor(windows())
    torch.testing.assert_close(x * MIRROR * MIRROR, x)
    y = augment(x, "mirror", torch.Generator().manual_seed(2))
    flipped = ~torch.isclose(y, x).all(dim=(1, 2))
    assert 0 < flipped.sum() < len(x)  # roughly half the batch
    torch.testing.assert_close(y[flipped], x[flipped] * MIRROR)


def test_no_augmentation_is_identity():
    x = torch.as_tensor(windows())
    assert augment(x, "none", torch.Generator()) is x
