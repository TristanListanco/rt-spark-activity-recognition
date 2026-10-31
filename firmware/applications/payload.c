#include "payload.h"

#include <string.h>

struct writer
{
    char *p;
    size_t left;
    int ok;
};

static void put_str(struct writer *w, const char *s)
{
    size_t n = strlen(s);
    if (!w->ok || n >= w->left)
    {
        w->ok = 0;
        return;
    }
    memcpy(w->p, s, n);
    w->p += n;
    w->left -= n;
}

static void put_u64(struct writer *w, uint64_t v)
{
    char digits[21];
    int i = sizeof(digits) - 1;
    digits[i] = '\0';
    do
    {
        digits[--i] = (char)('0' + v % 10);
        v /= 10;
    } while (v);
    put_str(w, &digits[i]);
}

/* v with exactly 4 decimals, rounded half away from zero, e.g. -0.98 -> "-0.9800". */
static void put_fixed4(struct writer *w, float v)
{
    char frac[6];
    uint64_t scaled;
    if (v < 0)
    {
        v = -v;
        put_str(w, "-");
    }
    scaled = (uint64_t)(v * 10000.0f + 0.5f);
    put_u64(w, scaled / 10000);
    frac[0] = '.';
    frac[1] = (char)('0' + (scaled / 1000) % 10);
    frac[2] = (char)('0' + (scaled / 100) % 10);
    frac[3] = (char)('0' + (scaled / 10) % 10);
    frac[4] = (char)('0' + scaled % 10);
    frac[5] = '\0';
    put_str(w, frac);
}

int payload_format(char *buf, size_t size, const char *device_id, uint64_t ts_ms,
                   int rate_hz, const float (*samples)[6], int count)
{
    struct writer w = {buf, size, size > 0};
    int i, j;

    put_str(&w, "{\"device_id\":\"");
    put_str(&w, device_id);
    put_str(&w, "\",\"ts\":");
    put_u64(&w, ts_ms);
    put_str(&w, ",\"rate_hz\":");
    put_u64(&w, (uint64_t)rate_hz);
    put_str(&w, ",\"samples\":[");
    for (i = 0; i < count; i++)
    {
        put_str(&w, i ? ",[" : "[");
        for (j = 0; j < 6; j++)
        {
            if (j)
                put_str(&w, ",");
            put_fixed4(&w, samples[i][j]);
        }
        put_str(&w, "]");
    }
    put_str(&w, "]}");

    if (!w.ok)
    {
        if (size > 0)
            buf[0] = '\0';
        return -1;
    }
    *w.p = '\0';
    return (int)(w.p - buf);
}

/* Position just after `"key"` followed by optional spaces and a colon, or NULL. */
static const char *after_key(const char *json, size_t len, const char *key)
{
    size_t klen = strlen(key);
    size_t i;
    for (i = 0; i + klen + 2 <= len; i++)
    {
        const char *p = json + i;
        const char *end = json + len;
        if (p[0] != '"' || memcmp(p + 1, key, klen) != 0 || p[klen + 1] != '"')
            continue;
        p += klen + 2;
        while (p < end && (*p == ' ' || *p == '\t'))
            p++;
        if (p >= end || *p != ':')
            continue;
        p++;
        while (p < end && (*p == ' ' || *p == '\t'))
            p++;
        return p;
    }
    return NULL;
}

int prediction_parse(const char *json, size_t len, char *activity, size_t activity_size,
                     int *confidence_pct)
{
    const char *end = json + len;
    const char *p;
    size_t n = 0;
    long whole = 0, frac = 0, scale = 1;

    /* "activity": "<label>" */
    p = after_key(json, len, "activity");
    if (p == NULL || p >= end || *p != '"' || activity_size == 0)
        return -1;
    for (p++; p < end && *p != '"'; p++)
    {
        if (n + 1 >= activity_size || *p < 'a' || *p > 'z') /* labels are lowercase words */
            return -1;
        activity[n++] = *p;
    }
    if (p >= end || n == 0)
        return -1;
    activity[n] = '\0';

    /* "confidence": <number between 0 and 1>, read without floating-point parsing */
    p = after_key(json, len, "confidence");
    if (p == NULL || p >= end || *p < '0' || *p > '9')
        return -1;
    for (; p < end && *p >= '0' && *p <= '9' && whole < 10; p++) /* stop before overflow */
        whole = whole * 10 + (*p - '0');
    if (p < end && *p == '.')
    {
        for (p++; p < end && *p >= '0' && *p <= '9' && scale < 100000; p++)
        {
            frac = frac * 10 + (*p - '0');
            scale *= 10;
        }
    }
    if (whole > 1)
        return -1;
    /* percentage = (whole + frac/scale) * 100, rounded */
    *confidence_pct = (int)(whole * 100 + (frac * 100 + scale / 2) / scale);
    return 0;
}
