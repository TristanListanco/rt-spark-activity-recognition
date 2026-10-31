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
