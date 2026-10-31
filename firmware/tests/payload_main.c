/*
 * Host-side driver for payload.c: prints one result per line as "<return value> <json>"
 * so test_firmware_payload.py can check the output against the cloud's parser.
 */
#include <stdio.h>
#include <string.h>

#include "payload.h"

static const float SAMPLES[5][6] = {
    {0.0f, -0.98f, 0.05f, 0.01f, -2.5f, 11.27f},
    {1.23456f, -0.00004f, 5.6f, -5.35f, -9.48f, 0.0f},
    {-1.0f, 2.0f, -3.0f, 0.1234f, -0.1234f, 7.9999f},
    {0.5f, 0.25f, 0.125f, 0.0625f, 0.03125f, 0.015625f},
    {7.99f, -7.99f, 0.0001f, -0.0001f, 1.0f, -1.0f},
};

int main(void)
{
    char buf[768];
    int full, n;

    /* 1: a normal message */
    full = payload_format(buf, sizeof(buf), "rtspark-01", 1761800000123ULL, 5, SAMPLES, 5);
    printf("%d %s\n", full, buf);

    /* 2: clock not synced yet → ts 0 */
    n = payload_format(buf, sizeof(buf), "rtspark-01", 0, 5, SAMPLES, 5);
    printf("%d %s\n", n, buf);

    /* 3: exactly enough room (length + NUL) */
    n = payload_format(buf, (size_t)full + 1, "rtspark-01", 1761800000123ULL, 5, SAMPLES, 5);
    printf("%d %s\n", n, buf);

    /* 4: one byte short → -1 and an empty string */
    n = payload_format(buf, (size_t)full, "rtspark-01", 1761800000123ULL, 5, SAMPLES, 5);
    printf("%d %s\n", n, buf);
    return 0;
}
