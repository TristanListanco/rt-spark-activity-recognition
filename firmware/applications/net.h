/* Wi-Fi, NTP and MQTT: publishes each IMU batch as one contract message and
 * receives the classifier's predictions back for the display. */
#ifndef NET_H
#define NET_H

#include <rtthread.h>

struct net_status
{
    rt_bool_t wifi_up;
    char ip[16];                /* "" until DHCP gives an address */
    rt_bool_t mqtt_online;
    const char *broker;         /* "host:port" */
    rt_uint32_t sent, skipped, failed;

    rt_bool_t has_prediction;   /* RT_FALSE until the first prediction arrives */
    char activity[8];           /* "walk" or "run" */
    int confidence_pct;
    rt_uint32_t prediction_age_ms;
};

/* Start the network thread; it reads batches from `in` and publishes them. */
rt_err_t net_start(rt_mq_t in);

/* True while connected to the MQTT broker. */
rt_bool_t net_is_online(void);

/* A consistent snapshot of the connection state, counters and latest prediction. */
void net_get_status(struct net_status *out);

#endif /* NET_H */
