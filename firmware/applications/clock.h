/* Wall-clock time from NTP, kept with the system tick between syncs. */
#ifndef CLOCK_H
#define CLOCK_H

#include <rtthread.h>
#include <stdint.h>

/* Ask an NTP server for the time. Needs a working network; blocks a few seconds. */
rt_bool_t clock_sync(void);

rt_bool_t clock_is_synced(void);

/* Unix time in milliseconds, or 0 before the first successful sync (contract: ts = 0). */
uint64_t clock_now_ms(void);

#endif /* CLOCK_H */
