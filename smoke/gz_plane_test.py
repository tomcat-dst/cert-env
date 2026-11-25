"""End-to-end check: ArduPlane SITL flying the Gazebo Zephyr through ardupilot_gazebo.

Follows the ardupilot_gazebo README procedure over MAVLink:
FBWA -> arm -> throttle 1800 (RC override) -> climb -> CIRCLE (override released).
PASS needs: a real climb, at least one full 360 deg of heading change in CIRCLE,
no altitude collapse while circling, and average groundspeed at or above the
vehicle's own AIRSPEED_MIN (no wind in this world, so groundspeed ~ airspeed).
"""
import sys
import time

from pymavlink import mavutil

URL = sys.argv[1] if len(sys.argv) > 1 else "tcp:127.0.0.1:5760"
CLIMB_TO = 40.0        # m above home before switching to CIRCLE
CIRCLE_MIN_ALT = 20.0  # m; below this while circling counts as a failure

m = mavutil.mavlink_connection(URL)
hb = m.wait_heartbeat(timeout=30)
if hb is None:
    sys.exit("FAIL: no heartbeat")
print(f"heartbeat: type={hb.type} autopilot={hb.autopilot}")
if hb.type != mavutil.mavlink.MAV_TYPE_FIXED_WING:
    sys.exit(f"FAIL: expected fixed wing (type 1), got type {hb.type}")

m.mav.request_data_stream_send(m.target_system, m.target_component,
                               mavutil.mavlink.MAV_DATA_STREAM_ALL, 10, 1)


def rc_throttle(pwm):
    # Channels 1..8; 0 = release that channel back to the RC input.
    m.mav.rc_channels_override_send(m.target_system, m.target_component,
                                    0, 0, pwm, 0, 0, 0, 0, 0)


deadline = time.time() + 120
while time.time() < deadline:
    msg = m.recv_match(type=["SYS_STATUS", "STATUSTEXT"], blocking=True, timeout=2)
    if msg is None:
        continue
    if msg.get_type() == "STATUSTEXT":
        print("  sitl:", msg.text)
    elif msg.onboard_control_sensors_health & mavutil.mavlink.MAV_SYS_STATUS_PREARM_CHECK:
        break
else:
    sys.exit("FAIL: prearm checks never passed within 120 s")
print("prearm checks passed")

m.param_fetch_one("AIRSPEED_MIN")
p = m.recv_match(type="PARAM_VALUE", condition='PARAM_VALUE.param_id=="AIRSPEED_MIN"',
                 blocking=True, timeout=10)
if p is None:
    sys.exit("FAIL: could not read AIRSPEED_MIN")
MIN_SPEED = p.param_value
print(f"vehicle AIRSPEED_MIN = {MIN_SPEED:.1f} m/s")

m.set_mode("FBWA")
m.arducopter_arm()          # generic MAV_CMD_COMPONENT_ARM_DISARM despite the name
m.motors_armed_wait()
print("armed in FBWA, throttle 1800")

# --- climb under manual throttle --------------------------------------------
alt = max_alt = 0.0
deadline = time.time() + 90
while time.time() < deadline:
    rc_throttle(1800)
    msg = m.recv_match(type=["VFR_HUD", "GLOBAL_POSITION_INT", "STATUSTEXT"],
                       blocking=True, timeout=1)
    if msg is None:
        continue
    if msg.get_type() == "STATUSTEXT":
        print("  sitl:", msg.text)
    elif msg.get_type() == "GLOBAL_POSITION_INT":
        alt = msg.relative_alt / 1000.0
        max_alt = max(max_alt, alt)
        if alt >= CLIMB_TO:
            break
print(f"climb: reached {max_alt:.1f} m")
if max_alt < CLIMB_TO:
    sys.exit(f"FAIL: did not climb to {CLIMB_TO} m within 90 s")

# --- CIRCLE under autopilot control -----------------------------------------
m.set_mode("CIRCLE")
rc_throttle(0)
print("mode CIRCLE, throttle override released")

turned = 0.0
last_hdg = None
min_rel, speeds = 1e9, []
deadline = time.time() + 120
while time.time() < deadline and turned < 400:
    msg = m.recv_match(type="VFR_HUD", blocking=True, timeout=2)
    if msg is None:
        continue
    speeds.append(msg.groundspeed)
    if last_hdg is not None:
        d = (msg.heading - last_hdg + 540) % 360 - 180
        turned += abs(d)
    last_hdg = msg.heading
    pos = m.messages.get("GLOBAL_POSITION_INT")
    if pos is not None:
        rel = pos.relative_alt / 1000.0
        min_rel = min(min_rel, rel)
        if rel < CIRCLE_MIN_ALT:
            sys.exit(f"FAIL: altitude dropped to {rel:.1f} m while circling")

pos = m.messages.get("GLOBAL_POSITION_INT")
rel_now = pos.relative_alt / 1000.0 if pos else float("nan")
avg_speed = sum(speeds) / len(speeds) if speeds else 0.0
print(f"circle: heading change {turned:.0f} deg, avg groundspeed {avg_speed:.1f} m/s, "
      f"min groundspeed {min(speeds) if speeds else 0:.1f} m/s, "
      f"min rel alt {min_rel:.1f} m, rel alt now {rel_now:.1f} m")

m.set_mode("RTL")
if turned < 360:
    sys.exit("FAIL: did not complete a full circle within 120 s")
if avg_speed < MIN_SPEED:
    sys.exit(f"FAIL: average groundspeed {avg_speed:.1f} m/s below {MIN_SPEED}")
print("PASS")
