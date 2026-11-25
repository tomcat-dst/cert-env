#!/usr/bin/env python3
"""Fly several fixed-wing physics models through one identical profile and compare.

Each model is launched the way sim_vehicle.py would (same frame default params),
in its own run directory, then flown by this script over MAVLink:

  takeoff  TAKEOFF mode to TKOFF_ALT
  settle   LOITER, 20 s (not scored)
  loiter   LOITER, 60 s: airspeed, throttle, altitude hold, bank, loiter radius
  glide    LOITER with THR_MAX=0, up to 45 s (first 5 s not scored): sink rate, glide ratio

All durations are simulated time (from the autopilot's time_boot_ms), so results
don't depend on --speedup. Outputs per run: samples.csv, the SITL log and the
DataFlash .BIN; plus summary.csv, summary.md and plots in the results directory.

Usage:
  compare_planes.py                          # all models
  compare_planes.py --models plane,skywalker
  compare_planes.py --param AIRSPEED_CRUISE=15 --param TRIM_THROTTLE=45
"""
import argparse
import csv
import importlib.util
import math
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

# System Python mixes apt's matplotlib (NumPy 1.x) with any user-installed NumPy 2.x and
# crashes at plotting time; the venv has a matching set.
if Path(sys.prefix).resolve() != (Path.home() / "cert-env/venv").resolve():
    sys.exit(f"Running under {sys.executable}, not the cert-env venv: "
             "run `source ~/cert-env/env.sh` first.")

from pymavlink import mavutil

ROOT = Path.home() / "cert-env"
# ARDUPILOT_DIR selects another ArduPilot checkout (e.g. a master worktree); default is ours.
ARDUPILOT = Path(os.environ.get("ARDUPILOT_DIR", ROOT / "src/ardupilot"))
AUTOTEST = ARDUPILOT / "Tools/autotest"
ARDUPLANE = ARDUPILOT / "build/sitl/bin/arduplane"
# SITL home: lat,lon,alt AMSL,heading. Default is Tsuniv airfield (Lviv region), midpoint of
# grass runway 10/28 from OpenStreetMap; 290 m from SRTM/EU-DEM (OurAirports lists 265 m).
# Altitude matters: the built-in plane's air density follows it. SITL_HOME overrides.
HOME = os.environ.get("SITL_HOME", "49.825888,23.689912,290,109")

# engine "sitl": SITL's built-in physics (the only engine; the field stays in the summaries).
MODELS = {
    "plane":        dict(frame="plane", engine="sitl"),
    # Coefficient-for-coefficient identical to "plane" (SITL's defaults come from the
    # same file): flying both measures the harness's own run-to-run noise.
    "skywalker":    dict(frame="plane", model="plane:@ROMFS/models/skywalker_2013.json",
                         engine="sitl"),
    # Illustrative longer, lower-drag wing; see the header of the JSON file.
    # "model_file" is copied into the run directory: SITL strips the leading "/" from
    # absolute paths, so it can only open files relative to where it was started.
    "high-ar":      dict(frame="plane", engine="sitl",
                         model_file=ROOT / "compare/models/plane_high_ar.json"),
    "plane-elevon": dict(frame="plane-elevon", engine="sitl"),
    # MFE Believer 1960, current design (5.9 kg, 2.36 m wing, Starlink, 6S5P), SITL's built-in physics
    # plus the local propulsion patch; see the header of the JSON file.
    "believer":     dict(frame="plane", engine="sitl",
                         model_file=ROOT / "compare/models/believer.json",
                         defaults=[AUTOTEST / "models/plane.parm",
                                   ROOT / "sim/params/believer.parm"]),
    # The original 5.0 kg design (1.96 m wing, 6S4P, no Starlink), for comparison.
    "believer-5kg": dict(frame="plane", engine="sitl",
                         model_file=ROOT / "compare/models/believer_5kg.json",
                         defaults=[AUTOTEST / "models/plane.parm",
                                   ROOT / "sim/params/believer_5kg.parm"]),
    # The same two airframes with AVL-derived stability and control derivatives
    # (aero/avl/believer_avl.py; tail, controls and CG estimated).
    "believer-avl": dict(frame="plane", engine="sitl",
                         model_file=ROOT / "compare/models/believer_avl.json",
                         defaults=[AUTOTEST / "models/plane.parm",
                                   ROOT / "sim/params/believer.parm"]),
    "believer-5kg-avl": dict(frame="plane", engine="sitl",
                         model_file=ROOT / "compare/models/believer_5kg_avl.json",
                         defaults=[AUTOTEST / "models/plane.parm",
                                   ROOT / "sim/params/believer_5kg.parm"]),
    # AVL airframes with MakeFlyEasy's stock gains and limits (sim/params/believer_mfe.parm)
    # and MIXING_GAIN 1 ruddervator authority in the model.
    "believer-avl-mfe": dict(frame="plane", engine="sitl",
                         model_file=ROOT / "compare/models/believer_avl_mfe.json",
                         defaults=[AUTOTEST / "models/plane.parm",
                                   ROOT / "sim/params/believer.parm",
                                   ROOT / "sim/params/believer_mfe.parm"]),
    "believer-5kg-avl-mfe": dict(frame="plane", engine="sitl",
                         model_file=ROOT / "compare/models/believer_5kg_avl_mfe.json",
                         defaults=[AUTOTEST / "models/plane.parm",
                                   ROOT / "sim/params/believer_5kg.parm",
                                   ROOT / "sim/params/believer_mfe.parm"]),
    # The same with the SITL AUTOTUNE result layered last (compare/autotune.py).
    "believer-avl-at": dict(frame="plane", engine="sitl",
                         model_file=ROOT / "compare/models/believer_avl_mfe.json",
                         defaults=[AUTOTEST / "models/plane.parm",
                                   ROOT / "sim/params/believer.parm",
                                   ROOT / "sim/params/believer_mfe.parm",
                                   ROOT / "sim/params/believer_avl_autotune.parm"]),
    "believer-5kg-avl-at": dict(frame="plane", engine="sitl",
                         model_file=ROOT / "compare/models/believer_5kg_avl_mfe.json",
                         defaults=[AUTOTEST / "models/plane.parm",
                                   ROOT / "sim/params/believer_5kg.parm",
                                   ROOT / "sim/params/believer_mfe.parm",
                                   ROOT / "sim/params/believer_5kg_avl_autotune.parm"]),
    # The same two with a gentler catapult (25 m/s^2 for 0.65 s instead of 59 m/s^2 for 0.39 s).
    "believer-avl-at-gentle": dict(frame="plane", engine="sitl",
                         model_file=ROOT / "compare/models/believer_avl_mfe_gentle.json",
                         defaults=[AUTOTEST / "models/plane.parm",
                                   ROOT / "sim/params/believer.parm",
                                   ROOT / "sim/params/believer_mfe.parm",
                                   ROOT / "sim/params/believer_avl_autotune.parm"]),
    "believer-5kg-avl-at-gentle": dict(frame="plane", engine="sitl",
                         model_file=ROOT / "compare/models/believer_5kg_avl_mfe_gentle.json",
                         defaults=[AUTOTEST / "models/plane.parm",
                                   ROOT / "sim/params/believer_5kg.parm",
                                   ROOT / "sim/params/believer_mfe.parm",
                                   ROOT / "sim/params/believer_5kg_avl_autotune.parm"]),
    # 3 g catapult (29.4 m/s^2 for 0.51 s).
    "believer-avl-at-3g": dict(frame="plane", engine="sitl",
                         model_file=ROOT / "compare/models/believer_avl_mfe_3g.json",
                         defaults=[AUTOTEST / "models/plane.parm",
                                   ROOT / "sim/params/believer.parm",
                                   ROOT / "sim/params/believer_mfe.parm",
                                   ROOT / "sim/params/believer_avl_autotune.parm"]),
    "believer-5kg-avl-at-3g": dict(frame="plane", engine="sitl",
                         model_file=ROOT / "compare/models/believer_5kg_avl_mfe_3g.json",
                         defaults=[AUTOTEST / "models/plane.parm",
                                   ROOT / "sim/params/believer_5kg.parm",
                                   ROOT / "sim/params/believer_mfe.parm",
                                   ROOT / "sim/params/believer_5kg_avl_autotune.parm"]),
    # 3.3 g catapult (32.4 m/s^2 for 0.48 s).
    "believer-avl-at-3g3": dict(frame="plane", engine="sitl",
                         model_file=ROOT / "compare/models/believer_avl_mfe_3g3.json",
                         defaults=[AUTOTEST / "models/plane.parm",
                                   ROOT / "sim/params/believer.parm",
                                   ROOT / "sim/params/believer_mfe.parm",
                                   ROOT / "sim/params/believer_avl_autotune.parm"]),
    "believer-5kg-avl-at-3g3": dict(frame="plane", engine="sitl",
                         model_file=ROOT / "compare/models/believer_5kg_avl_mfe_3g3.json",
                         defaults=[AUTOTEST / "models/plane.parm",
                                   ROOT / "sim/params/believer_5kg.parm",
                                   ROOT / "sim/params/believer_mfe.parm",
                                   ROOT / "sim/params/believer_5kg_avl_autotune.parm"]),
}

# Applied to every model. FLIGHT_OPTIONS bit 2 skips the takeoff attitude check; every
# recorded run used it, so it stays.
# TKOFF_ALT 120 leaves ~100 m for the glide, so it reaches a steady state.
COMMON_PARAMS = {"FLIGHT_OPTIONS": 4, "TKOFF_ALT": 120}

# Recorded per model so differing stock configurations are visible in the results.
REPORT_PARAMS = ["AIRSPEED_CRUISE", "AIRSPEED_MIN", "AIRSPEED_MAX", "ARSPD_USE",
                 "TRIM_THROTTLE", "THR_MAX", "TKOFF_ALT", "WP_LOITER_RAD", "SIM_WIND_SPD"]

PHASES = [("settle", 20.0), ("loiter", 60.0), ("glide", 45.0)]
GLIDE_FLOOR_M = 20.0
GLIDE_SKIP_S = 5.0      # pitch-over transient after cutting the throttle, not scored


# --------------------------------------------------------------------------- launch

def frame_defaults(frame):
    spec = importlib.util.spec_from_file_location("vehicleinfo", AUTOTEST / "pysim/vehicleinfo.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    files = mod.VehicleInfo().options["ArduPlane"]["frames"][frame]["default_params_filename"]
    if isinstance(files, str):
        files = [files]
    return [str(AUTOTEST / f) for f in files]


def ports_busy(instance=0):
    for port, kind in ((5760 + 10 * instance, socket.SOCK_STREAM), (9002 + 10 * instance, socket.SOCK_DGRAM)):
        s = socket.socket(socket.AF_INET, kind)
        # Bind the way SITL does: a live listener still fails, a TIME_WAIT leftover doesn't.
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(("127.0.0.1", port))
        except OSError:
            return port
        finally:
            s.close()
    return None


class Run:
    """Owns the processes for one model; everything is killed by process group."""

    def __init__(self, name, cfg, rundir, speedup, instance=0):
        self.name, self.cfg, self.dir, self.speedup = name, cfg, rundir, speedup
        self.instance = instance    # SITL -I: ports shift by 10 per instance (SITL only)
        self.procs = []

    def _spawn(self, cmd, log):
        p = subprocess.Popen(cmd, cwd=self.dir, stdout=open(self.dir / log, "w"),
                             stderr=subprocess.STDOUT, start_new_session=True)
        self.procs.append(p)
        return p

    def start(self):
        model = self.cfg.get("model", self.cfg["frame"])
        if "model_file" in self.cfg:
            src = Path(self.cfg["model_file"])
            shutil.copy(src, self.dir / src.name)
            model = f"plane:{src.name}"
        cmd = [str(ARDUPLANE), "--model", model,
               "--speedup", str(self.speedup), "-w", f"-I{self.instance}", "--home", HOME,
               "--defaults", ",".join(str(p) for p in self.cfg.get("defaults")
                                      or frame_defaults(self.cfg["frame"]))]
        cmd += self.cfg.get("sitl_args", [])    # e.g. ["--serial1", "udpclient:127.0.0.1:14550"]
        self._spawn(cmd, "sitl.log")
        time.sleep(3)

    def stop(self):
        for sig in (signal.SIGTERM, signal.SIGKILL):
            for p in self.procs:
                try:
                    os.killpg(p.pid, sig)
                except ProcessLookupError:
                    pass
            time.sleep(2)


# --------------------------------------------------------------------------- flight

class Flight:
    def __init__(self, url):
        self.m = mavutil.mavlink_connection(url, retries=30)
        self.t = 0.0            # simulated seconds since boot
        self.samples = []
        self.phase = "boot"
        self.texts = []

    def recv(self, timeout=2.0, types=None):
        msg = self.m.recv_match(type=types, blocking=True, timeout=timeout)
        if msg is None:
            return None
        if hasattr(msg, "time_boot_ms"):
            self.t = msg.time_boot_ms / 1000.0
        typ = msg.get_type()
        if typ == "STATUSTEXT":
            self.texts.append((round(self.t, 1), msg.text))
        elif typ == "VFR_HUD":
            pos = self.m.messages.get("GLOBAL_POSITION_INT")
            att = self.m.messages.get("ATTITUDE")
            if pos is not None and att is not None:
                self.samples.append(dict(
                    t=round(self.t, 2), phase=self.phase, mode=self.m.flightmode,
                    alt_rel=pos.relative_alt / 1000.0, lat=pos.lat / 1e7, lon=pos.lon / 1e7,
                    airspeed=msg.airspeed, groundspeed=msg.groundspeed,
                    throttle=msg.throttle, climb=msg.climb,
                    roll=math.degrees(att.roll), pitch=math.degrees(att.pitch)))
        return msg

    def run_for(self, sim_seconds, stop=None):
        # Sim time only advances while messages arrive, so also bound wall time.
        end, last_msg = self.t + sim_seconds, time.time()
        while self.t < end:
            if self.recv(1.0) is not None:
                last_msg = time.time()
            elif time.time() - last_msg > 30:
                raise RuntimeError("telemetry stopped (no messages for 30 s)")
            if stop is not None and stop():
                break

    def param(self, name):
        for _ in range(3):
            self.m.param_fetch_one(name)
            deadline = time.time() + 5
            while time.time() < deadline:
                p = self.recv(1.0, types=["PARAM_VALUE", "STATUSTEXT", "VFR_HUD",
                                          "GLOBAL_POSITION_INT", "ATTITUDE"])
                if p is not None and p.get_type() == "PARAM_VALUE" and p.param_id == name:
                    return p.param_value
        raise RuntimeError(f"could not read {name}")

    def set_param(self, name, value):
        self.m.param_set_send(name, float(value))
        got = self.param(name)
        if abs(got - float(value)) > 1e-3:
            raise RuntimeError(f"{name} reads back {got}, wanted {value}")

    def alt(self):
        pos = self.m.messages.get("GLOBAL_POSITION_INT")
        return pos.relative_alt / 1000.0 if pos else 0.0


def fly(url, overrides):
    f = Flight(url)
    if f.m.wait_heartbeat(timeout=60) is None:
        raise RuntimeError("no heartbeat")
    f.m.mav.request_data_stream_send(f.m.target_system, f.m.target_component,
                                     mavutil.mavlink.MAV_DATA_STREAM_ALL, 10, 1)
    # Ready = prearm healthy AND GPS 3D fix AND EKF has attitude, velocity and absolute
    # position. The prearm bit alone isn't enough: with ARMING_CHECK=0 it passes at once.
    ekf_needed = 1 | 2 | 4 | 16 | 32    # attitude, vel horiz/vert, pos horiz abs, pos vert abs
    ekf_bad = 128 | 1024                # constant-position mode, uninitialised
    deadline = time.time() + 180
    while True:
        f.recv(2.0, types=["SYS_STATUS", "STATUSTEXT", "VFR_HUD", "GLOBAL_POSITION_INT",
                           "ATTITUDE", "GPS_RAW_INT", "EKF_STATUS_REPORT"])
        sys_s, gps, ekf = (f.m.messages.get(n) for n in ("SYS_STATUS", "GPS_RAW_INT",
                                                          "EKF_STATUS_REPORT"))
        if (sys_s and sys_s.onboard_control_sensors_health
                & mavutil.mavlink.MAV_SYS_STATUS_PREARM_CHECK
                and gps and gps.fix_type >= 3
                and ekf and (ekf.flags & ekf_needed) == ekf_needed and not ekf.flags & ekf_bad):
            break
        if time.time() > deadline:
            raise RuntimeError("vehicle never became ready (prearm/GPS/EKF)")

    for name, value in {**COMMON_PARAMS, **overrides}.items():
        f.set_param(name, value)
    params = {}
    for n in REPORT_PARAMS:
        try:
            params[n] = f.param(n)
        except RuntimeError:
            params[n] = None    # not present on this vehicle; reported as "–"
    result = dict(params=params, events={})

    f.phase = "takeoff"
    f.m.set_mode("TAKEOFF")
    f.m.arducopter_arm()        # generic MAV_CMD_COMPONENT_ARM_DISARM despite the name
    f.m.motors_armed_wait()
    t0, target = f.t, 0.9 * params["TKOFF_ALT"]
    f.run_for(120.0, stop=lambda: f.alt() >= target)
    result["events"]["takeoff_s"] = f.t - t0 if f.alt() >= target else None

    if result["events"]["takeoff_s"] is not None:
        f.m.set_mode("LOITER")
        for phase, seconds in PHASES:
            f.phase = phase
            if phase == "glide":
                f.set_param("THR_MAX", 0)
                f.run_for(seconds, stop=lambda: f.alt() < GLIDE_FLOOR_M)
                f.set_param("THR_MAX", params["THR_MAX"])
            else:
                f.run_for(seconds)
        f.phase = "end"
        f.m.set_mode("RTL")
        f.run_for(3.0)
    result["samples"], result["texts"] = f.samples, f.texts
    return result


# --------------------------------------------------------------------------- metrics

def _mean(xs):
    return sum(xs) / len(xs) if xs else float("nan")


def _std(xs):
    if len(xs) < 2:
        return float("nan")
    mu = _mean(xs)
    return math.sqrt(sum((x - mu) ** 2 for x in xs) / (len(xs) - 1))


def _enu(rows):
    lat0, lon0 = rows[0]["lat"], rows[0]["lon"]
    k = math.cos(math.radians(lat0))
    return [((r["lon"] - lon0) * 111320.0 * k, (r["lat"] - lat0) * 110540.0) for r in rows]


def _circle_fit(xy):
    """Least-squares circle through points; returns (cx, cy, r). Robust to partial laps."""
    import numpy as np
    x = np.array([p[0] for p in xy])
    y = np.array([p[1] for p in xy])
    A = np.c_[2 * x, 2 * y, np.ones_like(x)]
    cx, cy, c = np.linalg.lstsq(A, x ** 2 + y ** 2, rcond=None)[0]
    return float(cx), float(cy), float(math.sqrt(c + cx ** 2 + cy ** 2))


def metrics(result):
    s = result["samples"]
    m = {"takeoff_s": result["events"].get("takeoff_s")}
    tk = [r for r in s if r["phase"] == "takeoff"]
    m["takeoff_max_climb_mps"] = max((r["climb"] for r in tk), default=float("nan"))

    lo = [r for r in s if r["phase"] == "loiter"]
    m["loiter_airspeed_mps"] = _mean([r["airspeed"] for r in lo])
    m["loiter_airspeed_std"] = _std([r["airspeed"] for r in lo])
    m["loiter_groundspeed_mps"] = _mean([r["groundspeed"] for r in lo])
    m["loiter_throttle_pct"] = _mean([r["throttle"] for r in lo])
    m["loiter_alt_std_m"] = _std([r["alt_rel"] for r in lo])
    m["loiter_bank_deg"] = _mean([abs(r["roll"]) for r in lo])
    if len(lo) > 10:
        m["loiter_radius_m"] = _circle_fit(_enu(lo))[2]
        # Radius a coordinated turn would have at this speed and bank: r = v^2 / (g tan(bank)).
        # A measured radius well above it means the turn isn't coordinated (e.g. sideslip).
        tan_bank = math.tan(math.radians(m["loiter_bank_deg"]))
        m["loiter_radius_from_bank_m"] = (m["loiter_groundspeed_mps"] ** 2 / (9.81 * tan_bank)
                                          if tan_bank > 0.05 else float("nan"))
    else:
        m["loiter_radius_m"] = m["loiter_radius_from_bank_m"] = float("nan")

    gl_all = [r for r in s if r["phase"] == "glide"]
    gl = [r for r in gl_all if gl_all and r["t"] >= gl_all[0]["t"] + GLIDE_SKIP_S]
    m["glide_scored_s"] = gl[-1]["t"] - gl[0]["t"] if len(gl) > 1 else 0.0
    if len(gl) > 10:
        xy = _enu(gl)
        path = sum(math.hypot(x2 - x1, y2 - y1) for (x1, y1), (x2, y2) in zip(xy, xy[1:]))
        lost = gl[0]["alt_rel"] - gl[-1]["alt_rel"]
        dt = gl[-1]["t"] - gl[0]["t"]
        m["glide_sink_mps"] = lost / dt if dt > 0 else float("nan")
        m["glide_airspeed_mps"] = _mean([r["airspeed"] for r in gl])
        m["glide_ratio"] = path / lost if lost > 0.5 else float("nan")
    else:
        m["glide_sink_mps"] = m["glide_airspeed_mps"] = m["glide_ratio"] = float("nan")
    return m


# --------------------------------------------------------------------------- report

METRIC_COLUMNS = [
    ("takeoff_s", "Takeoff to 90% alt (s)"),
    ("takeoff_max_climb_mps", "Max climb (m/s)"),
    ("loiter_airspeed_mps", "Loiter airspeed (m/s)"),
    ("loiter_airspeed_std", "Airspeed std (m/s)"),
    ("loiter_groundspeed_mps", "Loiter groundspeed (m/s)"),
    ("loiter_throttle_pct", "Loiter throttle (%)"),
    ("loiter_alt_std_m", "Alt hold std (m)"),
    ("loiter_bank_deg", "Mean bank (deg)"),
    ("loiter_radius_m", "Loiter radius, measured (m)"),
    ("loiter_radius_from_bank_m", "Radius implied by bank (m)"),
    ("glide_scored_s", "Glide time scored (s)"),
    ("glide_sink_mps", "Glide sink (m/s)"),
    ("glide_airspeed_mps", "Glide airspeed (m/s)"),
    ("glide_ratio", "Glide ratio"),
]


def fmt(v):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return "–"
    return f"{v:.1f}" if isinstance(v, float) else str(v)


def write_report(outdir, rows, overrides):
    with open(outdir / "summary.csv", "w", newline="") as fh:
        keys = ["model", "engine", "status"] + [k for k, _ in METRIC_COLUMNS] + REPORT_PARAMS
        w = csv.DictWriter(fh, fieldnames=keys)
        w.writeheader()
        for r in rows:
            w.writerow({"model": r["model"], "engine": r["engine"], "status": r["status"],
                        **r.get("metrics", {}), **r.get("params", {})})

    lines = [f"# Fixed-wing comparison — {outdir.name}", ""]
    lines.append("Same flight profile for every model. Parameters forced on all models: "
                 + ", ".join(f"`{k}={v}`" for k, v in {**COMMON_PARAMS, **overrides}.items()) + ".")
    lines.append("Everything else is each frame's stock defaults (see the parameter table).")
    lines.append("")
    for engine in ("sitl",):
        group = [r for r in rows if r["engine"] == engine]
        if not group:
            continue
        lines += [f"## Engine: {engine}", "",
                  "| Metric | " + " | ".join(r["model"] for r in group) + " |",
                  "|---|" + "---|" * len(group)]
        lines.append("| Status | " + " | ".join(r["status"] for r in group) + " |")
        for key, label in METRIC_COLUMNS:
            lines.append(f"| {label} | " + " | ".join(fmt(r.get("metrics", {}).get(key))
                                                      for r in group) + " |")
        lines += ["", "| Parameter | " + " | ".join(r["model"] for r in group) + " |",
                  "|---|" + "---|" * len(group)]
        for p in REPORT_PARAMS:
            vals = [r.get("params", {}).get(p) for r in group]
            mark = " ⚠️ differs" if len({v for v in vals if v is not None}) > 1 else ""
            lines.append(f"| `{p}`{mark} | " + " | ".join(fmt(v) for v in vals) + " |")
        lines.append("")
    (outdir / "summary.md").write_text("\n".join(lines) + "\n")


def plot(outdir, rows):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    ok = [r for r in rows if r.get("samples")]
    fig, axes = plt.subplots(3, 1, figsize=(11, 10), sharex=True)
    for r in ok:
        t0 = next((x["t"] for x in r["samples"] if x["phase"] == "takeoff"), r["samples"][0]["t"])
        # Start just before takeoff: boot-time sensor transients aren't part of the profile.
        s = [x for x in r["samples"] if x["t"] >= t0 - 3.0]
        style = "-"
        label = f'{r["model"]} [{r["engine"]}]'
        ts = [x["t"] - t0 for x in s]
        axes[0].plot(ts, [x["alt_rel"] for x in s], style, label=label)
        axes[1].plot(ts, [x["airspeed"] for x in s], style, label=label)
        axes[2].plot(ts, [x["throttle"] for x in s], style, label=label)
    for ax, ylabel in zip(axes, ["Altitude above home (m)", "Airspeed (m/s)", "Throttle (%)"]):
        ax.set_ylabel(ylabel)
        ax.grid(alpha=0.3)
    axes[-1].set_xlabel("Simulated time since takeoff command (s)")
    axes[0].legend(loc="best", fontsize=8)
    fig.suptitle("Fixed-wing comparison: same profile (takeoff → loiter → power-off glide)")
    fig.tight_layout()
    fig.savefig(outdir / "timeseries.png", dpi=110)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(8, 8))
    for r in ok:
        lo = [x for x in r["samples"] if x["phase"] == "loiter"]
        if lo:
            xy = _enu(lo)
            cx, cy, _ = _circle_fit(xy) if len(xy) > 10 else (0.0, 0.0, 0.0)
            ax.plot([x - cx for x, _ in xy], [y - cy for _, y in xy],
                    "-", label=f'{r["model"]} [{r["engine"]}]')
    ax.set_aspect("equal")
    ax.set_xlabel("East (m, centred)")
    ax.set_ylabel("North (m, centred)")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=8)
    ax.set_title("Loiter ground tracks (60 s)")
    fig.tight_layout()
    fig.savefig(outdir / "loiter_tracks.png", dpi=110)
    plt.close(fig)


# --------------------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--models", default=",".join(MODELS), help="comma list from: " + ", ".join(MODELS))
    ap.add_argument("--speedup", type=float, default=5.0)
    ap.add_argument("--param", action="append", default=[], metavar="NAME=VALUE",
                    help="force a parameter on every model (repeatable)")
    ap.add_argument("--out", type=Path, default=ROOT / "compare/results")
    args = ap.parse_args()

    names = [n.strip() for n in args.models.split(",") if n.strip()]
    unknown = [n for n in names if n not in MODELS]
    if unknown:
        sys.exit(f"unknown model(s): {unknown}; choose from {list(MODELS)}")
    overrides = {}
    for p in args.param:
        k, _, v = p.partition("=")
        overrides[k.strip()] = float(v)

    outdir = args.out / datetime.now().strftime("%Y%m%d-%H%M%S")
    outdir.mkdir(parents=True)
    rows = []
    for name in names:
        cfg = MODELS[name]
        busy = ports_busy()
        if busy:
            sys.exit(f"port {busy} is in use (another SITL running?); stop it first")
        rundir = outdir / name
        rundir.mkdir()
        print(f"=== {name} ({cfg['engine']}) ...", flush=True)
        run = Run(name, cfg, rundir, args.speedup)
        row = dict(model=name, engine=cfg["engine"])
        t_wall = time.time()
        try:
            run.start()
            res = fly("tcp:127.0.0.1:5760", overrides)
            row.update(params=res["params"], samples=res["samples"], metrics=metrics(res))
            row["status"] = "ok" if res["events"]["takeoff_s"] is not None else "no takeoff"
            (rundir / "statustext.txt").write_text("".join(f"{t:8.1f}  {x}\n" for t, x in res["texts"]))
        except Exception as e:      # keep going with the other models
            row["status"] = f"error: {e}"
        finally:
            run.stop()
        if row.get("samples"):
            with open(rundir / "samples.csv", "w", newline="") as fh:
                w = csv.DictWriter(fh, fieldnames=list(row["samples"][0]))
                w.writeheader()
                w.writerows(row["samples"])
        print(f"    {row['status']}  ({time.time() - t_wall:.0f} s wall)", flush=True)
        rows.append(row)

    write_report(outdir, rows, overrides)
    plot(outdir, rows)
    print(f"\nResults: {outdir}")
    print((outdir / "summary.md").read_text())
    return 0 if all(r["status"] == "ok" for r in rows) else 1


if __name__ == "__main__":
    sys.exit(main())
