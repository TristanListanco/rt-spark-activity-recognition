/*
 * Recording labels from the board's buttons, for collecting training data (M7):
 * LEFT = walk, RIGHT = run, UP = idle, DOWN = stop. While a label is set, every
 * MQTT message carries it, and tools/record.py saves those samples.
 */
#ifndef LABEL_H
#define LABEL_H

#include <rtthread.h>

void label_init(void);

/* Read the buttons; call every ~50 ms. */
void label_poll(void);

/* "walk", "run", "idle", or RT_NULL when not recording. */
const char *label_current(void);

#endif /* LABEL_H */
