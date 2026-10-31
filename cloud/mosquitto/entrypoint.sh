#!/bin/sh
# Starts Mosquitto with password auth. The password file is rebuilt on every
# start from MQTT_USERNAME / MQTT_PASSWORD (set in cloud/.env), so no
# credentials are stored in the repo.
set -eu

: "${MQTT_USERNAME:?MQTT_USERNAME is not set (see cloud/.env.example)}"
: "${MQTT_PASSWORD:?MQTT_PASSWORD is not set (see cloud/.env.example)}"

cp /opt/mqtt/mosquitto.conf /mosquitto/config/mosquitto.conf

passwd=/mosquitto/config/passwd
rm -f "$passwd"
mosquitto_passwd -c -b "$passwd" "$MQTT_USERNAME" "$MQTT_PASSWORD"
chmod 0700 "$passwd"
chown mosquitto:mosquitto "$passwd"
chown -R mosquitto:mosquitto /mosquitto/data

exec mosquitto -c /mosquitto/config/mosquitto.conf
