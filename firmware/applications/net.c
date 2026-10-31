#include "net.h"

#include <netdb.h> /* must come before netdev.h (defines the IP address types) */
#include <netdev.h>
#include <paho_mqtt.h>
#include <rtdevice.h> /* Wi-Fi management API (drivers/wlan.h) */

#include "app_config.h"
#include "clock.h"
#include "imu.h"
#include "payload.h"

#if __has_include("secrets.h")
#include "secrets.h"
#else
#error "Copy applications/secrets.example.h to applications/secrets.h and fill it in"
#endif

#define DBG_TAG "net"
#define DBG_LVL DBG_INFO
#include <rtdbg.h>

#define WIFI_RETRY_MS     5000
#define NTP_RETRY_MS      60000
#define MQTT_BUF_SIZE     1024

static rt_mq_t batches;
static MQTTClient client;
static char uri[96];
static char json[768]; /* one message is about 400 bytes */
static rt_uint32_t sent, not_connected, failed;

static void wifi_connect(void)
{
    rt_wlan_set_mode(RT_WLAN_DEVICE_STA_NAME, RT_WLAN_STATION);
    rt_wlan_config_autoreconnect(RT_TRUE); /* the WLAN framework rejoins after drops */

    for (;;)
    {
        LOG_I("joining Wi-Fi \"%s\"", WIFI_SSID);
        if (rt_wlan_connect(WIFI_SSID, WIFI_PASSWORD) == RT_EOK)
            break;
        LOG_W("Wi-Fi join failed; retrying in %d s", WIFI_RETRY_MS / 1000);
        rt_thread_mdelay(WIFI_RETRY_MS);
    }
    while (!rt_wlan_is_ready()) /* wait for a DHCP address */
        rt_thread_mdelay(200);
    if (netdev_default != RT_NULL)
        LOG_I("Wi-Fi up, IP %s", inet_ntoa(netdev_default->ip_addr));
}

static void on_online(MQTTClient *c)
{
    LOG_I("MQTT connected to %s, publishing to %s", uri, MQTT_TOPIC);
}

static void on_offline(MQTTClient *c)
{
    LOG_W("MQTT disconnected; the client retries automatically");
}

static void on_message(MQTTClient *c, MessageData *msg)
{
    /* nothing is subscribed; required so stray messages are ignored safely */
}

static rt_err_t mqtt_start(void)
{
    MQTTPacket_connectData condata = MQTTPacket_connectData_initializer;

    rt_snprintf(uri, sizeof(uri), "tcp://%s:%d", MQTT_HOST, MQTT_PORT);
    rt_memset(&client, 0, sizeof(client));
    client.uri = uri;
    rt_memcpy(&client.condata, &condata, sizeof(condata));
    client.condata.clientID.cstring = DEVICE_ID;
    client.condata.keepAliveInterval = 30;
    client.condata.cleansession = 1;
    client.condata.username.cstring = MQTT_USERNAME;
    client.condata.password.cstring = MQTT_PASSWORD;

    client.buf_size = client.readbuf_size = MQTT_BUF_SIZE;
    client.buf = rt_calloc(1, MQTT_BUF_SIZE);
    client.readbuf = rt_calloc(1, MQTT_BUF_SIZE);
    if (client.buf == RT_NULL || client.readbuf == RT_NULL)
    {
        LOG_E("no memory for MQTT buffers");
        return -RT_ENOMEM;
    }
    client.online_callback = on_online;
    client.offline_callback = on_offline;
    client.defaultMessageHandler = on_message;

    return paho_mqtt_start(&client) == 0 ? RT_EOK : -RT_ERROR;
}

static void net_entry(void *parameter)
{
    struct imu_batch batch;
    rt_tick_t last_ntp_try;

    wifi_connect();
    clock_sync();
    last_ntp_try = rt_tick_get();
    if (mqtt_start() != RT_EOK)
        LOG_E("MQTT client could not start");

    for (;;)
    {
        if (rt_mq_recv(batches, &batch, sizeof(batch), RT_WAITING_FOREVER) != sizeof(batch))
            continue;

        if (!clock_is_synced() && rt_tick_get() - last_ntp_try > rt_tick_from_millisecond(NTP_RETRY_MS))
        {
            clock_sync();
            last_ntp_try = rt_tick_get();
        }
        if (!client.isconnected)
        {
            not_connected++;
            continue;
        }
        if (payload_format(json, sizeof(json), DEVICE_ID, batch.ts_ms, IMU_RATE_HZ,
                           (const float (*)[6])batch.samples, IMU_RATE_HZ) < 0)
        {
            LOG_E("message does not fit the buffer");
            continue;
        }
        if (paho_mqtt_publish(&client, QOS0, MQTT_TOPIC, json) == 0)
            sent++;
        else
            failed++;
    }
}

rt_err_t net_start(rt_mq_t in)
{
    rt_thread_t thread;
    batches = in;
    thread = rt_thread_create("net", net_entry, RT_NULL, 4096, 15, 10);
    if (thread == RT_NULL)
        return -RT_ENOMEM;
    rt_thread_startup(thread);
    return RT_EOK;
}

rt_bool_t net_is_online(void)
{
    return client.isconnected ? RT_TRUE : RT_FALSE;
}

/* msh command: connection state and message counters. */
static void app_status(void)
{
    rt_kprintf("device   : %s\n", DEVICE_ID);
    rt_kprintf("wifi     : %s", rt_wlan_is_ready() ? "connected" : "not connected");
    if (rt_wlan_is_ready() && netdev_default != RT_NULL)
        rt_kprintf(" (IP %s)", inet_ntoa(netdev_default->ip_addr));
    rt_kprintf("\nmqtt     : %s (%s)\n", client.isconnected ? "connected" : "not connected", uri);
    rt_kprintf("clock    : %s\n", clock_is_synced() ? "synced via NTP" : "not synced (ts=0)");
    rt_kprintf("messages : %u sent, %u skipped while offline, %u failed\n",
               sent, not_connected, failed);
}
MSH_CMD_EXPORT(app_status, show Wi-Fi / MQTT / message status);
