import numpy as np
import pytest

from activity_ml.preprocess import AXES, sliding_windows


def samples(n: int) -> np.ndarray:
    return np.arange(n * len(AXES), dtype=np.float32).reshape(n, len(AXES))


def test_windows_shape_and_order():
    x = samples(12)
    w = sliding_windows(x, window=10)
    assert w.shape == (3, 10, 6)
    np.testing.assert_array_equal(w[0], x[0:10])
    np.testing.assert_array_equal(w[2], x[2:12])


def test_stride_skips_windows():
    w = sliding_windows(samples(20), window=10, stride=5)
    assert w.shape == (3, 10, 6)
    np.testing.assert_array_equal(w[1, 0], samples(20)[5])


def test_too_few_samples_gives_empty_batch():
    w = sliding_windows(samples(4), window=10)
    assert w.shape == (0, 10, 6)


def test_output_is_contiguous_float32():
    w = sliding_windows(samples(15).astype(np.float64), window=10)
    assert w.dtype == np.float32
    assert w.flags["C_CONTIGUOUS"]


@pytest.mark.parametrize("bad", [np.zeros((10, 5)), np.zeros(60), np.zeros((2, 10, 6))])
def test_rejects_wrong_shape(bad):
    with pytest.raises(ValueError):
        sliding_windows(bad, window=10)


def test_rejects_non_positive_window():
    with pytest.raises(ValueError):
        sliding_windows(samples(10), window=0)
