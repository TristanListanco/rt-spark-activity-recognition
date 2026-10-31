"""Publish fake IMU messages in the board's format (docs/CONTRACTS.md, section 3).

Stands in for the RT-Spark board so the cloud stack can be tested without
hardware. By default it generates synthetic walk/run signals (good enough to
test the plumbing, not the model). With --csv it replays real rows from the
Kaggle run-or-walk dataset instead.

MQTT credentials are read from cloud/.env unless given as options.

Examples:
  python tools/fake_publisher.py                          # alternate walk/run every 30 s
  python tools/fake_publisher.py --activity run --count 10
  python tools/fake_publisher.py --csv ml/data/dataset.csv --activity walk
"""

import argparse
import csv
import itertools
import json
import math
import os
import random
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import paho.mqtt.client as mqtt

ENV_FILE = Path(__file__).resolve().parent.parent / "cloud" / ".env"
SENSOR_COLUMNS = [
    "acceleration_x",
    "acceleration_y",
    "acceleration_z",
    "gyro_x",
    "gyro_y",
    "gyro_z",
]
DATASET_LABELS = {"walk": "0", "run": "1"}

# Synthetic signal per activity: (step frequency in Hz, accel amplitude, gyro amplitude)
SYNTHETIC = {"walk": (1.8, 0.35, 1.0), "run": (2.8, 1.2, 3.0)}


def load_env_file(path: Path) -> None:
    """Load KEY=VALUE lines into os.environ without overriding existing variables."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def synthetic_rows(activity: str, rate: int) -> Iterator[list[float]]:
    freq, acc_amp, gyro_amp = SYNTHETIC[activity]
    for n in itertools.count():
        phase = 2 * math.pi * freq * n / rate
        yield [
            round(acc_amp * math.sin(phase + offset) + random.gauss(0, 0.03), 4)
            for offset in (0.0, 1.0, 2.0)
        ] + [
            round(gyro_amp * math.cos(phase + offset) + random.gauss(0, 0.05), 4)
            for offset in (0.0, 1.0, 2.0)
        ]


def dataset_rows(csv_path: Path, activity: str) -> Iterator[list[float]]:
    """Rows of one activity from the Kaggle CSV, in recorded order, looping forever."""
    with csv_path.open(newline="") as f:
        rows = [
            [float(row[col]) for col in SENSOR_COLUMNS]
            for row in csv.DictReader(f)
            if row["activity"].strip() == DATASET_LABELS[activity]
        ]
    if not rows:
        sys.exit(f"No {activity} rows found in {csv_path}")
    return itertools.cycle(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--host", default=os.environ.get("MQTT_HOST", "localhost"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("MQTT_PORT", "1883")))
    parser.add_argument("--username", default=os.environ.get("MQTT_USERNAME"))
    parser.add_argument("--password", default=os.environ.get("MQTT_PASSWORD"))
    parser.add_argument("--device-id", default="rtspark-01")
    parser.add_argument("--rate", type=int, default=5, help="samples per second (R)")
    parser.add_argument("--activity", choices=["walk", "run", "alternate"], default="alternate")
    parser.add_argument("--switch-every", type=int, default=30, help="seconds per activity")
    parser.add_argument("--count", type=int, default=0, help="messages to send (0 = forever)")
    parser.add_argument("--csv", type=Path, help="replay the Kaggle run-or-walk CSV")
    return parser.parse_args()


def main() -> None:
    load_env_file(ENV_FILE)
    args = parse_args()
    if not args.username or not args.password:
        sys.exit("MQTT credentials missing: create cloud/.env or pass --username/--password")

    activities = ["walk", "run"] if args.activity == "alternate" else [args.activity]
    if args.csv:
        sources = {a: dataset_rows(args.csv, a) for a in activities}
    else:
        sources = {a: synthetic_rows(a, args.rate) for a in activities}

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.username_pw_set(args.username, args.password)
    try:
        client.connect(args.host, args.port, keepalive=30)
    except OSError as exc:
        sys.exit(f"Cannot reach MQTT broker at {args.host}:{args.port}: {exc}")
    client.loop_start()

    topic = f"activity/{args.device_id}/imu"
    print(f"Publishing to {topic} on {args.host}:{args.port} (Ctrl-C to stop)")
    start = time.monotonic()
    try:
        for n in itertools.count():
            if args.count and n >= args.count:
                break
            activity = activities[(n // args.switch_every) % len(activities)]
            samples = list(itertools.islice(sources[activity], args.rate))
            payload = {
                "device_id": args.device_id,
                "ts": int(time.time() * 1000) - 1000,  # first sample was ~1 s ago
                "rate_hz": args.rate,
                "samples": samples,
            }
            info = client.publish(topic, json.dumps(payload), qos=0)
            info.wait_for_publish(timeout=5)
            print(f"[{n + 1}] {activity}: {len(samples)} samples")
            time.sleep(max(0.0, start + n + 1 - time.monotonic()))
    except KeyboardInterrupt:
        pass
    finally:
        client.disconnect()
        client.loop_stop()


if __name__ == "__main__":
    main()
