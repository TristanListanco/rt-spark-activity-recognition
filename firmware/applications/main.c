/*
 * RT-Spark activity-recognition firmware.
 *
 * Follows the lab's sequence: initialise the sensor, join Wi-Fi, connect to the
 * MQTT broker, then send the IMU readings every second (5 samples per message,
 * docs/CONTRACTS.md). The IMU samples on its own thread so a slow network never
 * disturbs the 5 Hz timing; batches travel to the network thread through a
 * message queue.
 *
 * The LCD shows the cloud's latest prediction and the board's status (display.c).
 * LEDs: blue blinks once a second while the firmware runs; red is lit while the
 * board is NOT connected to the MQTT broker.
 */
#include <board.h>
#include <drv_gpio.h>
#include <rtdevice.h>
#include <rtthread.h>

#include "display.h"
#include "imu.h"
#include "net.h"

#define DBG_TAG "main"
#define DBG_LVL DBG_INFO
#include <rtdbg.h>

#define LED_BLUE   GET_PIN(F, 11)
#define LED_RED    GET_PIN(F, 12)
#define LED_ON     PIN_LOW /* assumed active-low; swap with LED_OFF if the LEDs look inverted */
#define LED_OFF    PIN_HIGH
#define QUEUE_LEN  4       /* seconds of data buffered while the network catches up */

int main(void)
{
    rt_mq_t queue;
    int blue = LED_OFF;

    rt_pin_mode(LED_BLUE, PIN_MODE_OUTPUT);
    rt_pin_mode(LED_RED, PIN_MODE_OUTPUT);
    rt_pin_write(LED_RED, LED_ON);

    if (display_start() != RT_EOK) /* first, so the screen shows progress during start-up */
        LOG_W("display not started; continuing without it");

    queue = rt_mq_create("imu", sizeof(struct imu_batch), QUEUE_LEN, RT_IPC_FLAG_FIFO);
    if (queue == RT_NULL || imu_start(queue) != RT_EOK || net_start(queue) != RT_EOK)
    {
        LOG_E("startup failed; see the messages above");
        for (;;) /* fast red blink = fatal error */
        {
            rt_pin_write(LED_RED, LED_ON);
            rt_thread_mdelay(100);
            rt_pin_write(LED_RED, LED_OFF);
            rt_thread_mdelay(100);
        }
    }

    for (;;)
    {
        blue = (blue == LED_ON) ? LED_OFF : LED_ON;
        rt_pin_write(LED_BLUE, blue);
        rt_pin_write(LED_RED, net_is_online() ? LED_OFF : LED_ON);
        rt_thread_mdelay(500);
    }
}
