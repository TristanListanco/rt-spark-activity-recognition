"""Apply this project's RT-Thread settings to the stm32f407-rt-spark BSP.

The non-interactive equivalent of ticking these boxes in `menuconfig`. Run it in
the full BSP directory with RT-Thread Env's Python (Env provides kconfiglib),
then generate rtconfig.h and download the packages:

  cd rt-thread/bsp/stm32/stm32f407-rt-spark
  source ~/.env/env.sh
  python <repo>/tools/firmware_config.py
  menuconfig --generate && pkgs --update

See firmware/README.md for the whole workflow.
"""

import os
import sys
from pathlib import Path

import kconfiglib

# Order matters: a menu has to be enabled before its sub-options exist.
SETTINGS = [
    # On-board RW007 Wi-Fi (SPI2); pulls in lwIP, SAL and the WLAN framework
    ("BSP_USING_RW007_WLAN", "y"),
    # RT-Spark wiring (pin index = port * 16 + pin). The rw007 package's Kconfig is
    # read before the board's and its generic defaults win (e.g. RST = 187, a pin
    # this chip doesn't have), which hangs the driver waiting for the module at
    # boot. Values from the board's Kconfig and RT-Thread's own RT-Spark SDK.
    ("RW007_CS_PIN", "90"),  # PF10
    ("RW007_BOOT0_PIN", "29"),  # PB13 (shared with SPI2 SCK)
    ("RW007_BOOT1_PIN", "90"),  # PF10 (shared with CS)
    ("RW007_INT_BUSY_PIN", "107"),  # PG11
    ("RW007_RST_PIN", "111"),  # PG15
    # On-board ICM-20608 6-axis IMU on software I2C bus 2
    ("BSP_USING_ICM20608", "y"),
    # On-board 240x240 LCD (FSMC), for the status screen in applications/display.c
    ("BSP_USING_ONBOARD_LCD", "y"),
    # MQTT client. Pipe mode (the default for RT-Thread 4.1+) needs the POSIX
    # file/pipe layer; UDP mode fails to compile on RT-Thread 5.4 because it
    # includes lwIP's and SAL's socket headers together.
    ("PKG_USING_PAHOMQTT", "y"),
    ("PAHOMQTT_PIPE_MODE", "y"),
    ("MQTT_DEBUG", "n"),
    # NTP client for real timestamps in the messages
    ("PKG_USING_NETUTILS", "y"),
    ("PKG_NETUTILS_NTP", "y"),
    ("NTP_USING_AUTO_SYNC", "n"),
    ("NETUTILS_NTP_HOSTNAME", "pool.ntp.org"),
    ("NETUTILS_NTP_HOSTNAME2", "time.google.com"),
    ("NETUTILS_NTP_HOSTNAME3", "time.cloudflare.com"),
    # Kernel object names up to 16 chars; the ICM-20608 driver names its mutex
    # "mutex_icm20608" (14), which logs an error at boot with the default 12.
    ("RT_NAME_MAX", "16"),
    # lwIP's tcpip thread peaked at 92% of the default 1 KB stack once the board
    # also receives predictions; 2 KB leaves a safe margin.
    ("RT_LWIP_TCPTHREAD_STACKSIZE", "2048"),
]


def main() -> None:
    bsp = Path.cwd()
    if not (bsp / "Kconfig").exists() or not (bsp / ".config").exists():
        sys.exit("Run this in the BSP directory (it needs Kconfig and .config).")
    rtt_root = (bsp / "../../..").resolve()
    os.environ.setdefault("RTT_DIR", str(rtt_root))
    os.environ.setdefault("RTT_ROOT", str(rtt_root))
    os.environ.setdefault("PKGS_DIR", str(Path.home() / ".env" / "packages"))

    kconf = kconfiglib.Kconfig("Kconfig", warn=False)
    kconf.load_config(".config")
    failed = []
    for name, value in SETTINGS:
        sym = kconf.syms.get(name)
        if sym is None:
            failed.append(f"{name}: no such option")
            continue
        sym.set_value(value)
        if sym.str_value != value:
            failed.append(f"{name}: wanted {value!r}, got {sym.str_value!r} (dependency missing?)")
        else:
            print(f"  {name} = {value}")
    if failed:
        sys.exit("Could not apply:\n  " + "\n  ".join(failed))
    kconf.write_config(".config")
    print("updated .config; now run: menuconfig --generate && pkgs --update")


if __name__ == "__main__":
    main()
