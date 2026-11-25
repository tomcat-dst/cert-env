# source ~/cert-env/env.sh — puts every built tool on PATH for the current shell.
CERT_ENV="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

source "$CERT_ENV/venv/bin/activate"                    # MAVProxy, pymavlink, waf deps
export PATH="$CERT_ENV/src/ardupilot/Tools/autotest:$PATH"  # sim_vehicle.py

export LD_LIBRARY_PATH="$CERT_ENV/install/mavsdk/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export CMAKE_PREFIX_PATH="$CERT_ENV/install/mavsdk${CMAKE_PREFIX_PATH:+:$CMAKE_PREFIX_PATH}"

export QGC_BIN="$CERT_ENV/src/qgroundcontrol/build/Release/QGroundControl"

if [ -f "$CERT_ENV/src/ardupilot_gazebo/build/libArduPilotPlugin.so" ]; then
  # colcon's setup.bash reads unset variables; don't let a caller's `set -u` abort it.
  case $- in *u*) _cert_env_nounset=1; set +u ;; esac
  source "$CERT_ENV/install/gz/setup.bash"
  [ -n "${_cert_env_nounset:-}" ] && set -u; unset _cert_env_nounset
  export GZ_SIM_SYSTEM_PLUGIN_PATH="$CERT_ENV/src/ardupilot_gazebo/build${GZ_SIM_SYSTEM_PLUGIN_PATH:+:$GZ_SIM_SYSTEM_PLUGIN_PATH}"
  export GZ_SIM_RESOURCE_PATH="$CERT_ENV/src/ardupilot_gazebo/models:$CERT_ENV/src/ardupilot_gazebo/worlds${GZ_SIM_RESOURCE_PATH:+:$GZ_SIM_RESOURCE_PATH}"
  # Our own models/worlds (e.g. the X-UAV Talon) — first, so they win over same-named upstream ones.
  export GZ_SIM_RESOURCE_PATH="$CERT_ENV/sim/models:$CERT_ENV/sim/worlds:$GZ_SIM_RESOURCE_PATH"
fi
