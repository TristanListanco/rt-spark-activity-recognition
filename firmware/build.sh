#!/usr/bin/env bash
# Build (and flash) the RT-Spark firmware.
#
# This folder holds only what is specific to this project: the application
# code (applications/) and the RT-Thread configuration (.config, rtconfig.h,
# made by tools/firmware_config.py). Everything else comes from upstream at a
# pinned commit: the script fetches RT-Thread's stm32f407-rt-spark board
# package, copies this project on top of it, downloads the packages with
# RT-Thread Env and builds with SCons.
#
# Usage:  firmware/build.sh [build|flash|clean]      (default: build)
#
# Environment (all optional):
#   RTT_DIR        existing RT-Thread checkout to use (default: firmware/.rtt/rt-thread)
#   ENV_ROOT       RT-Thread Env location (default: ~/.env; installed if missing)
#   RTT_EXEC_PATH  folder containing arm-none-eabi-gcc (default: PlatformIO's, else PATH)
set -euo pipefail

RTT_REPO=https://github.com/RT-Thread/rt-thread.git
RTT_COMMIT=cbc19778d0ae5ef2533a28c0f62c6a399858010a
RTT_PATHS=(src include libcpu components tools bsp/stm32/libraries bsp/stm32/tools
           bsp/stm32/stm32f407-rt-spark)

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
rtt_dir="${RTT_DIR:-$here/.rtt/rt-thread}"
bsp="$rtt_dir/bsp/stm32/stm32f407-rt-spark"
env_root="${ENV_ROOT:-$HOME/.env}"
out="$here/out"

log() { printf '\n==> %s\n' "$*"; }

toolchain_dir() {
  if [ -n "${RTT_EXEC_PATH:-}" ]; then
    echo "$RTT_EXEC_PATH"
  elif [ -x "$HOME/.platformio/packages/toolchain-gccarmnoneeabi/bin/arm-none-eabi-gcc" ]; then
    echo "$HOME/.platformio/packages/toolchain-gccarmnoneeabi/bin"
  elif command -v arm-none-eabi-gcc >/dev/null; then
    dirname "$(command -v arm-none-eabi-gcc)"
  else
    echo "arm-none-eabi-gcc not found; see firmware/README.md" >&2
    exit 1
  fi
}

fetch_rtthread() {
  if [ ! -d "$rtt_dir/.git" ]; then
    log "Fetching RT-Thread $RTT_COMMIT (only the parts this board needs)"
    mkdir -p "$rtt_dir"
    git -C "$rtt_dir" init -q
    git -C "$rtt_dir" remote add origin "$RTT_REPO"
    git -C "$rtt_dir" sparse-checkout set "${RTT_PATHS[@]}"
    git -C "$rtt_dir" fetch -q --depth 1 --filter=blob:none origin "$RTT_COMMIT"
    git -C "$rtt_dir" checkout -q FETCH_HEAD
  else
    git -C "$rtt_dir" sparse-checkout add "${RTT_PATHS[@]}"
  fi
  local head
  head="$(git -C "$rtt_dir" rev-parse HEAD)"
  if [ "$head" != "$RTT_COMMIT" ]; then
    echo "RT-Thread in $rtt_dir is at $head, but this project pins $RTT_COMMIT." >&2
    exit 1
  fi
}

ensure_env() {
  if [ ! -f "$env_root/env.sh" ]; then
    log "Installing RT-Thread Env into $env_root"
    mkdir -p "$env_root/local_pkgs" "$env_root/packages" "$env_root/tools"
    git clone -q --depth 1 https://github.com/RT-Thread/packages.git "$env_root/packages/packages"
    # Literal $PKGS_DIR: Kconfig expands it, not the shell.
    # shellcheck disable=SC2016
    echo 'source "$PKGS_DIR/packages/Kconfig"' > "$env_root/packages/Kconfig"
    git clone -q --depth 1 https://github.com/RT-Thread/sdk.git "$env_root/packages/sdk"
    git clone -q --depth 1 https://github.com/RT-Thread/env.git "$env_root/tools/scripts"
    cp "$env_root/tools/scripts/env.sh" "$env_root/env.sh"
  fi
}

overlay() {
  log "Copying this project's configuration and applications/ into the board package"
  cp "$here/.config" "$here/rtconfig.h" "$bsp/"
  rm -rf "$bsp/applications"
  cp -R "$here/applications" "$bsp/applications"
  if [ ! -f "$bsp/applications/secrets.h" ]; then
    cp "$here/applications/secrets.example.h" "$bsp/applications/secrets.h"
    echo "WARNING: applications/secrets.h not found; building with placeholder Wi-Fi/MQTT settings"
  fi
}

in_env() {
  # Run a command inside RT-Thread Env, in the board package, with our toolchain.
  local exec_path
  exec_path="$(toolchain_dir)"
  (
    cd "$bsp"
    # shellcheck source=/dev/null
    ENV_ROOT="$env_root" source "$env_root/env.sh" >/dev/null
    export RTT_CC=gcc RTT_EXEC_PATH="$exec_path"
    "$@"
  )
}

build() {
  fetch_rtthread
  ensure_env
  overlay
  log "Downloading packages (pkgs --update)"
  in_env pkgs --update
  log "Building with $("$(toolchain_dir)/arm-none-eabi-gcc" --version | head -1)"
  local jobs
  jobs="$(getconf _NPROCESSORS_ONLN 2>/dev/null || echo 4)"
  in_env scons -j"$jobs"
  mkdir -p "$out"
  cp "$bsp/rtthread.bin" "$bsp/rt-thread.elf" "$bsp/rt-thread.map" "$out/"
  [ -f "$bsp/rtthread.hex" ] && cp "$bsp/rtthread.hex" "$out/"
  log "Firmware ready in firmware/out/"
  "$(toolchain_dir)/arm-none-eabi-size" "$out/rt-thread.elf"
}

flash() {
  local oc="$HOME/.platformio/packages/tool-openocd"
  local openocd="openocd" scripts=()
  if [ -x "$oc/bin/openocd" ]; then
    openocd="$oc/bin/openocd"
    scripts=(-s "$oc/openocd/scripts")
  fi
  [ -f "$out/rtthread.bin" ] || build
  log "Flashing firmware/out/rtthread.bin through the on-board ST-Link"
  "$openocd" "${scripts[@]}" -f interface/stlink.cfg -f target/stm32f4x.cfg \
    -c "program $out/rtthread.bin 0x08000000 verify reset exit"
}

case "${1:-build}" in
  build) build ;;
  flash) build && flash ;;
  clean) [ -d "$bsp" ] && in_env scons -c; rm -rf "$out" ;;
  *) echo "usage: $0 [build|flash|clean]" >&2; exit 2 ;;
esac
