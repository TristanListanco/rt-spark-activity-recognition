/*
 * Screen layout (240 x 240):
 *
 *   rtspark-01             13:45:07     header: device and local time (NTP)
 *   ┌──────────────────────────────┐
 *   │           RUNNING            │    the cloud's latest prediction, coloured
 *   │        97% confident         │    blue (walk) / orange (run); grey if none
 *   └──────────────────────────────┘    has arrived for 5 s
 *   Wi-Fi  HomeWiFi
 *   IP     192.168.1.50
 *   MQTT   online
 *   Sent   1234   failed 0
 *   IMU    |a| 1.01g |w| 0.03
 *   Broker 172.20.10.2:1883
 *
 * Text is drawn opaque and padded to full width, and the coloured panel is only
 * refilled when the activity changes, so updating twice a second doesn't flicker.
 * Only this thread touches the LCD.
 */
#include "display.h"

#ifdef BSP_USING_ONBOARD_LCD

#include <drv_lcd.h>
#include <math.h>
#include <string.h>

#include "app_config.h"
#include "clock.h"
#include "imu.h"
#include "net.h"

#define DBG_TAG "display"
#define DBG_LVL DBG_INFO
#include <rtdbg.h>

#define FONT_S      16 /* 8 x 16 px glyphs */
#define FONT_L      32 /* 16 x 32 px glyphs */
#define MARGIN      8
#define COLS        28 /* FONT_S characters between the margins */
#define REFRESH_MS  500
#define STALE_MS    5000

#define PANEL_TOP   36
#define PANEL_BOT   120
#define TITLE_Y     (PANEL_TOP + 14)
#define SUBTITLE_Y  (PANEL_TOP + 56)
#define ROW_Y(i)    (128 + 18 * (i)) /* six 16 px rows */

/* The project's chart palette (dark-mode steps, docs/ml figures and the web page), RGB565 */
#define C_BG    0x18C3 /* #1a1a19 surface */
#define C_INK   0xF77D /* #f0efec primary text */
#define C_INK2  0xC616 /* #c3c2b7 secondary text */
#define C_MUTED 0x8C30 /* #898781 */
#define C_WALK  0x3C3C /* #3987e5 */
#define C_RUN   0xDAC4 /* #d95926 */
#define C_IDLE  0x4A49 /* #4a4a4a: no recent prediction */
#define C_GOOD  0x0D01 /* #0ca30c */
#define C_BAD   0xE32C /* #e66767 */
#define C_WHITE 0xFFFF

enum panel_kind
{
    PANEL_WAITING,
    PANEL_LIVE,
    PANEL_STALE,
};

/* What is currently on screen, to redraw only what changed. */
static struct
{
    enum panel_kind kind;
    char activity[8];
    char subtitle[COLS + 1];
} shown = {(enum panel_kind)-1, "", ""};

/* Copy `text` into a COLS-wide, space-padded line (left-aligned or centred). */
static void pad(char out[COLS + 1], const char *text, rt_bool_t centre)
{
    int len = (int)strlen(text);
    int left;
    if (len > COLS)
        len = COLS;
    left = centre ? (COLS - len) / 2 : 0;
    memset(out, ' ', COLS);
    memcpy(out + left, text, (size_t)len);
    out[COLS] = '\0';
}

static void draw_row(int index, rt_uint16_t colour, const char *label, const char *value)
{
    char text[COLS + 8], line[COLS + 1];
    rt_snprintf(text, sizeof(text), "%s%s", label, value);
    pad(line, text, RT_FALSE);
    lcd_set_color(C_BG, colour);
    lcd_show_string(MARGIN, ROW_Y(index), FONT_S, "%s", line);
}

/* The LCD font is ASCII only: keep ASCII, show curly quotes (as in iOS hotspot names,
 * "Tristan’s iPhone") as ', and anything else non-ASCII as ?. */
static void ascii_copy(char *out, rt_size_t size, const char *utf8)
{
    rt_size_t n = 0;
    const unsigned char *p = (const unsigned char *)utf8;
    while (*p && n + 1 < size)
    {
        if (*p < 0x80)
        {
            out[n++] = (char)*p++;
            continue;
        }
        if (p[0] == 0xE2 && p[1] == 0x80 && (p[2] == 0x98 || p[2] == 0x99))
            out[n++] = '\'';
        else
            out[n++] = '?';
        for (p++; (*p & 0xC0) == 0x80; p++) /* skip continuation bytes */
            ;
    }
    out[n] = '\0';
}

/* v >= 0 with two decimals, e.g. "1.01" (rt_snprintf has no %f) */
static void fmt2(char *buf, rt_size_t size, float v)
{
    int centi = (int)(v * 100.0f + 0.5f);
    rt_snprintf(buf, size, "%d.%02d", centi / 100, centi % 100);
}

static void draw_header(void)
{
    char clock_text[9] = "--:--:--";
    uint64_t now = clock_now_ms();
    if (now != 0)
    {
        uint32_t s = (uint32_t)((now / 1000 + LOCAL_UTC_OFFSET_MIN * 60) % 86400);
        rt_snprintf(clock_text, sizeof(clock_text), "%02u:%02u:%02u", s / 3600, s / 60 % 60, s % 60);
    }
    lcd_set_color(C_BG, C_INK2);
    lcd_show_string(MARGIN, 6, FONT_S, "%s", DEVICE_ID);
    lcd_set_color(C_BG, C_INK);
    lcd_show_string(LCD_W - MARGIN - 8 * 8, 6, FONT_S, "%s", clock_text);
}

static void draw_panel(const struct net_status *st)
{
    enum panel_kind kind;
    const char *title;
    char subtitle[COLS + 1], line[COLS + 1];
    rt_uint16_t colour;

    if (!st->has_prediction)
        kind = PANEL_WAITING;
    else if (st->prediction_age_ms > STALE_MS)
        kind = PANEL_STALE;
    else
        kind = PANEL_LIVE;

    if (kind == PANEL_WAITING)
        title = "WAITING";
    else if (strcmp(st->activity, "walk") == 0)
        title = "WALKING";
    else if (strcmp(st->activity, "run") == 0)
        title = "RUNNING";
    else
        title = st->activity;

    colour = C_IDLE;
    if (kind == PANEL_LIVE)
        colour = strcmp(st->activity, "run") == 0 ? C_RUN : C_WALK;

    /* Background and title: only when the state or the activity changes. */
    if (kind != shown.kind || strcmp(st->activity, shown.activity) != 0)
    {
        lcd_fill(MARGIN, PANEL_TOP, LCD_W - MARGIN, PANEL_BOT, colour);
        lcd_set_color(colour, C_WHITE);
        lcd_show_string((LCD_W - (int)strlen(title) * FONT_L / 2) / 2, TITLE_Y, FONT_L, "%s", title);
        shown.kind = kind;
        rt_strncpy(shown.activity, st->activity, sizeof(shown.activity));
        shown.subtitle[0] = '\0'; /* force the subtitle to redraw on the new background */
    }

    /* Subtitle: redrawn in place whenever its text changes. */
    if (kind == PANEL_WAITING)
        rt_snprintf(subtitle, sizeof(subtitle), "waiting for the cloud");
    else if (kind == PANEL_STALE)
        rt_snprintf(subtitle, sizeof(subtitle), "no update for %u s", st->prediction_age_ms / 1000);
    else
        rt_snprintf(subtitle, sizeof(subtitle), "%d%% confident", st->confidence_pct);
    if (strcmp(subtitle, shown.subtitle) != 0)
    {
        pad(line, subtitle, RT_TRUE);
        lcd_set_color(colour, C_WHITE);
        lcd_show_string(MARGIN, SUBTITLE_Y, FONT_S, "%s", line);
        rt_strncpy(shown.subtitle, subtitle, sizeof(shown.subtitle));
    }
}

static void draw_status(const struct net_status *st)
{
    char value[COLS + 1], a[8], w[8];
    float s[IMU_AXES];

    if (st->wifi_up && st->ssid != RT_NULL)
        ascii_copy(value, sizeof(value), st->ssid);
    else
        rt_strncpy(value, "joining...", sizeof(value));
    draw_row(0, st->wifi_up ? C_GOOD : C_BAD, "Wi-Fi  ", value);
    draw_row(1, C_INK2, "IP     ", st->ip[0] ? st->ip : "-");
    draw_row(2, st->mqtt_online ? C_GOOD : C_BAD, "MQTT   ", st->mqtt_online ? "online" : "offline");

    rt_snprintf(value, sizeof(value), "%u   failed %u", st->sent, st->failed);
    draw_row(3, st->failed ? C_BAD : C_INK, "Sent   ", value);

    if (imu_get_latest(s))
    {
        fmt2(a, sizeof(a), sqrtf(s[0] * s[0] + s[1] * s[1] + s[2] * s[2]));
        fmt2(w, sizeof(w), sqrtf(s[3] * s[3] + s[4] * s[4] + s[5] * s[5]));
        rt_snprintf(value, sizeof(value), "|a| %sg |w| %s", a, w);
        draw_row(4, C_INK, "IMU    ", value);
    }
    else
    {
        draw_row(4, C_BAD, "IMU    ", "no data");
    }

    draw_row(5, C_INK2, "Broker ", st->broker ? st->broker : "");
}

static void display_entry(void *parameter)
{
    struct net_status st;

    lcd_clear(C_BG);
    lcd_fill(MARGIN, 28, LCD_W - MARGIN, 29, C_MUTED); /* hairline under the header */

    for (;;)
    {
        net_get_status(&st);
        draw_header();
        draw_panel(&st);
        draw_status(&st);
        rt_thread_mdelay(REFRESH_MS);
    }
}

rt_err_t display_start(void)
{
    rt_thread_t thread = rt_thread_create("display", display_entry, RT_NULL, 2048, 20, 10);
    if (thread == RT_NULL)
        return -RT_ENOMEM;
    rt_thread_startup(thread);
    return RT_EOK;
}

#else /* BSP_USING_ONBOARD_LCD */

rt_err_t display_start(void)
{
    return RT_EOK;
}

#endif /* BSP_USING_ONBOARD_LCD */
