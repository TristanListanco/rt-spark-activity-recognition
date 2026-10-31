"""Compile the firmware's payload.c on the host and check it against the cloud's code.

Both directions: the board's IMU message must pass the classifier's validator, and
the board must read the prediction message exactly as the classifier writes it.
This catches format mismatches before flashing. Needs a C compiler (cc).
"""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

FIRMWARE = Path(__file__).resolve().parents[1]
REPO = FIRMWARE.parent
sys.path.insert(0, str(REPO / "cloud" / "classifier"))

from payload import parse_imu_message  # noqa: E402  (the classifier's validator)
from pipeline import prediction_message  # noqa: E402  (what the classifier publishes back)
from predictor import Prediction  # noqa: E402

SAMPLES = [
    [0.0, -0.98, 0.05, 0.01, -2.5, 11.27],
    [1.23456, -0.00004, 5.6, -5.35, -9.48, 0.0],
    [-1.0, 2.0, -3.0, 0.1234, -0.1234, 7.9999],
    [0.5, 0.25, 0.125, 0.0625, 0.03125, 0.015625],
    [7.99, -7.99, 0.0001, -0.0001, 1.0, -1.0],
]
TOPIC = "activity/rtspark-01/imu"


@pytest.fixture(scope="module")
def exe(tmp_path_factory) -> Path:
    cc = shutil.which("cc") or shutil.which("gcc")
    if cc is None:
        pytest.skip("no C compiler")
    exe = tmp_path_factory.mktemp("payload") / "payload_main"
    subprocess.run(
        [cc, "-std=c99", "-Wall", "-Wextra", "-Werror", "-I", str(FIRMWARE / "applications"),
         str(FIRMWARE / "applications" / "payload.c"), str(FIRMWARE / "tests" / "payload_main.c"),
         "-o", str(exe)],
        check=True,
    )
    return exe


@pytest.fixture(scope="module")
def results(exe) -> list[tuple[int, str]]:
    lines = subprocess.run([str(exe)], check=True, capture_output=True, text=True).stdout
    out = []
    for line in lines.splitlines():
        code, _, text = line.partition(" ")
        out.append((int(code), text))
    return out


def test_message_passes_the_classifier_validator(results):
    length, text = results[0]
    assert length == len(text)
    batch = parse_imu_message(TOPIC, text.encode())
    assert batch.device_id == "rtspark-01"
    assert batch.ts == 1_761_800_000_123
    assert batch.rate_hz == 5
    # 4 decimals → at most 0.5e-4 rounding error (e.g. 0.03125 → 0.0313), plus float noise
    for got, want in zip(batch.samples, SAMPLES, strict=True):
        assert got == pytest.approx(want, abs=0.51e-4)


def test_four_decimal_formatting(results):
    text = results[0][1]
    assert '"samples":[[0.0000,-0.9800,0.0500,0.0100,-2.5000,11.2700],' in text
    assert "1.2346" in text  # rounded, not truncated
    assert text.startswith('{"device_id":"rtspark-01","ts":1761800000123,"rate_hz":5,')


def test_unsynced_clock_sends_ts_zero(results):
    assert parse_imu_message(TOPIC, results[1][1].encode()).ts == 0


def test_label_is_added_while_recording(results):
    length, text = results[4]
    assert length == len(text)
    assert '"rate_hz":5,"label":"run","samples"' in text
    assert parse_imu_message(TOPIC, text.encode()).rate_hz == 5  # the classifier ignores it
    assert '"label"' not in results[0][1]  # absent when not recording


def test_buffer_boundaries(results):
    full_length = results[0][0]
    assert results[2] == (full_length, results[0][1])  # exact fit works
    assert results[3] == (-1, "")  # one byte short fails cleanly


def board_parse(exe: Path, text: str) -> tuple[int, str, int]:
    out = subprocess.run([str(exe), "parse", text], check=True, capture_output=True, text=True)
    code, activity, pct = out.stdout.split()
    return int(code), activity, int(pct)


@pytest.mark.parametrize(
    ("activity", "confidence", "pct"),
    [("run", 0.973456, 97), ("walk", 0.5, 50), ("walk", 1.0, 100), ("run", 0.99996, 100),
     ("walk", 0.005, 1)],
)
def test_board_reads_the_classifier_prediction(exe, activity, confidence, pct):
    message = prediction_message(Prediction(activity, confidence), 1_761_800_000_123)
    assert board_parse(exe, message) == (0, activity, pct)


def test_prediction_parse_tolerates_spacing_and_order(exe):
    assert board_parse(exe, '{ "confidence" : 0.8 , "activity" : "run" }') == (0, "run", 80)


@pytest.mark.parametrize(
    "text",
    [
        "",
        '{"activity":"run"}',
        '{"confidence":0.9}',
        '{"activity":"run","confidence":"high"}',
        '{"activity":"run","confidence":2.5}',
        '{"activity":"sprinting","confidence":0.9}',  # longer than the 8-byte buffer
        '{"activity":"","confidence":0.9}',
        '{"activity":"run,"confidence":0.9',
    ],
)
def test_prediction_parse_rejects_bad_messages(exe, text):
    assert board_parse(exe, text) == (-1, "-", -1)
