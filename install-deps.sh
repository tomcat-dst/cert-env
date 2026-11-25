#!/usr/bin/env bash
# System packages missing on this host (Ubuntu 24.04 noble) for:
#   ArduPilot Copter-4.7.3 SITL + Gazebo Harmonic (source) + ardupilot_gazebo
#   + QGroundControl v5.1.5 + MAVSDK v4.2.1
# Every name below was checked against `apt-cache policy` on this machine;
# packages already installed are left out. Run with: sudo ./install-deps.sh
set -euo pipefail

# --- Gazebo Harmonic (from failed colcon configure + package.xml deps) ------
GZ_PKGS=(
  libtinyxml2-dev libtinyxml-dev liburdfdom-dev            # sdformat14
  libprotobuf-dev libprotoc-dev protobuf-compiler python3-protobuf  # gz-msgs10
  libeigen3-dev                                             # gz-math7 eigen3
  libfreeimage-dev libgts-dev libassimp-dev libgdal-dev libavdevice-dev  # gz-common5
  libogre-next-dev libogre-1.9-dev libglew-dev freeglut3-dev libvulkan-dev libxmu-dev  # gz-rendering8
  libdart-all-dev libbullet-dev libccd-dev libfcl-dev libode-dev libbenchmark-dev  # gz-physics7
  libzmq3-dev libsqlite3-dev libcurl4-openssl-dev libjsoncpp-dev libyaml-dev libzip-dev  # transport / fuel-tools
  libwebsockets-dev libgflags-dev                           # gz-launch7 / gz-sim8
  qtbase5-dev qtdeclarative5-dev qtquickcontrols2-5-dev libqt5charts5-dev  # gz-gui8 (Qt5)
  qml-module-qtcharts qml-module-qt-labs-platform qml-module-qtlocation
  qml-module-qtpositioning qml-module-qtquick-extras
  pybind11-dev python3-pybind11 python3-psutil python3-pytest ruby-dev  # bindings / gz CLI
)

# --- ardupilot_gazebo plugin (README, Harmonic) ------------------------------
APGZ_PKGS=( rapidjson-dev gstreamer1.0-plugins-ugly )

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
  "${GZ_PKGS[@]}" "${APGZ_PKGS[@]}" "${QGC_PKGS[@]}" "${AP_PKGS[@]}"
