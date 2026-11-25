# source ~/cert-env/env.sh — puts every built tool on PATH for the current shell.
CERT_ENV="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

source "$CERT_ENV/venv/bin/activate"                    # MAVProxy, pymavlink, waf deps
export PATH="$CERT_ENV/src/ardupilot/Tools/autotest:$PATH"  # sim_vehicle.py

export LD_LIBRARY_PATH="$CERT_ENV/install/mavsdk/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export CMAKE_PREFIX_PATH="$CERT_ENV/install/mavsdk${CMAKE_PREFIX_PATH:+:$CMAKE_PREFIX_PATH}"

export QGC_BIN="$CERT_ENV/src/qgroundcontrol/build/Release/QGroundControl"

