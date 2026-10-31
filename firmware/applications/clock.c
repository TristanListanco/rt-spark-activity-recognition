#include "clock.h"

#include <ntp.h>

#define DBG_TAG "clock"
#define DBG_LVL DBG_INFO
#include <rtdbg.h>

/* Unix ms at tick-millisecond 0; written by the network thread, read by the IMU thread. */
static int64_t epoch_at_boot_ms;
static volatile rt_bool_t synced;

rt_bool_t clock_sync(void)
{
    rt_base_t level;
    time_t now = ntp_get_time(RT_NULL); /* tries the NETUTILS_NTP_HOSTNAME servers */
    if (now <= 0)
    {
        LOG_W("NTP sync failed; messages carry ts=0 until it succeeds");
        return RT_FALSE;
    }
    level = rt_hw_interrupt_disable(); /* 64-bit write is not atomic on Cortex-M4 */
    epoch_at_boot_ms = (int64_t)now * 1000 - (int64_t)rt_tick_get_millisecond();
    synced = RT_TRUE;
    rt_hw_interrupt_enable(level);
    LOG_I("time synced from NTP: %d", (int)now);
    return RT_TRUE;
}

rt_bool_t clock_is_synced(void)
{
    return synced;
}

uint64_t clock_now_ms(void)
{
    rt_base_t level;
    int64_t base;
    if (!synced)
        return 0;
    level = rt_hw_interrupt_disable();
    base = epoch_at_boot_ms;
    rt_hw_interrupt_enable(level);
    return (uint64_t)(base + (int64_t)rt_tick_get_millisecond());
}
