#!/usr/bin/env bash
# End-to-end: headless Gazebo + ArduPilot SITL over the JSON interface + flight
# test. Usage: run_gz_e2e.sh [copter|plane|plane-takeoff|plane-takeoff-15]   (default: copter)
#   copter: iris_runway.sdf  + arducopter, copter.parm + gazebo-iris.parm
#   plane:  zephyr_runway.sdf + arduplane, gazebo-zephyr.parm (as sim_vehicle.py)
#   plane-takeoff: same, but auto-takeoff in TAKEOFF mode (needs FLIGHT_OPTIONS bit 2)
#   plane-takeoff-15: TAKEOFF mode from zephyr_runway_15deg.sdf, attitude check left on
# Each process runs in its own session (setsid) so teardown kills the whole tree; nothing is left holding UDP 9002 / TCP 5760.
set -u
ROOT="$HOME/cert-env"
LOGS="$ROOT/logs"
AP="$ROOT/src/ardupilot"
PARAMS="$AP/Tools/autotest/default_params"
VEHICLE="${1:-copter}"
case "$VEHICLE" in
  copter) WORLD=iris_runway.sdf;   BIN=arducopter; DEFAULTS="$PARAMS/copter.parm,$PARAMS/gazebo-iris.parm"
          TEST=gz_takeoff_test.py ;;
  plane)  WORLD=zephyr_runway.sdf; BIN=arduplane;  DEFAULTS="$PARAMS/gazebo-zephyr.parm"
          TEST=gz_plane_test.py ;;
  plane-takeoff) WORLD=zephyr_runway.sdf; BIN=arduplane; DEFAULTS="$PARAMS/gazebo-zephyr.parm"
          TEST=gz_plane_auto_takeoff_test.py ;;
  plane-takeoff-15) WORLD=zephyr_runway_15deg.sdf; BIN=arduplane; DEFAULTS="$PARAMS/gazebo-zephyr.parm"
          TEST=gz_plane_auto_takeoff_test.py; TEST_ARGS=--keep-attitude-check ;;
  *) echo "usage: $0 [copter|plane|plane-takeoff|plane-takeoff-15]"; exit 2 ;;
esac
mkdir -p "$ROOT/smoke/gz-run"
cd "$ROOT/smoke/gz-run"

cleanup() {
  for pg in ${SITL_PG:-} ${GZ_PG:-}; do kill -TERM -- "-$pg" 2>/dev/null; done
  sleep 3
  for pg in ${SITL_PG:-} ${GZ_PG:-}; do kill -KILL -- "-$pg" 2>/dev/null; done
}
trap cleanup EXIT

if ss -ltn | grep -q ':5760 ' || ss -uan | grep -q ':9002 '; then
  echo "ABORT: 5760/tcp or 9002/udp already in use"; exit 3
fi

setsid bash -c "source '$ROOT/env.sh'; exec gz sim -s -r -v4 --headless-rendering $WORLD" \
  > "$LOGS/gz-server-$VEHICLE.log" 2>&1 &
GZ_PG=$!
sleep 15
kill -0 "$GZ_PG" 2>/dev/null || { echo "FAIL: gz server died"; exit 4; }

setsid "$AP/build/sitl/bin/$BIN" --model JSON --speedup 1 --slave 0 \
  --defaults "$DEFAULTS" \
  --sim-address=127.0.0.1 -I0 > "$LOGS/sitl-gz-$VEHICLE.log" 2>&1 &
SITL_PG=$!
sleep 5

"$ROOT/venv/bin/python" -I "$ROOT/smoke/$TEST" tcp:127.0.0.1:5760 ${TEST_ARGS:-} \
  2>&1 | tee "$LOGS/gz-test-$VEHICLE.log"
exit "${PIPESTATUS[0]}"
