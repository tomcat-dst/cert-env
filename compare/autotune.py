#!/usr/bin/env python3
"""
ArduPlane AUTOTUNE flight in SITL, following Tools/autotest/arduplane.py run_autotune: catapult
launch, TAKEOFF, GUIDED climb to --alt, then AUTOTUNE mode with full-stick roll doublets (stick
reversed every --period s) until "Roll: Finished", sticks centred for 15 s, then pitch doublets until
"Pitch: Finished". Then RTL. Sticks come from MAVLink RC overrides; throttle stick --throttle %.

  compare/autotune.py --model believer-5kg-avl-mfe --out sim/params/believer_5kg_avl_autotune.parm

AUTOTUNE saves each axis' gains when it prints "<axis>: Finished" (APM_Control/AP_AutoTune.cpp);
the script then reads the tuned parameters back and writes them as a parameter file that can be
layered after the model's other parameter files. Outputs (compare/results/autotune-<time>/<model>/):
the dataflash log, texts.txt and tuned.parm (also copied to --out).
"""
import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import compare_planes as cp    # noqa: E402  (also enforces the venv)
import endurance               # noqa: E402
from pymavlink import mavutil  # noqa: E402

TUNED = ["RLL_RATE_P", "RLL_RATE_I", "RLL_RATE_D", "RLL_RATE_FF", "RLL_RATE_IMAX", "RLL_RATE_FLTT",
         "RLL_RATE_FLTD", "RLL_RATE_FLTE", "RLL2SRV_TCONST", "RLL2SRV_RMAX",
         "PTCH_RATE_P", "PTCH_RATE_I", "PTCH_RATE_D", "PTCH_RATE_FF", "PTCH_RATE_IMAX", "PTCH_RATE_FLTT",
         "PTCH_RATE_FLTD", "PTCH_RATE_FLTE", "PTCH2SRV_TCONST", "PTCH2SRV_RMAX_UP", "PTCH2SRV_RMAX_DN",
         "AUTOTUNE_LEVEL", "AUTOTUNE_AXES"]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", required=True, choices=sorted(cp.MODELS))
    ap.add_argument("--alt", type=float, default=300.0, help="altitude above home for the tune, m")
    ap.add_argument("--throttle", type=float, default=60.0, help="throttle stick in AUTOTUNE, %%")
    ap.add_argument("--period", type=float, default=1.0, help="stick reversal period, sim s")
    ap.add_argument("--timeout", type=float, default=900.0, help="per-axis limit, sim s")
    ap.add_argument("--speedup", type=float, default=20.0)
    ap.add_argument("--instance", type=int, default=0)
    ap.add_argument("--out", type=Path, help="also write the tuned parameters here")
    args = ap.parse_args()

    if cp.ports_busy(args.instance):
        sys.exit(f"SITL ports for instance {args.instance} are in use; pick another --instance.")
    out = cp.ROOT / "compare/results" / f"autotune-{datetime.now():%Y%m%d-%H%M%S}" / args.model
    out.mkdir(parents=True)
    run = cp.Run(args.model, cp.MODELS[args.model], out, args.speedup, args.instance)
    try:
        run.start()
        f, before, after = fly(args)
    finally:
        run.stop()

    (out / "texts.txt").write_text("".join(f"{t:8.1f} {s}\n" for t, s in f.texts))
    lines = [f"# AUTOTUNE result for {args.model}, {datetime.now():%Y-%m-%d %H:%M}, compare/autotune.py",
             f"# Tuned in SITL ({out.relative_to(cp.ROOT)}); load after the model's other parameter files.",
             "# name value   (value before the tune)"]
    lines += [f"{k:16s} {after[k]:.7g}   # was {before[k]:.7g}" for k in TUNED]
    text = "\n".join(lines) + "\n"
    (out / "tuned.parm").write_text(text)
    if args.out:
        args.out.write_text(text)
    print(f"\nResults: {out}\n\n{text}")


def fly(args):
    f = cp.Flight(f"tcp:127.0.0.1:{5760 + 10 * args.instance}")
    if f.m.wait_heartbeat(timeout=60) is None:
        raise RuntimeError("no heartbeat")
    f.m.mav.request_data_stream_send(f.m.target_system, f.m.target_component,
                                     mavutil.mavlink.MAV_DATA_STREAM_ALL, 4, 1)
    endurance.wait_ready(f)
    for name, value in {"FLIGHT_OPTIONS": 4, "TKOFF_ALT": 120}.items():
        f.set_param(name, value)
    before = {k: f.param(k) for k in TUNED}
    home = f.m.messages["GLOBAL_POSITION_INT"]

    def step(stop, limit, what):
        t0, last = f.t, time.time()
        while not stop():
            if f.recv(1.0) is not None:
                last = time.time()
            elif time.time() - last > 30:
                raise RuntimeError("telemetry stopped (no messages for 30 s)")
            if f.t - t0 > limit:
                raise RuntimeError(f"{what}: not done within {limit:.0f} sim s")

    f.m.set_mode("TAKEOFF")
    f.m.arducopter_arm()
    f.m.motors_armed_wait()
    f.m.mav.command_long_send(f.m.target_system, f.m.target_component,
                              mavutil.mavlink.MAV_CMD_DO_SET_SERVO, 0, 7, 2000, 0, 0, 0, 0, 0)
    step(lambda: f.alt() >= 108.0, 180, "takeoff")
    f.m.mav.command_int_send(f.m.target_system, f.m.target_component,
                             mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT_INT,
                             mavutil.mavlink.MAV_CMD_DO_REPOSITION, 0, 0,
                             -1, mavutil.mavlink.MAV_DO_REPOSITION_FLAGS_CHANGE_MODE, 0, 0,
                             home.lat, home.lon, args.alt)
    step(lambda: f.alt() >= 0.98 * args.alt, 600, "climb")

    thr = int(1000 + 10 * args.throttle)
    sticks = {"roll": 1500, "pitch": 1500}

    def override():
        f.m.mav.rc_channels_override_send(f.m.target_system, f.m.target_component,
                                          sticks["roll"], sticks["pitch"], thr, 1500, 0, 0, 0, 0)

    def finished(axis):
        return any(f"{axis}: Finished" in s for _, s in f.texts)

    override()
    f.m.set_mode("AUTOTUNE")
    for axis, key in (("Roll", "roll"), ("Pitch", "pitch")):
        t0, t_flip, value = f.t, f.t, 1000
        while not finished(axis):
            if f.t - t_flip >= args.period:
                value = 2000 if value == 1000 else 1000
                t_flip = f.t
            sticks.update(roll=1500, pitch=1500)
            sticks[key] = value
            override()
            f.recv(0.2)
            if f.t - t0 > args.timeout:
                raise RuntimeError(f"AUTOTUNE {axis}: not finished within {args.timeout:.0f} sim s")
        sticks.update(roll=1500, pitch=1500)
        t_c = f.t
        while f.t - t_c < 15:
            override()
            f.recv(0.2)
    f.m.set_mode("RTL")
    f.m.mav.rc_channels_override_send(f.m.target_system, f.m.target_component, 0, 0, 0, 0, 0, 0, 0, 0)
    f.run_for(10)
    after = {k: f.param(k) for k in TUNED}
    return f, before, after


if __name__ == "__main__":
    main()
