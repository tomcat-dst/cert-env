#!/usr/bin/env python3
"""
Health and consistency check for an ArduPlane SITL dataflash log: messages, scheduler, EKF,
estimate vs SITL truth, sensors, flight envelope, control saturation and roll/pitch ringing.

  compare/log_health.py compare/results/<run>/<model>/logs/00000001.BIN

Writes health.md into the run folder. Phases follow log_tuning.py (takeoff, climb, cruise, rtl).
Each check prints its value and a short verdict: ok / NOTE / WARN. Thresholds are rules of thumb,
stated next to each check.
"""
import sys
from pathlib import Path

import numpy as np
from pymavlink import DFReader

sys.path.insert(0, str(Path(__file__).resolve().parent))
import log_tuning as lt  # noqa: E402

FIELDS = {
    "PM": ["NLon", "NL", "MaxT", "Load"],
    "XKF4": ["C", "SV", "SP", "SH", "SM", "SVT", "errRP", "FS", "TS", "SS"],
    "VIBE": ["IMU", "VibeX", "VibeY", "VibeZ", "Clip"],
    "ARSP": ["I", "Airspeed", "H"],
    "SIM": ["Roll", "Pitch", "Yaw", "Alt"],
    "SIM2": ["As"],
    "ATT": ["Roll", "Pitch", "Yaw", "DesRoll", "DesPitch"],
    "AETR": ["Ail", "Elev", "Thr", "Rudd"],
    "CTUN": ["As", "ThO"],
    "AOA": ["AOA", "SSA"],
    "GPS": ["I", "Status", "NSats", "HDop"],
    "MAG": ["I", "Health"],
    "BARO": ["I", "H"],
    "BAT": ["Inst", "Volt", "Curr", "H"],
    "TECS": ["h", "hdem", "sp", "spdem"],
    "PIDR": ["Tar", "Act"],
    "PIDP": ["Tar", "Act"],
    "XKF2": ["C", "VWN", "VWE"],
}
WIND = ("SIM_WIND_SPD", "SIM_WIND_DIR", "SIM_WIND_TURB")
PARAMS = ("SCHED_LOOP_RATE", "AIRSPEED_MIN", "AIRSPEED_MAX", "AIRSPEED_CRUISE", "ROLL_LIMIT_DEG",
          "PTCH_LIM_MAX_DEG", "PTCH_LIM_MIN_DEG")


def load(path):
    r = DFReader.DFReader_binary(str(path), zero_time_base=False)
    raw = {k: [] for k in FIELDS}
    msgs, modes, params, errs, evs = [], [], {}, [], []
    wind = {k: [] for k in WIND}
    want = list(FIELDS) + ["MSG", "MODE", "PARM", "ERR", "EV"]
    while True:
        m = r.recv_match(type=want)
        if m is None:
            break
        t = m.get_type()
        ts = m.TimeUS / 1e6
        if t == "MSG":
            msgs.append((ts, m.Message))
        elif t == "MODE":
            modes.append((ts, int(m.ModeNum)))
        elif t == "PARM":
            if m.Name in PARAMS:
                params[m.Name] = m.Value
            if m.Name in WIND:
                wind[m.Name].append((ts, m.Value))
        elif t == "ERR":
            errs.append((ts, m.Subsys, m.ECode))
        elif t == "EV":
            evs.append((ts, m.Id))
        else:
            raw[t].append([ts] + [getattr(m, f) for f in FIELDS[t]])
    data = {k: dict(zip(["t"] + FIELDS[k], np.array(v, float).T)) for k, v in raw.items() if v}
    data["wind"] = wind
    return data, modes, msgs, params, errs, evs


def wrap180(x):
    return (x + 180) % 360 - 180


def ringing(att, des_key, act_key, span, min_step=8.0, window=6.0, band=1.5):
    """Each demand step > min_step deg inside span: overshoot past the new demand, number of
    error sign changes with |error| > band within `window` s (or until the demand moves > 5 deg),
    and the ratio of the 2nd to the 1st error peak (decay; < 0.3 well damped, > 0.6 ringing)."""
    a = lt.cut(att, span)
    jumps = np.where(np.abs(np.diff(a[des_key])) > min_step)[0]
    out, last = [], -1e9
    for i in jumps:
        t0 = a["t"][i + 1]
        if t0 - last < 2.0:
            continue
        last = t0
        r0, r1 = a[act_key][i], a[des_key][i + 1]
        w = lt.cut(a, (t0, t0 + window))
        moved = np.abs(w[des_key] - r1) > 5
        t_end = w["t"][np.argmax(moved)] if np.any(moved) else t0 + window
        w = lt.cut(a, (t0, t_end))
        if len(w["t"]) < 10:
            continue
        e = w[act_key] - w[des_key]
        sgn = np.sign(r1 - r0)
        overshoot = float(np.max(e * sgn))
        big = e[np.abs(e) > band]
        flips = int(np.sum(np.sign(big[1:]) != np.sign(big[:-1]))) if len(big) > 1 else 0
        # successive extrema of the error after the first zero crossing
        zc = np.where(np.diff(np.sign(e)) != 0)[0]
        peaks = [float(np.max(np.abs(e[a_:b_ + 1]))) for a_, b_ in zip(zc[:-1], zc[1:]) if b_ > a_]
        decay = peaks[1] / peaks[0] if len(peaks) >= 2 and peaks[0] > band else float("nan")
        out.append(dict(t=t0, step=f"{r0:+.0f}->{r1:+.0f}", win=t_end - t0, over=overshoot,
                        flips=flips, decay=decay, peaks=[round(p, 1) for p in peaks[:4]]))
    return out


def dominant(x, fs, fmin=0.2, fmax=5.0):
    f, p = lt.welch(x, fs, min(len(x), 1024))
    sel = (f >= fmin) & (f <= fmax)
    i = np.argmax(p[sel])
    return float(f[sel][i]), float(np.sqrt(p[sel][i] * (f[1] - f[0])))


def main():
    path = Path(sys.argv[1])
    data, modes, msgs, prm, errs, evs = load(path)
    ph = lt.phases({"TECS": data["TECS"]}, modes)
    # airborne: 1 s after SITL truth altitude first exceeds 0.5 m (the SITL launcher pushes the
    # aircraft along the ground, so the ground run is excluded from in-flight checks)
    sim0 = data["SIM"]
    t_air = sim0["t"][np.argmax(sim0["Alt"] - sim0["Alt"][0] > 0.5)] + 1.0
    t_end = ph["rtl"][1] if "rtl" in ph else data["ATT"]["t"][-1]
    L, add = [], None
    L.append(f"# Log health: {path.parent.parent.parent.name}/{path.parent.parent.name}\n")
    L.append("Phases: " + ", ".join(f"{k} {v[0]:.0f}-{v[1]:.0f} s" for k, v in ph.items())
             + f"; airborne checks from {t_air:.1f} s (liftoff + 1 s)")
    L.append("Parameters: " + ", ".join(f"{k} {v:g}" for k, v in prm.items()) + "\n")
    rows = []

    def chk(area, item, value, verdict):
        rows.append(f"| {area} | {item} | {value} | {verdict} |")

    # messages
    warn_words = ("fail", "error", "bad", "lost", "unhealthy", "stall", "glitch", "reset", "variance",
                  "timeout", "crash", "low", "critical")
    flagged = [(t, m) for t, m in msgs if any(w in m.lower() for w in warn_words)]
    chk("Messages", f"{len(msgs)} MSG lines", "; ".join(f"{t:.0f}s {m}" for t, m in flagged) or "none flagged",
        "WARN" if flagged else "ok")
    chk("Messages", "ERR / EV entries", f"{len(errs)} / {len(evs)}",
        "WARN" if errs else "ok")
    chk("Modes", "sequence", " -> ".join(f"{n}@{t:.0f}s" for t, n in modes),
        "ok" if [n for _, n in modes] == [13, 15, 11] else "NOTE")

    # scheduler
    pm = data["PM"]
    period_us = 1e6 / prm.get("SCHED_LOOP_RATE", 50)
    chk("Scheduler", "long loops NLon (sum) / max loop time",
        f"{int(pm['NLon'].sum())} / {pm['MaxT'].max():.0f} us (period {period_us:.0f} us)",
        "NOTE" if pm["MaxT"].max() > 1.5 * period_us else "ok")

    # EKF
    xk = data["XKF4"]
    worst = {k: float(np.max(xk[k])) for k in ("SV", "SP", "SH", "SM", "SVT")}
    chk("EKF", "max innovation test ratios (>0.5 note, >1 rejected)",
        ", ".join(f"{k} {v:.2f}" for k, v in worst.items()),
        "WARN" if max(worst.values()) > 1 else "NOTE" if max(worst.values()) > 0.5 else "ok")
    # TS bit 5 (drag fusion timeout) is always set when EK3_DRAG_BCOEF_X/Y are 0, i.e. drag
    # fusion is off; bits 0-4 are position, velocity, height, compass and airspeed timeouts.
    xa = lt.cut(xk, (t_air, t_end))
    ts = xa["TS"].astype(int) & 0x1F
    chk("EKF", "fault flags / timeouts excl. drag (airborne samples)",
        f"FS {int(np.sum(xa['FS'] != 0))}, TS {int(np.sum(ts != 0))} (drag-timeout bit set in "
        f"{int(np.sum(xa['TS'].astype(int) & 0x20 != 0))}: drag fusion off)",
        "WARN" if np.any(xa["FS"] != 0) or np.any(ts != 0) else "ok")

    # estimate vs truth
    att, sim = data["ATT"], data["SIM"]
    span = (t_air, t_end)
    a, s = lt.cut(att, span), lt.cut(sim, span)
    for k in ("Roll", "Pitch", "Yaw"):
        st = np.interp(a["t"], s["t"], np.unwrap(np.radians(s[k])) if k == "Yaw" else s[k])
        est = np.unwrap(np.radians(a[k])) if k == "Yaw" else a[k]
        d = np.degrees(est - st) if k == "Yaw" else est - st
        if k == "Yaw":
            d = wrap180(d)
        chk("Estimate vs truth", f"{k} AHRS - SITL (mean / max abs)", f"{np.mean(d):+.2f} / {np.max(np.abs(d)):.2f} deg",
            "WARN" if np.max(np.abs(d)) > 5 else "NOTE" if np.max(np.abs(d)) > 2 else "ok")
    ar, s2 = lt.cut(data["ARSP"], span), lt.cut(data["SIM2"], span)
    ar = {k: v[ar["I"] == 0] for k, v in ar.items()}
    tru = np.interp(ar["t"], s2["t"], s2["As"])
    d = ar["Airspeed"] - tru
    # SIM2.As is the pitot EAS. ArduPilot 4.7.3's sitl_airspeed.cpp divides it by EAS2TAS again
    # (fixed on master), so a mean offset of about EAS*(1/EAS2TAS - 1) is that SITL bug, not a sensor fault.
    alt = np.interp(ar["t"], lt.cut(sim, span)["t"], lt.cut(sim, span)["Alt"])
    e2t = np.sqrt(1.0 / ((288.15 - 0.0065 * alt) / 288.15) ** 4.2559)
    expected = tru / e2t - tru
    chk("Estimate vs truth", "airspeed sensor - SITL pitot EAS (mean / max abs; 4.7.3 double-EAS predicts)",
        f"{np.mean(d):+.2f} / {np.max(np.abs(d)):.2f} m/s ({np.mean(expected):+.2f})",
        "NOTE" if abs(np.mean(d)) > 0.2 else "ok")

    # sensors
    vib = lt.cut(data["VIBE"], span)
    chk("Sensors", "vibration max X/Y/Z (m/s^2), clip increase",
        f"{vib['VibeX'].max():.2f}/{vib['VibeY'].max():.2f}/{vib['VibeZ'].max():.2f}, "
        f"{int(vib['Clip'].max() - vib['Clip'].min())}", "NOTE" if vib["VibeZ"].max() > 30 else "ok")
    gps = lt.cut(data["GPS"], span)
    chk("Sensors", "GPS status min / sats min / HDop max",
        f"{gps['Status'].min():.0f} / {gps['NSats'].min():.0f} / {gps['HDop'].max():.2f}",
        "WARN" if gps["Status"].min() < 3 else "ok")
    unhealthy = {n: int(np.sum(lt.cut(data[n], span)[k] == 0))
                 for n, k in (("ARSP", "H"), ("MAG", "Health"), ("BARO", "H"))}
    chk("Sensors", "unhealthy samples (airspeed, compass, baro)",
        ", ".join(f"{k} {v}" for k, v in unhealthy.items()), "WARN" if any(unhealthy.values()) else "ok")

    # envelope (airborne, takeoff ground run excluded)
    ct, ao = lt.cut(data["CTUN"], span), lt.cut(data["AOA"], span)
    amin = prm.get("AIRSPEED_MIN", 0)
    chk("Envelope", f"min airspeed (AIRSPEED_MIN {amin:g})",
        f"{ct['As'].min():.1f} m/s at {ct['t'][np.argmin(ct['As'])]:.0f} s",
        "WARN" if ct["As"].min() < amin - 0.5 else "ok")
    chk("Envelope", f"max airspeed (AIRSPEED_MAX {prm.get('AIRSPEED_MAX', 0):g})",
        f"{ct['As'].max():.1f} m/s", "NOTE" if ct["As"].max() > prm.get("AIRSPEED_MAX", 99) else "ok")
    chk("Envelope", "angle of attack max / sideslip max abs",
        f"{ao['AOA'].max():.1f} / {np.max(np.abs(ao['SSA'])):.1f} deg",
        "NOTE" if ao["AOA"].max() > 10 else "ok")
    rl = prm.get("ROLL_LIMIT_DEG", 65)
    over = a["Roll"][np.abs(a["Roll"]) > rl + 3]
    chk("Envelope", f"roll beyond ROLL_LIMIT_DEG {rl:g} + 3", f"{len(over)} samples, max {np.max(np.abs(a['Roll'])):.1f} deg",
        "WARN" if len(over) else "ok")
    pmax, pmin = prm.get("PTCH_LIM_MAX_DEG", 25), prm.get("PTCH_LIM_MIN_DEG", -20)
    chk("Envelope", f"pitch range (limits {pmin:g}/{pmax:g})", f"{a['Pitch'].min():.1f} / {a['Pitch'].max():.1f} deg",
        "NOTE" if a["Pitch"].max() > pmax + 3 or a["Pitch"].min() < pmin - 3 else "ok")
    te = lt.cut(data["TECS"], (ph["cruise"][0], ph["cruise"][1]))
    chk("Envelope", "cruise height / speed error max", f"{np.max(np.abs(te['h'] - te['hdem'])):.1f} m / "
        f"{np.max(np.abs(te['sp'] - te['spdem'])):.1f} m/s", "ok")

    # saturation (airborne)
    ae = lt.cut(data["AETR"], span)
    dt = np.median(np.diff(ae["t"]))
    for k, lim in (("Ail", 4400), ("Elev", 4400), ("Rudd", 4400), ("Thr", 99)):
        sat = np.abs(ae[k]) >= lim
        chk("Saturation", f"{k} at limit (airborne)", f"{sat.sum() * dt:.1f} s, max {np.max(np.abs(ae[k])) / (45 if k != 'Thr' else 1):.0f}%",
            "NOTE" if sat.sum() * dt > 1 else "ok")

    # wind and disturbance response in cruise
    w = data["wind"]
    spd = [v for t, v in w["SIM_WIND_SPD"] if t > 1.0]
    dirs = [v for t, v in w["SIM_WIND_DIR"] if t > 1.0]
    turb = [v for _, v in w["SIM_WIND_TURB"]]
    chk("Wind", "SIM_WIND_SPD changes / range, direction range, turbulence",
        f"{len(spd)} / {min(spd):.1f}-{max(spd):.1f} m/s, {min(dirs):.0f}-{max(dirs):.0f} deg, TURB {turb[-1]:g}"
        if spd else f"steady: SPD {prm.get('SIM_WIND_SPD', 0):g}, TURB {turb[-1] if turb else 0:g}", "ok")
    xk2 = lt.cut(data["XKF2"], ph["cruise"])
    xk2 = {k: v[xk2["C"] == 0] for k, v in xk2.items()}
    ws = np.hypot(xk2["VWN"], xk2["VWE"])
    wfrom = (np.degrees(np.arctan2(-np.mean(xk2["VWE"]), -np.mean(xk2["VWN"]))) + 360) % 360
    chk("Wind", "EKF wind estimate in cruise (mean / min / max, mean from)",
        f"{ws.mean():.1f} / {ws.min():.1f} / {ws.max():.1f} m/s, from {wfrom:.0f} deg", "ok")
    cr_att, cr_ae = lt.cut(att, ph["cruise"]), lt.cut(data["AETR"], ph["cruise"])
    chk("Disturbance", "cruise roll / pitch error std and max",
        f"{np.std(cr_att['DesRoll'] - cr_att['Roll']):.2f} / {np.std(cr_att['DesPitch'] - cr_att['Pitch']):.2f} deg, "
        f"max {np.max(np.abs(cr_att['DesRoll'] - cr_att['Roll'])):.1f} / {np.max(np.abs(cr_att['DesPitch'] - cr_att['Pitch'])):.1f} deg",
        "NOTE" if np.max(np.abs(cr_att["DesRoll"] - cr_att["Roll"])) > 5 else "ok")
    chk("Disturbance", "cruise aileron / elevator RMS and max",
        f"{np.sqrt(np.mean(cr_ae['Ail'] ** 2)) / 45:.1f} / {np.sqrt(np.mean(cr_ae['Elev'] ** 2)) / 45:.1f} %, "
        f"max {np.max(np.abs(cr_ae['Ail'])) / 45:.0f} / {np.max(np.abs(cr_ae['Elev'])) / 45:.0f} %", "ok")
    chk("Disturbance", "cruise airspeed / height error std",
        f"{np.std(te['sp'] - te['spdem']):.2f} m/s / {np.std(te['h'] - te['hdem']):.2f} m", "ok")
    ct_c = lt.cut(data["CTUN"], ph["cruise"])
    chk("Disturbance", "cruise airspeed min / max, throttle max",
        f"{ct_c['As'].min():.1f} / {ct_c['As'].max():.1f} m/s, {ct_c['ThO'].max():.0f} %",
        "WARN" if ct_c["As"].min() < amin else "ok")

    # ringing
    att_air = lt.cut(att, (t_air, t_end))
    for axis, dk, ak in (("roll", "DesRoll", "Roll"), ("pitch", "DesPitch", "Pitch")):
        steps = ringing(att_air, dk, ak, (t_air, t_end), min_step=8.0 if axis == "roll" else 4.0)
        if not steps:
            chk("Ringing", f"{axis} steps", "no demand steps", "ok")
        for s_ in steps:
            verdict = "WARN" if s_["flips"] >= 4 or (s_["decay"] == s_["decay"] and s_["decay"] > 0.6) else \
                      "NOTE" if s_["flips"] >= 2 or s_["over"] > 5 else "ok"
            chk("Ringing", f"{axis} step {s_['step']} at {s_['t']:.0f} s ({s_['win']:.1f} s window)",
                f"overshoot {s_['over']:.1f} deg, {s_['flips']} sign changes, peaks {s_['peaks']}, "
                f"decay {s_['decay']:.2f}", verdict)
    # lateral-directional: sideslip oscillation in climb + cruise
    so = lt.cut(data["AOA"], (t_air, ph["cruise"][1]))
    f, amp = dominant(so["SSA"], lt.fs_of(so))
    chk("Ringing", "sideslip dominant oscillation (Dutch roll check)", f"{f:.2f} Hz, {amp:.3f} deg RMS", "ok" if amp < 0.5 else "NOTE")

    L += ["| Area | Check | Value | Verdict |", "|---|---|---|---|"] + rows
    text = "\n".join(L) + "\n"
    (path.parent.parent / "health.md").write_text(text)
    print(text)


if __name__ == "__main__":
    main()
