"""Record labelled IMU data from the board, to test and fine-tune the model on it (M7).

Set a label with the board's buttons (LEFT walk, RIGHT run, UP idle, DOWN stop):
while one is set, every message the board sends carries it. This script saves the
samples of those messages to a CSV, one row per sample, and ignores unlabelled
messages. MQTT credentials come from cloud/.env. Stop with Ctrl-C.

Examples:
  python tools/record.py --host rtspark-activity-b2093c.eastasia.cloudapp.azure.com
  python tools/record.py --host localhost --out ml/data/own/test.csv
"""

import argparse
import collections
import csv
import json
import os
import sys
import time
from pathlib import Path

import paho.mqtt.client as mqtt

from fake_publisher import ENV_FILE, load_env_file

COLUMNS = ["received_at_ms", "device_id", "label", "batch_ts_ms", "sample_index",
           "ax", "ay", "az", "gx", "gy", "gz"]
REPO = Path(__file__).resolve().parent.parent


def parse_args() -> argparse.Namespace:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--host", default=os.environ.get("MQTT_HOST", "localhost"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("MQTT_PORT", "1883")))
    parser.add_argument("--username", default=os.environ.get("MQTT_USERNAME"))
    parser.add_argument("--password", default=os.environ.get("MQTT_PASSWORD"))
    parser.add_argument("--device-id", default="rtspark-01")
    default_out = REPO / "ml" / "data" / "own" / f"rec-{stamp}.csv"
    parser.add_argument("--out", type=Path, default=default_out)
    return parser.parse_args()


def main() -> None:
    load_env_file(ENV_FILE)
    args = parse_args()
    if not args.username or not args.password:
        sys.exit("MQTT credentials missing: create cloud/.env or pass --username/--password")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    new_file = not args.out.exists()
    out = args.out.open("a", newline="")
    writer = csv.writer(out)
    if new_file:
        writer.writerow(COLUMNS)

    seconds = collections.Counter()  # one message = one second of data
    topic = f"activity/{args.device_id}/imu"

    def on_connect(client, userdata, flags, reason_code, properties):
        if reason_code.is_failure:
            print(f"MQTT connection refused: {reason_code}", file=sys.stderr)
            return
        client.subscribe(topic, qos=1)
        print(f"recording labelled messages from {topic} on {args.host} into {args.out}")
        print("on the board: LEFT = walk, RIGHT = run, UP = idle, DOWN = stop")

    def on_message(client, userdata, msg):
        try:
            body = json.loads(msg.payload)
        except json.JSONDecodeError:
            return
        label = body.get("label")
        if not label:
            return
        now = int(time.time() * 1000)
        for i, sample in enumerate(body.get("samples", [])):
            writer.writerow([now, body.get("device_id"), label, body.get("ts", 0), i, *sample])
        out.flush()
        seconds[label] += 1
        summary = ", ".join(f"{k} {v} s" for k, v in sorted(seconds.items()))
        print(f"\r{summary}   ", end="", flush=True)

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"recorder-{os.getpid()}")
    client.username_pw_set(args.username, args.password)
    client.on_connect = on_connect
    client.on_message = on_message
    client.reconnect_delay_set(min_delay=1, max_delay=10)
    client.connect(args.host, args.port, keepalive=30)
    try:
        client.loop_forever(retry_first_connection=True)
    except KeyboardInterrupt:
        pass
    finally:
        out.close()
        print(f"\nsaved {sum(seconds.values())} labelled seconds to {args.out}")


if __name__ == "__main__":
    main()
