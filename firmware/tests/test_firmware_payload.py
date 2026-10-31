"""Compile the firmware's payload.c on the host and check its JSON with the cloud's parser.

This catches format mismatches between the board and the classifier before flashing.
Needs a C compiler (cc); skipped otherwise.
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

SAMPLES = [
    [0.0, -0.98, 0.05, 0.01, -2.5, 11.27],
    [1.23456, -0.00004, 5.6, -5.35, -9.48, 0.0],
    [-1.0, 2.0, -3.0, 0.1234, -0.1234, 7.9999],
    [0.5, 0.25, 0.125, 0.0625, 0.03125, 0.015625],
    [7.99, -7.99, 0.0001, -0.0001, 1.0, -1.0],
]
TOPIC = "activity/rtspark-01/imu"


@pytest.fixture(scope="module")
def results(tmp_path_factory) -> list[tuple[int, str]]:
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


def test_buffer_boundaries(results):
    full_length = results[0][0]
    assert results[2] == (full_length, results[0][1])  # exact fit works
    assert results[3] == (-1, "")  # one byte short fails cleanly
