/* Wi-Fi, NTP and MQTT: publishes each IMU batch as one contract message. */
#ifndef NET_H
#define NET_H

#include <rtthread.h>

/* Start the network thread; it reads batches from `in` and publishes them. */
rt_err_t net_start(rt_mq_t in);

/* True while connected to the MQTT broker. */
rt_bool_t net_is_online(void);

#endif /* NET_H */
