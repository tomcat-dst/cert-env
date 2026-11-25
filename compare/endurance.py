#!/usr/bin/env python3
"""
Endurance flight in SITL: take off, climb to a working altitude, orbit home on a wide circle
(nearly straight flight) at AIRSPEED_CRUISE until the battery reaches its reserve.

  compare/endurance.py --model believer-5kg --alt 900

Reuses compare_planes.py's models, process handling and readiness gate. Stops when the
consumed charge reaches BATT_CAPACITY - BATT_LOW_MAH (the planned reserve), or on --max-hours.

SITL's battery feeds propulsion only. The report therefore also gives a corrected flight time
with --payload-w (avionics + payload, default 18 W) added, counted to --usable (default 90%)
of the pack's nominal energy (--pack-wh).

Outputs (compare/results/endurance-<time>/<model>/): samples.csv, summary.md, sitl.log, logs/.
"""
import argparse
import csv
import math
import random
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import compare_planes as cp    # noqa: E402  (also enforces the venv)
from pymavlink import mavutil  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", default="believer-5kg", choices=sorted(cp.MODELS))
    ap.add_argument("--alt", type=float, default=900.0, help="working altitude above home, m")
    ap.add_argument("--orbit", type=float, default=500.0, help="orbit radius (WP_LOITER_RAD), m")
    ap.add_argument("--speedup", type=float, default=20.0)
    ap.add_argument("--pack-wh", type=float, default=444.0, help="nominal pack energy, Wh")
    ap.add_argument("--usable", type=float, default=0.9, help="usable fraction of pack energy")
    ap.add_argument("--payload-w", type=float, default=18.0, help="avionics + payload draw not in SITL, W")
    ap.add_argument("--max-hours", type=float, default=4.0, help="stop after this much flight time")
    ap.add_argument("--param", action="append", default=[], metavar="NAME=VALUE")
    ap.add_argument("--param-at", action="append", default=[], metavar="T:NAME=VALUE",
                    help="set a parameter T sim seconds after arming (e.g. end a take-off throttle boost)")
    ap.add_argument("--instance", type=int, default=0, help="SITL instance; ports shift by 10 each")
    ap.add_argument("--gusts", metavar="MIN:MAX", help="gusty wind: speed re-drawn uniformly in MIN..MAX m/s "
                    "every --gust-hold s (SITL eases to it with SIM_WIND_TC); off by default")
    ap.add_argument("--gust-dir", type=float, default=290.0, help="mean wind direction (from), deg")
    ap.add_argument("--gust-dir-var", type=float, default=30.0, help="direction drawn within +- this, deg")
    ap.add_argument("--gust-hold", metavar="MIN:MAX", default="5:20", help="seconds each gust value holds")
    ap.add_argument("--seed", type=int, default=1, help="gust random seed (same seed = same sequence)")
    args = ap.parse_args()

    if cp.ports_busy(args.instance):
        sys.exit(f"SITL ports for instance {args.instance} are in use; pick another --instance.")
    out = cp.ROOT / "compare/results" / f"endurance-{datetime.now():%Y%m%d-%H%M%S}" / args.model
    out.mkdir(parents=True)
    run = cp.Run(args.model, cp.MODELS[args.model], out, args.speedup, args.instance)
    try:
        run.start()
        rows, summary = fly(args)
    finally:
        run.stop()

    with open(out / "samples.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    text = report(args, summary)
    (out / "summary.md").write_text(text)
    print(f"\nResults: {out}\n\n{text}")


def fly(args):
    f = cp.Flight(f"tcp:127.0.0.1:{5760 + 10 * args.instance}")
    if f.m.wait_heartbeat(timeout=60) is None:
        raise RuntimeError("no heartbeat")
    f.m.mav.request_data_stream_send(f.m.target_system, f.m.target_component,
                                     mavutil.mavlink.MAV_DATA_STREAM_ALL, 4, 1)
    wait_ready(f)
    # WP_LOITER_RAD is set only after takeoff: TAKEOFF mode loiters around a point TKOFF_DIST
    # (200 m) ahead with this radius, and a 500 m circle there makes it bank hard at 20-50 m.
    overrides = {"FLIGHT_OPTIONS": 4, "TKOFF_ALT": 120}
    for p in args.param:
        name, value = p.split("=", 1)
        overrides[name] = float(value)
    for name, value in overrides.items():
        f.set_param(name, value)
    capacity, reserve = f.param("BATT_CAPACITY"), f.param("BATT_LOW_MAH")
    stop_mah = capacity - reserve
    home = f.m.messages["GLOBAL_POSITION_INT"]

    rows, last_t = [], -1.0
    state = dict(phase="takeoff", mah=0.0, wh=0.0, last_e_t=None)

    def sample():
        nonlocal last_t
        sys_s, bat = f.m.messages.get("SYS_STATUS"), f.m.messages.get("BATTERY_STATUS")
        vfr, pos, att = (f.m.messages.get(n) for n in ("VFR_HUD", "GLOBAL_POSITION_INT", "ATTITUDE"))
        if not (sys_s and vfr and pos and att):
            return
        volts, amps = sys_s.voltage_battery / 1000.0, max(sys_s.current_battery, 0) / 100.0
        if state["last_e_t"] is not None:
            state["wh"] += volts * amps * (f.t - state["last_e_t"]) / 3600.0
        state["last_e_t"] = f.t
        if bat is not None and bat.current_consumed >= 0:
            state["mah"] = bat.current_consumed
        if f.t - last_t >= 2.0:
            last_t = f.t
            rows.append(dict(t=round(f.t, 1), phase=state["phase"], mode=f.m.flightmode,
                             alt=round(pos.relative_alt / 1000.0, 1),
                             airspeed=round(vfr.airspeed, 2), groundspeed=round(vfr.groundspeed, 2),
                             throttle=vfr.throttle, roll=round(math.degrees(att.roll), 1),
                             volts=round(volts, 2), amps=round(amps, 2),
                             mah=round(state["mah"]), prop_wh=round(state["wh"], 2)))

    gust = None
    if args.gusts:
        lo, hi = (float(x) for x in args.gusts.split(":"))
        hlo, hhi = (float(x) for x in args.gust_hold.split(":"))
        gust = dict(rng=random.Random(args.seed), lo=lo, hi=hi, hlo=hlo, hhi=hhi, next_t=0.0)

    def gust_update():
        # new wind every few sim seconds; sent without read-back so the sampling loop keeps running
        if gust is None or f.t < gust["next_t"]:
            return
        r = gust["rng"]
        spd = r.uniform(gust["lo"], gust["hi"])
        direction = (args.gust_dir + r.uniform(-args.gust_dir_var, args.gust_dir_var)) % 360
        f.m.param_set_send("SIM_WIND_SPD", spd)
        f.m.param_set_send("SIM_WIND_DIR", direction)
        gust["next_t"] = f.t + r.uniform(gust["hlo"], gust["hhi"])

    timed = sorted((float(t), *nv.split("=", 1)) for t, nv in (p.split(":", 1) for p in args.param_at))

    def timed_update():
        # sent without read-back, like the gusts
        while timed and f.t - t_arm >= timed[0][0]:
            _, name, value = timed.pop(0)
            f.m.param_set_send(name, float(value))

    def step(stop):
        last_msg = time.time()
        while not stop():
            if f.recv(1.0) is not None:
                last_msg = time.time()
                sample()
                gust_update()
                timed_update()
            elif time.time() - last_msg > 30:
                raise RuntimeError("telemetry stopped (no messages for 30 s)")

    f.m.set_mode("TAKEOFF")
    f.m.arducopter_arm()
    f.m.motors_armed_wait()
    t_arm, wh_arm = f.t, state["wh"]
    # fire the launcher (SITL: servo 7 > 1700); harmless for models without launch_accel
    f.m.mav.command_long_send(f.m.target_system, f.m.target_component,
                              mavutil.mavlink.MAV_CMD_DO_SET_SERVO, 0, 7, 2000, 0, 0, 0, 0, 0)
    step(lambda: f.alt() >= 108.0 or f.t - t_arm > 180)

    state["phase"] = "climb"
    f.set_param("WP_LOITER_RAD", args.orbit)
    f.m.mav.command_int_send(f.m.target_system, f.m.target_component,
                             mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT,
                             mavutil.mavlink.MAV_CMD_DO_REPOSITION, 0, 0,
                             -1, mavutil.mavlink.MAV_DO_REPOSITION_FLAGS_CHANGE_MODE, 0, 0,
                             home.lat, home.lon, args.alt)
    step(lambda: f.alt() >= 0.98 * args.alt or f.t - t_arm > 1200)
    t_top, wh_top, mah_top = f.t, state["wh"], state["mah"]

    state["phase"] = "cruise"
    step(lambda: state["mah"] >= stop_mah or f.t - t_arm > args.max_hours * 3600)
    t_end = f.t
    f.m.set_mode("RTL")
    step(lambda: f.t - t_end > 5)

    cruise = [r for r in rows if r["phase"] == "cruise" and r["t"] > t_top + 60]
    if not cruise:
        raise RuntimeError("no cruise samples (over 60 s after the climb): raise --max-hours")
    mean = lambda k: sum(abs(r[k]) for r in cruise) / len(cruise)   # noqa: E731
    return rows, dict(
        capacity=capacity, reserve=reserve, stop_mah=stop_mah,
        reached_reserve=state["mah"] >= stop_mah,
        flight_s=t_end - t_arm, climb_s=t_top - t_arm, climb_wh=wh_top - wh_arm, climb_mah=mah_top,
        prop_wh=state["wh"] - wh_arm, mah=state["mah"],
        airspeed=mean("airspeed"), groundspeed=mean("groundspeed"), throttle=mean("throttle"),
        roll=mean("roll"), volts=mean("volts"), amps=mean("amps"),
        cruise_w=sum(r["volts"] * r["amps"] for r in cruise) / len(cruise),
        start_v=rows[0]["volts"], end_v=rows[-1]["volts"], alt=mean("alt"))


def wait_ready(f):
    ekf_needed, ekf_bad = 1 | 2 | 4 | 16 | 32, 128 | 1024
    deadline = time.time() + 180
    while True:
        f.recv(2.0)
        sys_s, gps, ekf = (f.m.messages.get(n) for n in ("SYS_STATUS", "GPS_RAW_INT", "EKF_STATUS_REPORT"))
        if (sys_s and sys_s.onboard_control_sensors_health & mavutil.mavlink.MAV_SYS_STATUS_PREARM_CHECK
                and gps and gps.fix_type >= 3
                and ekf and (ekf.flags & ekf_needed) == ekf_needed and not ekf.flags & ekf_bad):
            return
        if time.time() > deadline:
            raise RuntimeError("vehicle never became ready (prearm/GPS/EKF)")


def report(args, s):
    usable_wh = args.pack_wh * args.usable
    # corrected endurance: climb as flown, then cruise at the measured power plus the payload draw
    climb_total_wh = s["climb_wh"] + args.payload_w * s["climb_s"] / 3600.0
    cruise_h = (usable_wh - climb_total_wh) / (s["cruise_w"] + args.payload_w)
    corrected_min = s["climb_s"] / 60.0 + cruise_h * 60.0
    hm = lambda m: f"{int(m // 60)} h {m % 60:02.0f} min"   # noqa: E731
    lines = [
        f"# Endurance: {args.model}, {args.alt:.0f} m above home",
        "",
        f"Orbit radius {args.orbit:.0f} m, speedup {args.speedup:g}. SITL battery feeds propulsion only.",
        (f"Gusty wind {args.gusts} m/s from {args.gust_dir:g} +- {args.gust_dir_var:g} deg, new value every "
         f"{args.gust_hold} s (seed {args.seed}). " if args.gusts else "No gust schedule. ")
        + ("Extra parameters: " + ", ".join(args.param) + "." if args.param else "")
        + (" Timed (s after arming): " + ", ".join(args.param_at) + "." if args.param_at else ""),
        "",
        "| | Value |",
        "|---|---|",
        f"| Climb to {args.alt:.0f} m | {s['climb_s'] / 60:.1f} min, {s['climb_wh']:.1f} Wh, {s['climb_mah']:.0f} mAh |",
        f"| Cruise airspeed / groundspeed | {s['airspeed']:.1f} / {s['groundspeed']:.1f} m/s |",
        f"| Cruise throttle, bank | {s['throttle']:.1f}%, {s['roll']:.1f} deg |",
        f"| Cruise battery | {s['amps']:.2f} A at {s['volts']:.2f} V, {s['cruise_w']:.0f} W |",
        f"| Pack voltage start / end | {s['start_v']:.2f} / {s['end_v']:.2f} V |",
        f"| **SITL flight time to reserve** ({s['stop_mah']:.0f} of {s['capacity']:.0f} mAh, propulsion only) "
        f"| **{hm(s['flight_s'] / 60)}**{'' if s['reached_reserve'] else ' (reserve NOT reached: stopped by --max-hours)'} |",
        f"| **Corrected flight time** (+{args.payload_w:g} W payload, {args.usable:.0%} of {args.pack_wh:g} Wh) "
        f"| **{hm(corrected_min)}** |",
        "",
    ]
    return "\n".join(lines)


if __name__ == "__main__":
    main()
