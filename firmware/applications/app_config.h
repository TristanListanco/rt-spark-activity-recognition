/*
 * Project settings shared by the firmware modules (see docs/CONTRACTS.md).
 * Wi-Fi and MQTT credentials live in secrets.h, which is not committed.
 */
#ifndef APP_CONFIG_H
#define APP_CONFIG_H

#define DEVICE_ID      "rtspark-01"
#define MQTT_TOPIC     "activity/" DEVICE_ID "/imu"

/* Contract section 2: 5 samples per second, sent as one message per second. */
#define IMU_RATE_HZ    5
#define IMU_AXES       6        /* ax, ay, az (g), gx, gy, gz (rad/s) */
#define IMU_I2C_BUS    "swi2c2" /* on-board ICM-20608, software I2C bus 2 */

#endif /* APP_CONFIG_H */
