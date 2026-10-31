/* Samples the on-board ICM-20608 at IMU_RATE_HZ and hands out one-second batches. */
#ifndef IMU_H
#define IMU_H

#include <rtthread.h>
#include <stdint.h>

#include "app_config.h"

struct imu_batch
{
    uint64_t ts_ms;    /* Unix ms of the first sample, 0 if the clock is not synced yet */
    const char *label; /* recording label when the first sample was taken (label.h), or RT_NULL */
    float samples[IMU_RATE_HZ][IMU_AXES];
};

/* Initialise the sensor and start sampling; full batches are sent to `out`. */
rt_err_t imu_start(rt_mq_t out);

/* Copy the newest sample (g, rad/s). Returns RT_FALSE if nothing was read yet. */
rt_bool_t imu_get_latest(float out[IMU_AXES]);

#endif /* IMU_H */
