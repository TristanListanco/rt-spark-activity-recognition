/*
 * Copy this file to secrets.h (same folder) and fill in real values.
 * secrets.h is git-ignored, so the Wi-Fi and MQTT passwords never reach GitHub.
 */
#ifndef SECRETS_H
#define SECRETS_H

/*
 * Known Wi-Fi networks, tried in this order at boot; the first one in range is used,
 * together with its broker address: the Azure VM's host name (the same on every
 * network), or for the local stack the IP of the computer running it on that network.
 * Networks must be 2.4 GHz and hand out IPv4 addresses (firmware/README.md).
 * Copy SSIDs exactly: iPhone hotspots use a curly apostrophe (Tristan’s iPhone).
 */
#define WIFI_NETWORKS                                                     \
    {"your-home-wifi", "your-home-wifi-password", "rtspark-activity-b2093c.eastasia.cloudapp.azure.com"}, \
    {"your-phone-hotspot", "your-hotspot-password", "rtspark-activity-b2093c.eastasia.cloudapp.azure.com"},

#define MQTT_PORT      1883
#define MQTT_USERNAME  "device"    /* from cloud/.env */
#define MQTT_PASSWORD  "change-me" /* from cloud/.env */

#endif /* SECRETS_H */
