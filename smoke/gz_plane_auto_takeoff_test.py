"""Zephyr auto-takeoff check (TAKEOFF mode), the path that reports "Bad launch AUTO".

1. Reads the resting attitude: the Zephyr spawns standing on its tail, which
   fails ArduPlane's takeoff attitude check (pitch >= 45 or |roll| > 30 deg).
2. Sets FLIGHT_OPTIONS bit 2 (DISABLE_TOFF_ATTITUDE_CHK), keeping other bits,
   unless --keep-attitude-check is given (for spawn poses that should pass it).
3. Arms in TAKEOFF mode and requires a climb to 90% of TKOFF_ALT.
"""
import math
import sys
import time

from pymavlink import mavutil

args = [a for a in sys.argv[1:] if not a.startswith("--")]
KEEP_CHECK = "--keep-attitude-check" in sys.argv
URL = args[0] if args else "tcp:127.0.0.1:5760"
DISABLE_TOFF_ATTITUDE_CHK = 1 << 2

m = mavutil.mavlink_connection(URL)
if m.wait_heartbeat(timeout=30) is None:
    sys.exit("FAIL: no heartbeat")
m.mav.request_data_stream_send(m.target_system, m.target_component,
                               mavutil.mavlink.MAV_DATA_STREAM_ALL, 10, 1)


def get_param(name):
    m.param_fetch_one(name)
    p = m.recv_match(type="PARAM_VALUE", condition=f'PARAM_VALUE.param_id=="{name}"',
                     blocking=True, timeout=10)
    if p is None:
        sys.exit(f"FAIL: could not read {name}")
    return p.param_value


deadline = time.time() + 120
while time.time() < deadline:
    msg = m.recv_match(type="SYS_STATUS", blocking=True, timeout=2)
    if msg and msg.onboard_control_sensors_health & mavutil.mavlink.MAV_SYS_STATUS_PREARM_CHECK:
        break
else:
    sys.exit("FAIL: prearm checks never passed within 120 s")

# Sample for a few seconds: the airframe has no gear, so it may still be settling.
# Read continuously (sleeping would leave stale messages in the buffer).
end, next_print = time.time() + 4.5, 0.0
while time.time() < end:
    att = m.recv_match(type="ATTITUDE", blocking=True, timeout=2)
    if att is None:
        continue
    pitch, roll = math.degrees(att.pitch), math.degrees(att.roll)
    if time.time() >= next_print:
        print(f"resting attitude: pitch {pitch:.1f} deg, roll {roll:.1f} deg")
        next_print = time.time() + 1.5
fails = pitch >= 45 or pitch <= -30 or abs(roll) > 30
print(f"takeoff attitude check would {'FAIL (Bad launch AUTO)' if fails else 'pass'}")

opts = int(get_param("FLIGHT_OPTIONS"))
tkoff_alt = get_param("TKOFF_ALT")
if KEEP_CHECK:
    print(f"FLIGHT_OPTIONS {opts} (attitude check left enabled), TKOFF_ALT {tkoff_alt:.0f} m")
else:
    m.param_set_send("FLIGHT_OPTIONS", opts | DISABLE_TOFF_ATTITUDE_CHK)
    new_opts = int(get_param("FLIGHT_OPTIONS"))
    print(f"FLIGHT_OPTIONS {opts} -> {new_opts}, TKOFF_ALT {tkoff_alt:.0f} m")

m.set_mode("TAKEOFF")
m.arducopter_arm()          # generic MAV_CMD_COMPONENT_ARM_DISARM despite the name
m.motors_armed_wait()
print("armed in TAKEOFF")

max_alt, bad_launch = 0.0, False
deadline = time.time() + 120
while time.time() < deadline:
    msg = m.recv_match(type=["GLOBAL_POSITION_INT", "STATUSTEXT"], blocking=True, timeout=2)
    if msg is None:
        continue
    if msg.get_type() == "STATUSTEXT":
        print("  sitl:", msg.text)
        bad_launch |= "Bad launch" in msg.text
    else:
        max_alt = max(max_alt, msg.relative_alt / 1000.0)
        if max_alt >= 0.9 * tkoff_alt:
            break
print(f"max relative altitude: {max_alt:.1f} m (target {tkoff_alt:.0f} m)")

m.set_mode("RTL")
if bad_launch:
    sys.exit("FAIL: still got Bad launch")
if max_alt < 0.9 * tkoff_alt:
    sys.exit("FAIL: did not reach 90% of TKOFF_ALT")
print("PASS")
