#!/usr/bin/env python3
"""
Flies a jammer-search mission (sim/missions/tsuniv_search*.plan) in SITL with QGroundControl in the
loop, and tests RC loss beyond RC range.

  compare/mission.py [--model believer-5kg-avl-at] [--speedup 5]
  compare/mission.py --plan sim/missions/tsuniv_search_long.plan \
      --params sim/params/believer_mission_long.parm --rc-fail-s 0     # ~1 h 30 min, RC off beyond 5 km
  compare/mission.py --plan sim/missions/tsuniv_rf_search.plan --rf --rc-fail-km 0
      # RF direction finding: compare/rf_companion.py on SERIAL2 sends bearings and the fix to QGC
  compare/mission.py --plan sim/missions/tsuniv_rf_sweep.plan --params sim/params/believer_mission_long.parm \
      --rf --rc-fail-km 0 --mode RFSEARCH      # the autopilot sweeps by itself (plain waypoints)

1. Starts SITL with the model's parameter files plus sim/params/believer_mission.parm (geofence,
   RC failsafe). SERIAL1 sends MAVLink to UDP 14550, where QGC auto-connects; this script uses
   SERIAL0 (TCP 5760).
2. Waits for the operator in QGC: Plan view -> Open tsuniv_search.plan -> Upload (mission and fence);
   Fly view -> Arm -> Start Mission.
3. Once armed in AUTO or RFSEARCH, releases the catapult (servo 7, the launcher in the SITL model).
4. The first time the aircraft is past --rc-fail-km from home and on a search leg, sets SIM_RC_FAIL 1
   (no RC pulses) for --rc-fail-s sim seconds, then restores RC. Mode and mission item are logged
   throughout.
5. Once the aircraft has landed and disarmed (or, as a fallback, circled home in RTL for 60 sim
   seconds), keeps SITL running for --hold wall seconds (QGC stays connected for screenshots). After a
   landing it switches to MANUAL and makes mission item 1 current; otherwise pre-arm keeps reporting
   "In landing sequence" (see the comment there for why a mode change alone is not enough).

Outputs (compare/results/mission-<time>/<model>/): logs/ (dataflash), events.txt (sim time, event),
track.csv, summary.md.
"""
import argparse
import csv
import json
import math
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import compare_planes as cp    # noqa: E402  (also enforces the venv)
import endurance               # noqa: E402
from pymavlink import mavutil  # noqa: E402

# RFSEARCH: our ArduPlane mode 27 (AUTO with RF sweeps, ArduPlane/rf_search.cpp), unknown to pymavlink
mavutil.mode_mapping_apm.setdefault(27, "RFSEARCH")
MISSION_MODES = ("AUTO", "RFSEARCH")

PLAN = cp.ROOT / "sim/missions/tsuniv_search.plan"
MISSION_PARM = cp.ROOT / "sim/params/believer_mission.parm"
STOP_FILE = Path(__file__).resolve().parent / "mission.stop"


def dist_m(lat1, lon1, lat2, lon2):
    n = math.radians(lat2 - lat1) * 6371000.0
    e = math.radians(lon2 - lon1) * 6371000.0 * math.cos(math.radians(lat1))
    return math.hypot(n, e)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", default="believer-5kg-avl-at", choices=sorted(cp.MODELS))
    ap.add_argument("--speedup", type=float, default=5.0)
    ap.add_argument("--rc-fail-km", type=float, default=5.0, help="0 = no RC-loss test")
    ap.add_argument("--rc-fail-s", type=float, default=60.0,
                    help="RC loss duration, sim s; 0 = until back inside --rc-fail-km (out of range)")
    ap.add_argument("--plan", type=Path, default=PLAN)
    ap.add_argument("--params", type=Path, nargs="*", default=[],
                    help="extra parameter files, after believer_mission.parm")
    ap.add_argument("--home-radius", type=float, default=400.0)
    ap.add_argument("--wait-operator", type=float, default=1800.0,
                    help="wall seconds to wait for arm + AUTO from QGC")
    ap.add_argument("--hold", type=float, default=None,
                    help=f"wall seconds to keep SITL running after RTL (default 1800 with QGC, 0 with "
                         f"--upload); touch {STOP_FILE.name} in compare/ to stop early")
    ap.add_argument("--rc-fail-in-sweep", action="store_true",
                    help="RFSEARCH failsafe test: cut RC only once past --rc-fail-km and in a sweep")
    ap.add_argument("--batt-fail-in-sweep", action="store_true",
                    help="RFSEARCH failsafe test: in the first sweep past --rc-fail-km, raise BATT_LOW_MAH "
                         "so the low-battery failsafe fires (BATT_FS_LOW_ACT, RTL in believer_mission.parm)")
    ap.add_argument("--rf-scenario", default="auto",
                    help="hidden sources for the companion (rf_companion.py --scenario: auto, single, multi, multi_b)")
    ap.add_argument("--rf-seed", type=int, default=7,
                    help="random seed of the companion's simulated readings (rf_companion.py --seed)")
    ap.add_argument("--rf", action="store_true",
                    help="also run compare/rf_companion.py on SERIAL2 (RF direction finding; use with "
                         "--plan sim/missions/tsuniv_rf_search.plan)")
    ap.add_argument("--upload", action="store_true",
                    help="upload the plan, arm and start --mode from this script (test run without QGC)")
    ap.add_argument("--instance", type=int, default=0,
                    help="SITL instance (ports +10 each): a test run beside a QGC flight on instance 0")
    ap.add_argument("--mode", choices=MISSION_MODES, default="AUTO",
                    help="mission mode set with --upload (with QGC the operator picks it)")
    args = ap.parse_args()
    if args.hold is None:
        args.hold = 0.0 if args.upload else 1800.0

    if cp.ports_busy(args.instance):
        sys.exit(f"SITL ports for instance {args.instance} are in use: stop the other SITL first.")
    # instance in the name: runs on several instances may start in the same second
    tag = f"-i{args.instance}" if args.instance else ""
    out = cp.ROOT / "compare/results" / f"mission-{datetime.now():%Y%m%d-%H%M%S}{tag}" / args.model
    out.mkdir(parents=True)
    cfg = dict(cp.MODELS[args.model])
    # SITL runs in the results folder, so parameter files need absolute paths
    cfg["defaults"] = list(cfg["defaults"]) + [MISSION_PARM] + [q.resolve() for q in args.params]
    # QGC link only when QGC is meant to fly it: a scripted --upload run would otherwise show up in
    # (and take commands from) any QGC left open
    cfg["sitl_args"] = [] if args.upload else ["--serial1", "udpclient:127.0.0.1:14550"]
    run = cp.Run(args.model, cfg, out, args.speedup, args.instance)
    events = []
    companion = None
    try:
        run.start()
        if args.rf:
            companion = subprocess.Popen(
                [sys.executable, str(cp.ROOT / "compare/rf_companion.py"), "--plan", str(args.plan.resolve()),
                 "--out", str(out), "--instance", str(args.instance), "--scenario", args.rf_scenario,
                 "--seed", str(args.rf_seed)], stdout=open(out / "rf_companion.log", "w"), stderr=subprocess.STDOUT)
        f = fly(args, events)
        if companion is not None:
            # the final source fit can take a minute or two of wall time after the landing
            start = time.time()
            while (companion.poll() is None and not (out / "rf_result.json").exists()
                   and time.time() - start < 600):
                time.sleep(2)
            print(f"{datetime.now():%H:%M:%S}  RF result "
                  + ("written" if (out / "rf_result.json").exists() else "missing"), flush=True)
    finally:
        if companion is not None:
            companion.terminate()
            companion.wait(timeout=10)
        run.stop()
        (out / "events.txt").write_text("".join(f"{t:8.1f}  {e}\n" for t, e in events))
    with open(out / "track.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(f.samples[0]))
        w.writeheader()
        w.writerows(f.samples)
    report(args, out, f, events)


def fly(args, events):
    f = cp.Flight(f"tcp:127.0.0.1:{5760 + 10 * args.instance}")
    if f.m.wait_heartbeat(timeout=60) is None:
        raise RuntimeError("no heartbeat")
    f.m.mav.request_data_stream_send(f.m.target_system, f.m.target_component,
                                     mavutil.mavlink.MAV_DATA_STREAM_ALL, 4, 1)
    endurance.wait_ready(f)
    home = f.m.messages["GLOBAL_POSITION_INT"]
    state = dict(mode=None, seq=None, armed=False, ntexts=0, sweep=0)

    def log(e):
        events.append((round(f.t, 1), e))
        print(f"{datetime.now():%H:%M:%S}  t={f.t:7.1f}  {e}", flush=True)

    def dist():
        p = f.m.messages["GLOBAL_POSITION_INT"]
        return dist_m(home.lat / 1e7, home.lon / 1e7, p.lat / 1e7, p.lon / 1e7)

    def poll(timeout=1.0):
        msg = f.recv(timeout)
        if msg is not None and msg.get_type() == "NAMED_VALUE_FLOAT" and msg.name == "RFS_SWP":
            state["sweep"] = int(msg.value)       # RFSEARCH sweep phase, 0 = tracking the leg
        # pymavlink tracks these from the vehicle's own heartbeats (QGC's are forwarded here too)
        armed = bool(f.m.motors_armed())
        if armed != state["armed"]:
            state["armed"] = armed
            log("ARMED" if armed else "DISARMED")
        if f.m.flightmode != state["mode"]:
            state["mode"] = f.m.flightmode
            log(f"mode {state['mode']}")
        mc = f.m.messages.get("MISSION_CURRENT")
        if mc is not None and mc.seq != state["seq"]:
            state["seq"] = mc.seq
            log(f"mission item {mc.seq}  ({dist() / 1000:.2f} km from home, {f.alt():.0f} m)")
        for t, s in f.texts[state["ntexts"]:]:
            events.append((t, f"text: {s}"))
            print(f"{datetime.now():%H:%M:%S}  t={t:7.1f}  text: {s}", flush=True)
        state["ntexts"] = len(f.texts)
        return msg

    def wait(cond, wall_limit, what):
        start, last = time.time(), time.time()
        while not cond():
            if poll() is not None:
                last = time.time()
            elif time.time() - last > 30:
                raise RuntimeError("telemetry stopped (no messages for 30 s)")
            if time.time() - start > wall_limit:
                raise RuntimeError(f"{what}: not done within {wall_limit:.0f} wall s")

    if args.upload:
        n_mis, n_fence = upload_plan(f, args.plan)
        log(f"uploaded {args.plan.name} without QGC: {n_mis} mission items, {n_fence} fence items")
        f.m.set_mode(args.mode)
        f.m.arducopter_arm()
    else:
        log(f"ready; waiting for QGC: upload {args.plan.name}, arm, start mission")
    wait(lambda: state["armed"] and state["mode"] in MISSION_MODES, args.wait_operator,
         "arm + AUTO/RFSEARCH from QGC")
    f.m.mav.command_long_send(f.m.target_system, f.m.target_component,
                              mavutil.mavlink.MAV_CMD_DO_SET_SERVO, 0, 7, 2000, 0, 0, 0, 0, 0)
    log("catapult released (servo 7 = 2000)")

    if args.batt_fail_in_sweep:
        wait(lambda: (state["seq"] or 0) >= 2 and dist() > args.rc_fail_km * 1000 and state["sweep"],
             3600, "a sweep past --rc-fail-km")
        f.m.param_set_send("BATT_LOW_MAH", 100000)
        log(f"BATTERY LOW forced (BATT_LOW_MAH 100000) at {dist() / 1000:.2f} km, mode {state['mode']}, "
            f"sweep phase {state['sweep']}")
    elif args.rc_fail_km > 0:
        wait(lambda: (state["seq"] or 0) >= 2 and dist() > args.rc_fail_km * 1000
             and (state["sweep"] or not args.rc_fail_in_sweep), 3600, "reach the search area")
        f.m.param_set_send("SIM_RC_FAIL", 1)
        log(f"RC LOST (SIM_RC_FAIL 1) at {dist() / 1000:.2f} km, mode {state['mode']}, item {state['seq']}"
            + (f", sweep phase {state['sweep']}" if args.rc_fail_in_sweep else ""))
        t_fail = f.t
        if args.rc_fail_s > 0:
            wait(lambda: f.t - t_fail >= args.rc_fail_s, 1800, "RC-loss window")
        else:
            # out of range: RC stays off until the aircraft is back inside the range after going 1 km past it
            peak = dict(d=0.0)

            def back_in_range():
                peak["d"] = max(peak["d"], dist())
                return peak["d"] > (args.rc_fail_km + 1) * 1000 and dist() < args.rc_fail_km * 1000

            wait(back_in_range, 7200, "return inside RC range")
        f.m.param_set_send("SIM_RC_FAIL", 0)
        log(f"RC restored (SIM_RC_FAIL 0) at {dist() / 1000:.2f} km, mode {state['mode']}, item {state['seq']}")

    near = dict(since=None)

    def finished():
        # normal end: landed and auto-disarmed (LAND_DISARMDELAY); fallback: circling home in RTL
        if not state["armed"]:
            return True
        if state["mode"] == "RTL" and dist() < args.home_radius:
            near["since"] = near["since"] or f.t
            return f.t - near["since"] >= 60
        near["since"] = None
        return False

    wait(finished, 3600, "landing or RTL to home")
    p = f.m.messages["GLOBAL_POSITION_INT"]
    log(("landed and disarmed" if not state["armed"] else "in RTL loiter over home for 60 s")
        + f": {dist():.0f} m from home, {p.relative_alt / 1000:.1f} m, ground speed "
        + f"{math.hypot(p.vx, p.vy) / 100:.1f} m/s")
    if not state["armed"]:
        # After an autoland the mission stays "in landing sequence" and pre-arm refuses to arm
        # (AP_Arming_Plane.cpp). A mode change alone does not clear it in 4.7.3: set_mode() runs the new
        # mode's enter() (which resets the mission) before AUTO's exit(), and that exit restarts the
        # landing at DO_LAND_START again ("Restarted landing via DO_LAND_START"). So: leave AUTO, then
        # make item 1 (the take-off) current, as QGC's "set current waypoint" would; set_current_cmd()
        # clears the flag and the next AUTO starts from the take-off.
        f.m.set_mode("MANUAL")
        wait(lambda: state["mode"] == "MANUAL", 30, "switch to MANUAL after landing")
        f.m.mav.command_long_send(f.m.target_system, f.m.target_component,
                                  mavutil.mavlink.MAV_CMD_DO_SET_MISSION_CURRENT, 0, 1, 0, 0, 0, 0, 0, 0)
        wait(lambda: state["seq"] == 1, 30, "set mission item 1 current after landing")
        log("mission set back to item 1 (take-off): landing sequence cleared")
    if args.hold > 0:
        # keep SITL (and QGC's link) up for screenshots; the aircraft keeps circling home in RTL
        log(f"holding for {args.hold / 60:.0f} wall min, or until {STOP_FILE} exists")
        STOP_FILE.unlink(missing_ok=True)
        start = time.time()
        while time.time() - start < args.hold and not STOP_FILE.exists():
            poll()
        STOP_FILE.unlink(missing_ok=True)
    log("stopping")
    return f


def upload_plan(f, path):
    """Uploads a QGC .plan's mission and inclusion circles the way QGC does (for runs without QGC)."""
    plan = json.loads(path.read_text())
    home = plan["mission"]["plannedHomePosition"]
    mav = mavutil.mavlink
    mission = [(mav.MAV_CMD_NAV_WAYPOINT, 0, [0, 0, 0, 0, home[0], home[1], home[2]])]
    mission += [(it["command"], it["frame"], it["params"]) for it in plan["mission"]["items"]]
    fence = [(mav.MAV_CMD_NAV_FENCE_CIRCLE_INCLUSION, mav.MAV_FRAME_GLOBAL,
              [c["circle"]["radius"], 0, 0, 0, c["circle"]["center"][0], c["circle"]["center"][1], 0])
             for c in plan["geoFence"]["circles"] if c["inclusion"]]
    for kind, items in ((mav.MAV_MISSION_TYPE_MISSION, mission), (mav.MAV_MISSION_TYPE_FENCE, fence)):
        f.m.mav.mission_count_send(f.m.target_system, f.m.target_component, len(items), kind)
        while True:
            msg = f.recv(5.0, types=["MISSION_REQUEST_INT", "MISSION_REQUEST", "MISSION_ACK"])
            if msg is None:
                raise RuntimeError(f"mission upload (type {kind}): no reply")
            if msg.get_type() == "MISSION_ACK":
                if msg.type != mav.MAV_MISSION_ACCEPTED:
                    raise RuntimeError(f"mission upload (type {kind}) rejected: {msg.type}")
                break
            cmd, frame, p = items[msg.seq]
            p = [0 if v is None else v for v in p]
            x, y = (int(p[4] * 1e7), int(p[5] * 1e7)) if frame != 2 else (0, 0)
            f.m.mav.mission_item_int_send(f.m.target_system, f.m.target_component, msg.seq, frame, cmd,
                                          0, 1, p[0], p[1], p[2], p[3], x, y, p[6], kind)
    return len(mission), len(fence)


def report(args, out, f, events):
    fs = [f"| {t:.1f} | {e} |" for t, e in events
          if any(k in e for k in ("RC ", "Failsafe", "mode ", "catapult", "Fence", "fence", "Land",
                                  "lare", "ARMED", "landed"))]
    rc = (f"RC cut for {args.rc_fail_s:g} sim s" if args.rc_fail_s > 0 else "RC off for the whole time")
    lines = [f"# Mission: {args.plan.name}, {args.model}", "",
             f"Speedup {args.speedup:g}; {rc} beyond {args.rc_fail_km:g} km.", "",
             "| sim t, s | event |", "|---|---|", *fs, "",
             f"Full event list: events.txt ({len(events)} lines); track: track.csv; log: logs/."]
    (out / "summary.md").write_text("\n".join(lines) + "\n")
    print(f"\nResults: {out}")


if __name__ == "__main__":
    main()
