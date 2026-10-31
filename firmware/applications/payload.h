/*
 * Builds the JSON message from docs/CONTRACTS.md, section 3:
 *   {"device_id":"rtspark-01","ts":<unix ms>,"rate_hz":5,"samples":[[ax,ay,az,gx,gy,gz],...]}
 *
 * Plain C with no RT-Thread or printf dependency (RT-Thread's printf cannot
 * print floats), so it is also compiled and tested on the host
 * (firmware/tests/test_payload.py).
 */
#ifndef PAYLOAD_H
#define PAYLOAD_H

#include <stddef.h>
#include <stdint.h>

/*
 * Writes the message into buf (always NUL-terminated when size > 0).
 * Values are written with 4 decimal places. Returns the length written, or -1
 * if buf is too small.
 */
int payload_format(char *buf, size_t size, const char *device_id, uint64_t ts_ms,
                   int rate_hz, const float (*samples)[6], int count);

/*
 * Reads the classifier's prediction message (docs/CONTRACTS.md, section 3):
 *   {"activity":"run","confidence":0.9735,"ts":1761800000123}
 * `json` need not be NUL-terminated (MQTT payloads aren't). On success writes the
 * label into `activity` and the confidence as a rounded percentage, and returns 0;
 * returns -1 if a field is missing or malformed.
 */
int prediction_parse(const char *json, size_t len, char *activity, size_t activity_size,
                     int *confidence_pct);

#endif /* PAYLOAD_H */
