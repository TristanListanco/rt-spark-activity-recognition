"""Classifier service.

M1: subscribes to the board's IMU topic and validates every message against
the contract, logging what arrives. M3 adds the sliding window, the ONNX model
and writing predictions to PostgreSQL.
"""

import logging
import os
import signal
from pathlib import Path

import paho.mqtt.client as mqtt

from payload import PayloadError, parse_imu_message

TOPIC = "activity/+/imu"
HEALTH_FILE = Path("/tmp/healthy")  # present while connected; used by the Compose healthcheck

log = logging.getLogger("classifier")


def on_connect(client, userdata, flags, reason_code, properties):
    if reason_code.is_failure:
        log.error("MQTT connection refused: %s", reason_code)
        return
    client.subscribe(TOPIC, qos=0)
    HEALTH_FILE.touch()
    log.info("connected to broker, subscribed to %s", TOPIC)


def on_disconnect(client, userdata, flags, reason_code, properties):
    HEALTH_FILE.unlink(missing_ok=True)
    log.warning("disconnected from broker: %s", reason_code)


def on_message(client, userdata, msg):
    try:
        batch = parse_imu_message(msg.topic, msg.payload)
    except PayloadError as exc:
        log.warning("invalid message on %s: %s", msg.topic, exc)
        return
    log.info(
        "received device=%s rate=%dHz samples=%d ts=%d",
        batch.device_id,
        batch.rate_hz,
        len(batch.samples),
        batch.ts,
    )


def main() -> None:
    logging.basicConfig(
        level=os.environ.get("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    host = os.environ.get("MQTT_HOST", "mosquitto")
    port = int(os.environ.get("MQTT_PORT", "1883"))

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="activity-classifier")
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
