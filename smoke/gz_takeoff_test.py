"""End-to-end check: ArduCopter SITL flying the Gazebo iris through ardupilot_gazebo.

Connects to SITL, waits for EKF/GPS readiness, takes off in GUIDED to 5 m,
and reports the altitude the autopilot sees over MAVLink. In --model JSON mode
Gazebo is the only physics source, so a climb proves the JSON loop is closed.
"""
import sys
import time

from pymavlink import mavutil

URL = sys.argv[1] if len(sys.argv) > 1 else "tcp:127.0.0.1:5760"
TARGET_ALT = 5.0

m = mavutil.mavlink_connection(URL)
hb = m.wait_heartbeat(timeout=30)
if hb is None:
    sys.exit("FAIL: no heartbeat")
print(f"heartbeat: type={hb.type} autopilot={hb.autopilot}")

m.mav.request_data_stream_send(m.target_system, m.target_component,
                               mavutil.mavlink.MAV_DATA_STREAM_ALL, 10, 1)

# Wait until the autopilot reports it can arm (EKF + GPS good).
deadline = time.time() + 120
armable = False
while time.time() < deadline:
    msg = m.recv_match(type=["SYS_STATUS", "STATUSTEXT", "GPS_RAW_INT"], blocking=True, timeout=2)
    if msg is None:
        continue
    if msg.get_type() == "STATUSTEXT":
        print("  sitl:", msg.text)
    if msg.get_type() == "SYS_STATUS":
        prearm = mavutil.mavlink.MAV_SYS_STATUS_PREARM_CHECK
        if msg.onboard_control_sensors_health & prearm:
            armable = True
            break
if not armable:
    sys.exit("FAIL: prearm checks never passed within 120 s")
print("prearm checks passed")

m.set_mode("GUIDED")
m.arducopter_arm()
m.motors_armed_wait()
print("armed")
m.mav.command_long_send(m.target_system, m.target_component,
                        mavutil.mavlink.MAV_CMD_NAV_TAKEOFF, 0, 0, 0, 0, 0, 0, 0, TARGET_ALT)

max_alt = 0.0
deadline = time.time() + 40
while time.time() < deadline:
    msg = m.recv_match(type="GLOBAL_POSITION_INT", blocking=True, timeout=2)
    if msg is None:
        continue
    alt = msg.relative_alt / 1000.0
    max_alt = max(max_alt, alt)
    if alt >= TARGET_ALT * 0.9:
        break
print(f"max relative altitude reached: {max_alt:.2f} m")

m.set_mode("LAND")
if max_alt >= TARGET_ALT * 0.9:
    print("PASS")
else:
    sys.exit("FAIL: did not reach target altitude")
