"""Classifier service.

Subscribes to every board's IMU topic, validates each message against the
contract, keeps a 2 s sliding window per device, classifies it once per
second with the exported ONNX model, and stores the result in PostgreSQL.
"""

import logging
import os
import signal
import time
from pathlib import Path

import paho.mqtt.client as mqtt

from payload import PayloadError, parse_imu_message
from pipeline import Classifier
from predictor import Model
from store import PredictionWriter

TOPIC = "activity/+/imu"
HEALTH_FILE = Path("/tmp/healthy")  # present while connected; used by the Compose healthcheck

log = logging.getLogger("classifier")


def on_connect(client, classifier, flags, reason_code, properties):
    if reason_code.is_failure:
        log.error("MQTT connection refused: %s", reason_code)
        return
    client.subscribe(TOPIC, qos=0)
    HEALTH_FILE.touch()
    log.info("connected to broker, subscribed to %s", TOPIC)


def on_disconnect(client, classifier, flags, reason_code, properties):
    HEALTH_FILE.unlink(missing_ok=True)
    log.warning("disconnected from broker: %s", reason_code)


def on_message(client, classifier: Classifier, msg):
    try:
        batch = parse_imu_message(msg.topic, msg.payload)
    except PayloadError as exc:
        log.warning("invalid message on %s: %s", msg.topic, exc)
        return
    classifier.handle(batch, now_monotonic=time.monotonic(), now_ms=int(time.time() * 1000))


def main() -> None:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    model = Model(Path(os.environ.get("MODEL_DIR", "/srv/model")))
    log.info("model loaded: window=%d samples at %d Hz, labels=%s",
             model.window, model.rate_hz, model.labels)
    classifier = Classifier(model, PredictionWriter(os.environ.get("DATABASE_URL", "")))

    host = os.environ.get("MQTT_HOST", "mosquitto")
    port = int(os.environ.get("MQTT_PORT", "1883"))
    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2, client_id="activity-classifier", userdata=classifier
    )
    client.username_pw_set(os.environ["MQTT_USERNAME"], os.environ["MQTT_PASSWORD"])
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    client.reconnect_delay_set(min_delay=1, max_delay=30)

    # Docker stops containers with SIGTERM; disconnecting ends loop_forever cleanly.
    signal.signal(signal.SIGTERM, lambda *_: client.disconnect())

    log.info("connecting to %s:%d", host, port)
    client.connect_async(host, port, keepalive=30)
    client.loop_forever(retry_first_connection=True)


if __name__ == "__main__":
    main()
