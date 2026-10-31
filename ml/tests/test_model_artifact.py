"""Checks on the committed model that the classifier service loads."""

import hashlib
import json
from pathlib import Path

import numpy as np
import onnxruntime as ort
import pytest

from activity_ml.model import CLASSES
from activity_ml.preprocess import AXES, RATE_HZ

MODELS = Path(__file__).resolve().parent.parent / "models"
META_PATH = MODELS / "model_meta.json"

pytestmark = pytest.mark.skipif(not META_PATH.exists(), reason="no exported model yet")


@pytest.fixture(scope="module")
def meta() -> dict:
    return json.loads(META_PATH.read_text())


@pytest.fixture(scope="module")
def session(meta) -> ort.InferenceSession:
    return ort.InferenceSession(MODELS / meta["model_file"], providers=["CPUExecutionProvider"])


def test_checksum_matches(meta):
    data = (MODELS / meta["model_file"]).read_bytes()
    assert hashlib.sha256(data).hexdigest() == meta["sha256"]


def test_meta_matches_contract(meta):
    assert meta["rate_hz"] == RATE_HZ
    assert meta["input"]["axes"] == list(AXES)
    assert meta["output"]["labels"] == list(CLASSES)
    assert meta["input"]["shape"] == ["batch", meta["window"], len(AXES)]


def test_io_names(session, meta):
    assert [i.name for i in session.get_inputs()] == [meta["input"]["name"]]
    assert [o.name for o in session.get_outputs()] == [meta["output"]["name"]]


@pytest.mark.parametrize("batch", [1, 7])
def test_outputs_are_probabilities(session, meta, batch):
    rng = np.random.default_rng(0)
    x = rng.normal(size=(batch, meta["window"], len(AXES))).astype(np.float32)
    probs = session.run(None, {meta["input"]["name"]: x})[0]
    assert probs.shape == (batch, len(meta["output"]["labels"]))
    assert np.all(probs >= 0)
    np.testing.assert_allclose(probs.sum(axis=1), 1.0, rtol=1e-5)


def test_model_is_lightweight(meta):
    assert meta["parameters"] < 5000
    assert (MODELS / meta["model_file"]).stat().st_size < 100_000
