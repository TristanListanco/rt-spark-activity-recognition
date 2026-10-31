#include "label.h"

#include <board.h>
#include <drv_gpio.h>
#include <rtdevice.h>

#define DBG_TAG "label"
#define DBG_LVL DBG_INFO
#include <rtdbg.h>

/* RT-Spark buttons. As in RT-Thread's RT-Spark SDK examples (02_basic_key, 02_basic_irq_beep),
 * all four, WK_UP included, use the internal pull-up and read LOW while pressed. */
static const struct
{
    rt_base_t pin;
    const char *label; /* RT_NULL = stop recording */
} buttons[] = {
    {GET_PIN(C, 0), "walk"}, /* LEFT  (KEY0) */
    {GET_PIN(C, 4), "run"},  /* RIGHT (KEY2) */
    {GET_PIN(C, 5), "idle"}, /* UP    (WK_UP) */
    {GET_PIN(C, 1), RT_NULL}, /* DOWN (KEY1) */
};
#define BUTTON_COUNT (sizeof(buttons) / sizeof(buttons[0]))

static rt_uint8_t pressed_polls[BUTTON_COUNT];
static const char *volatile current;

void label_init(void)
{
    rt_size_t i;
    for (i = 0; i < BUTTON_COUNT; i++)
        rt_pin_mode(buttons[i].pin, PIN_MODE_INPUT_PULLUP);
}

void label_poll(void)
{
    rt_size_t i;
    for (i = 0; i < BUTTON_COUNT; i++)
    {
        if (rt_pin_read(buttons[i].pin) != PIN_LOW) /* released */
        {
            pressed_polls[i] = 0;
            continue;
        }
        /* act once per press, after two consecutive reads (~100 ms debounce) */
        if (++pressed_polls[i] == 2 && current != buttons[i].label)
        {
            current = buttons[i].label;
            LOG_I("recording label: %s", current ? current : "(stopped)");
        }
        if (pressed_polls[i] > 2)
            pressed_polls[i] = 2;
    }
}

const char *label_current(void)
{
    return current;
}

/* msh command: show or set the label without the buttons, e.g. `rec walk`, `rec stop`. */
static void rec(int argc, char **argv)
{
    if (argc == 2)
    {
        if (rt_strcmp(argv[1], "walk") == 0 || rt_strcmp(argv[1], "run") == 0)
            current = rt_strcmp(argv[1], "walk") == 0 ? "walk" : "run";
        else if (rt_strcmp(argv[1], "idle") == 0)
            current = "idle";
        else
            current = RT_NULL;
    }
    rt_kprintf("recording label: %s\n", current ? current : "(not recording)");
}
MSH_CMD_EXPORT(rec, show or set the recording label: rec [walk|run|idle|stop]);
