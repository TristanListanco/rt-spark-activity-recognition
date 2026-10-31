#include "imu.h"

#include <icm20608.h>

#include "clock.h"
#include "label.h"

#define DBG_TAG "imu"
#define DBG_LVL DBG_INFO
#include <rtdbg.h>

/*
 * Ranges chosen to cover the dataset (up to 5.6 g and 11 rad/s ≈ 650 °/s while
 * running; see docs/ml-report.md), with headroom.
 * The driver's calibration (icm20608_calib_level) is deliberately not used: it
 * subtracts gravity as if the board lay flat, but the model expects
 * acceleration *with* gravity (contract section 2).
 */
#define ACCEL_RANGE      ICM20608_ACCELEROMETER_RANGE2 /* ±8 g */
#define ACCEL_LSB_PER_G  4096.0f
#define GYRO_RANGE       ICM20608_GYROSCOPE_RANGE2     /* ±1000 °/s */
#define GYRO_LSB_PER_DPS 32.8f
#define ACCEL_DLPF_21HZ  4 /* ACCEL_CONFIG2: A_DLPF_CFG = 4, ~21 Hz bandwidth */
#define DEG_TO_RAD       0.017453292519943295f

static icm20608_device_t icm;
static rt_mq_t batches;
static struct imu_batch latest; /* last full batch, for the imu_read command */
static float newest[IMU_AXES];   /* last single sample, for the display */
static volatile rt_bool_t has_newest;
static rt_uint32_t read_errors, dropped_batches;

static rt_err_t read_sample(float out[IMU_AXES])
{
    rt_int16_t ax, ay, az, gx, gy, gz;
    if (icm20608_get_accel(icm, &ax, &ay, &az) != RT_EOK ||
        icm20608_get_gyro(icm, &gx, &gy, &gz) != RT_EOK)
    {
        return -RT_ERROR;
    }
    out[0] = ax / ACCEL_LSB_PER_G;
    out[1] = ay / ACCEL_LSB_PER_G;
    out[2] = az / ACCEL_LSB_PER_G;
    out[3] = gx / GYRO_LSB_PER_DPS * DEG_TO_RAD;
    out[4] = gy / GYRO_LSB_PER_DPS * DEG_TO_RAD;
    out[5] = gz / GYRO_LSB_PER_DPS * DEG_TO_RAD;
    return RT_EOK;
}

static void sampler_entry(void *parameter)
{
    struct imu_batch batch;
    int count = 0;
    const rt_tick_t period = rt_tick_from_millisecond(1000 / IMU_RATE_HZ);
    rt_tick_t next = rt_tick_get();

    for (;;)
    {
        if (count == 0)
        {
            batch.ts_ms = clock_now_ms();
            batch.label = label_current();
        }
        if (read_sample(batch.samples[count]) == RT_EOK)
        {
            rt_base_t level = rt_hw_interrupt_disable();
            rt_memcpy(newest, batch.samples[count], sizeof(newest));
            has_newest = RT_TRUE;
            rt_hw_interrupt_enable(level);
            count++;
        }
        else if (read_errors++ % 50 == 0)
        {
            LOG_W("IMU read failed (%u so far)", read_errors);
        }

        if (count == IMU_RATE_HZ)
        {
            latest = batch;
            /* Never block the sampler: if the network side is behind, drop this batch. */
            if (rt_mq_send(batches, &batch, sizeof(batch)) != RT_EOK)
                dropped_batches++;
            count = 0;
        }
        rt_thread_delay_until(&next, period); /* fixed 200 ms grid, no drift */
    }
}

rt_err_t imu_start(rt_mq_t out)
{
    rt_thread_t thread;

    icm = icm20608_init(IMU_I2C_BUS);
    if (icm == RT_NULL)
    {
        LOG_E("ICM-20608 not found on %s", IMU_I2C_BUS);
        return -RT_ERROR;
    }
    if (icm20608_set_param(icm, ICM20608_ACCEL_CONFIG1, ACCEL_RANGE) != RT_EOK ||
        icm20608_set_param(icm, ICM20608_GYRO_CONFIG, GYRO_RANGE) != RT_EOK ||
        icm20608_set_param(icm, ICM20608_ACCEL_CONFIG2, ACCEL_DLPF_21HZ) != RT_EOK)
    {
        LOG_E("could not configure ICM-20608 ranges");
        return -RT_ERROR;
    }

    batches = out;
    thread = rt_thread_create("imu", sampler_entry, RT_NULL, 2048, 10, 10);
    if (thread == RT_NULL)
        return -RT_ENOMEM;
    rt_thread_startup(thread);
    LOG_I("sampling at %d Hz (±8 g, ±1000 dps)", IMU_RATE_HZ);
    return RT_EOK;
}

rt_bool_t imu_get_latest(float out[IMU_AXES])
{
    rt_base_t level = rt_hw_interrupt_disable();
    rt_memcpy(out, newest, sizeof(newest));
    rt_hw_interrupt_enable(level);
    return has_newest;
}

/* msh command: print the newest batch, to check units (at rest |a| should be about 1 g). */
static void imu_read(void)
{
    char line[96];
    int i;
    if (icm == RT_NULL)
    {
        rt_kprintf("IMU not started\n");
        return;
    }
    for (i = 0; i < IMU_RATE_HZ; i++)
    {
        const float *s = latest.samples[i];
        /* rt_kprintf has no %f: print milli-units as integers */
        rt_snprintf(line, sizeof(line), "a[mg] %6d %6d %6d   w[mrad/s] %6d %6d %6d\n",
                    (int)(s[0] * 1000), (int)(s[1] * 1000), (int)(s[2] * 1000),
                    (int)(s[3] * 1000), (int)(s[4] * 1000), (int)(s[5] * 1000));
        rt_kprintf("%s", line);
    }
    rt_kprintf("read errors: %u, dropped batches: %u\n", read_errors, dropped_batches);
}
MSH_CMD_EXPORT(imu_read, print the last second of IMU samples);
