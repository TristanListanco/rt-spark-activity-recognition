/*
 * Copy this file to secrets.h (same folder) and fill in real values.
 * secrets.h is git-ignored, so the Wi-Fi and MQTT passwords never reach GitHub.
 */
#ifndef SECRETS_H
#define SECRETS_H

/*
 * Known Wi-Fi networks, tried in this order at boot; the first one in range is used,
 * together with its broker address (the computer running the MQTT broker on that
 * network, e.g. your Mac's IP there; later the Azure VM). A hostname also works.
 * Networks must be 2.4 GHz and hand out IPv4 addresses (firmware/README.md).
 * Copy SSIDs exactly: iPhone hotspots use a curly apostrophe (Tristan’s iPhone).
 */
#define WIFI_NETWORKS                                                     \
    {"your-home-wifi", "your-home-wifi-password", "192.168.1.10"},        \
    {"your-phone-hotspot", "your-hotspot-password", "172.20.10.2"},

#define MQTT_PORT      1883
#define MQTT_USERNAME  "device"    /* from cloud/.env */
#define MQTT_PASSWORD  "change-me" /* from cloud/.env */

#endif /* SECRETS_H */
