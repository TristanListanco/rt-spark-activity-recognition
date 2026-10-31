/*
 * Copy this file to secrets.h (same folder) and fill in real values.
 * secrets.h is git-ignored, so the Wi-Fi and MQTT passwords never reach GitHub.
 */
#ifndef SECRETS_H
#define SECRETS_H

/* A 2.4 GHz network that gives out IPv4 addresses (e.g. a phone hotspot). */
#define WIFI_SSID      "your-wifi-name"
#define WIFI_PASSWORD  "your-wifi-password"

/* The MQTT broker: your Mac's IP on that network for now, the Azure VM later.
 * A hostname also works. Username and password are the ones in cloud/.env. */
#define MQTT_HOST      "192.168.1.10"
#define MQTT_PORT      1883
#define MQTT_USERNAME  "device"
#define MQTT_PASSWORD  "change-me"

#endif /* SECRETS_H */
