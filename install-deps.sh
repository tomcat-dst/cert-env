#!/usr/bin/env bash
# System packages missing on this host (Ubuntu 24.04 noble) for:
#   ArduPilot Plane-4.7.3 SITL + QGroundControl v5.1.5 + MAVSDK v4.2.1
# Every name below was checked against `apt-cache policy` on this machine;
# packages already installed are left out. Run with: sudo ./install-deps.sh
set -euo pipefail

# --- QGroundControl (its own tools/setup/install_dependencies --print-packages)
QGC_PKGS=(
  ccache cppcheck gnupg2 gstreamer1.0-plugins-rtp gstreamer1.0-rtsp
  libatspi2.0-dev libfontconfig1-dev libfreetype-dev libfuse2t64 libgtk-3-dev
  libopenblas0 libpipewire-0.3-dev libpulse-dev mold nasm patchelf pipx
  python3-gst-1.0 valgrind xvfb zsync
)

# --- ArduPilot (Tools/environment_install/install-prereqs-ubuntu.sh, noble) --
# SITL itself built with no extra apt packages; these are for MAVProxy GUI
# modules (console/map), sim_vehicle.py xterms and the SFML joystick/display bits.
AP_PKGS=(
  astyle python-is-python3 xterm
  libcsfml-dev libsfml-dev libwxgtk3.2-dev python3-wxgtk4.0
  libportmidi-dev
)

apt-get update
apt-get install -y \
  "${QGC_PKGS[@]}" "${AP_PKGS[@]}"
