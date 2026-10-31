/*
 * Host-side driver for payload.c, used by test_firmware_payload.py.
 *
 *   payload_main             prints payload_format() results, one per line: "<return> <json>"
 *   payload_main parse JSON  prints prediction_parse() of JSON: "<return> <activity> <percent>"
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

static int parse_mode(const char *json)
{
    char activity[8] = "";
    int pct = -1;
    int rc = prediction_parse(json, strlen(json), activity, sizeof(activity), &pct);
    printf("%d %s %d\n", rc, rc == 0 ? activity : "-", rc == 0 ? pct : -1);
    return 0;
}

int main(int argc, char **argv)
{
    char buf[768];
    int full, n;

    if (argc == 3 && strcmp(argv[1], "parse") == 0)
        return parse_mode(argv[2]);

    /* 1: a normal message */
    full = payload_format(buf, sizeof(buf), "rtspark-01", 1761800000123ULL, 5, SAMPLES, 5, NULL);
    printf("%d %s\n", full, buf);

    /* 2: clock not synced yet → ts 0 */
    n = payload_format(buf, sizeof(buf), "rtspark-01", 0, 5, SAMPLES, 5, NULL);
    printf("%d %s\n", n, buf);

    /* 3: exactly enough room (length + NUL) */
    n = payload_format(buf, (size_t)full + 1, "rtspark-01", 1761800000123ULL, 5, SAMPLES, 5, NULL);
    printf("%d %s\n", n, buf);

    /* 4: one byte short → -1 and an empty string */
    n = payload_format(buf, (size_t)full, "rtspark-01", 1761800000123ULL, 5, SAMPLES, 5, NULL);
    printf("%d %s\n", n, buf);

    /* 5: while recording training data, with a label */
    n = payload_format(buf, sizeof(buf), "rtspark-01", 1761800000123ULL, 5, SAMPLES, 5, "run");
    printf("%d %s\n", n, buf);
    return 0;
}
