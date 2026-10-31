/* On-board 240x240 LCD: the cloud's current prediction and the board's live status. */
#ifndef DISPLAY_H
#define DISPLAY_H

#include <rtthread.h>

/* Start the display thread (a no-op if the LCD is disabled in rtconfig.h). */
rt_err_t display_start(void);

#endif /* DISPLAY_H */
