/* Samples the on-board ICM-20608 at IMU_RATE_HZ and hands out one-second batches. */
#ifndef IMU_H
#define IMU_H

#include <rtthread.h>
#include <stdint.h>

#include "app_config.h"

struct imu_batch
{
    uint64_t ts_ms; /* Unix ms of the first sample, 0 if the clock is not synced yet */
    float samples[IMU_RATE_HZ][IMU_AXES];
};

/* Initialise the sensor and start sampling; full batches are sent to `out`. */
rt_err_t imu_start(rt_mq_t out);

#endif /* IMU_H */
