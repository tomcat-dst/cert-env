#!/usr/bin/env python3
"""
Control-loop health check for an ArduPlane dataflash log: tracking error, controller term
balance, servo usage and oscillation spectra, split by flight phase.

  compare/log_tuning.py compare/results/endurance-*/believer-5kg/logs/00000001.BIN [--out DIR]

Phases: takeoff (TAKEOFF mode), climb (GUIDED until within 5 m of the demanded height),
cruise (the rest of GUIDED, first 60 s dropped), rtl. Spectra are Welch averages over cruise.
Writes tuning.md and tuning.png into the run folder (or into --out).
"""
import argparse
import sys
from pathlib import Path

import numpy as np

from pymavlink import DFReader

MODES = {13: "takeoff", 15: "guided", 11: "rtl"}
WANT = ["PIDR", "PIDP", "ATT", "AETR", "TECS", "CTUN", "NTUN", "IMU", "MODE", "PARM"]
PARAMS = ("SIM_WIND_SPD", "SIM_WIND_DIR", "SIM_WIND_TURB", "RLL_RATE_P", "RLL_RATE_I", "RLL_RATE_D",
          "RLL_RATE_FF", "PTCH_RATE_P", "PTCH_RATE_I", "PTCH_RATE_D", "PTCH_RATE_FF")
FIELDS = {
    "PIDR": ["Tar", "Act", "Err", "P", "I", "D", "FF"],
    "PIDP": ["Tar", "Act", "Err", "P", "I", "D", "FF"],
    "ATT": ["DesRoll", "Roll", "DesPitch", "Pitch"],
    "AETR": ["Ail", "Elev", "Thr"],
    "TECS": ["h", "hdem", "sp", "spdem", "th", "ph"],
    "CTUN": ["ThO", "As"],
    "NTUN": ["XT"],
    "IMU": ["GyrX", "GyrY", "GyrZ"],
}


def load(path):
    r = DFReader.DFReader_binary(str(path), zero_time_base=False)
    raw = {k: [] for k in FIELDS}
    modes = []
    params = {}
    while True:
        m = r.recv_match(type=WANT)
        if m is None:
            break
        t = m.get_type()
        if t == "PARM":
            if m.Name in PARAMS:
                params[m.Name] = m.Value    # last value wins: runtime changes override defaults
        elif t == "MODE":
            modes.append((m.TimeUS / 1e6, int(m.ModeNum)))
        elif t == "IMU" and m.I != 0:
            continue
        else:
            raw[t].append([m.TimeUS / 1e6] + [getattr(m, f) for f in FIELDS[t]])
    data = {k: dict(zip(["t"] + FIELDS[k], np.array(v).T)) for k, v in raw.items() if v}
    data["params"] = params
    return data, modes


def phases(data, modes):
    """Return {phase: (t0, t1)} from mode changes and TECS height error."""
    ends = [t for t, _ in modes[1:]] + [data["TECS"]["t"][-1]]
    spans = {MODES.get(n, f"mode{n}"): (t, e) for (t, n), e in zip(modes, ends)}
    out = {}
    if "takeoff" in spans:
        out["takeoff"] = spans["takeoff"]
    if "guided" in spans:
        g0, g1 = spans["guided"]
        te = data["TECS"]
        sel = (te["t"] > g0) & (te["t"] < g1)
        hdem_final = np.median(te["hdem"][sel][-1000:])
        reached = te["t"][sel][np.argmax(np.abs(te["h"][sel] - hdem_final) < 5.0)]
        out["climb"] = (g0, reached)
        out["cruise"] = (reached + 60.0, g1)
    if "rtl" in spans:
        out["rtl"] = spans["rtl"]
    return out


def cut(d, span):
    s = (d["t"] >= span[0]) & (d["t"] < span[1])
    return {k: v[s] for k, v in d.items()}


def rms(x):
    return float(np.sqrt(np.mean(np.square(x)))) if len(x) else float("nan")


def hp_std(d, x, window=60.0):
    """Std of x after removing its moving mean over `window` s: fast variation without slow drift."""
    n = max(1, int(round(window * fs_of(d))))
    if len(x) <= n:
        return float(np.std(x))
    c = np.cumsum(np.insert(np.asarray(x, float), 0, 0.0))
    mean = (c[n:] - c[:-n]) / n
    return float(np.std(np.asarray(x, float)[n // 2:n // 2 + len(mean)] - mean))


def welch(x, fs, nperseg):
    """Mean-removed Hann-windowed Welch PSD (one-sided); returns f, psd."""
    x = np.asarray(x, float) - np.mean(x)
    nperseg = min(nperseg, len(x))
    step = nperseg // 2
    win = np.hanning(nperseg)
    scale = fs * np.sum(win ** 2)
    segs = [x[i:i + nperseg] for i in range(0, len(x) - nperseg + 1, step)]
    p = np.mean([np.abs(np.fft.rfft((s - s.mean()) * win)) ** 2 for s in segs], axis=0) / scale
    p[1:-1] *= 2
    return np.fft.rfftfreq(nperseg, 1 / fs), p


def peaks(f, p, fmin, n=3):
    """Largest local maxima above fmin, with the RMS amplitude in a +-2-bin band."""
    df = f[1] - f[0]
    idx = [i for i in range(2, len(p) - 2) if f[i] >= fmin and p[i] == p[i - 2:i + 3].max()]
    idx = sorted(idx, key=lambda i: -p[i])[:n]
    return [(f[i], float(np.sqrt(np.sum(p[i - 2:i + 3]) * df))) for i in idx]


def fs_of(d):
    return 1.0 / np.median(np.diff(d["t"]))


def analyse(data, ph):
    lines = []
    add = lines.append
    add("## Tracking by phase\n")
    add("| Phase | Dur, s | Roll err RMS / max, deg | Pitch err RMS / max, deg | "
        "Roll-rate err RMS, deg/s | Pitch-rate err RMS, deg/s | Ail RMS / max, % | Elev RMS / max, % |")
    add("|---|---|---|---|---|---|---|---|")
    for name, span in ph.items():
        a, r, p, s = (cut(data[k], span) for k in ("ATT", "PIDR", "PIDP", "AETR"))
        er, ep = a["DesRoll"] - a["Roll"], a["DesPitch"] - a["Pitch"]
        add(f"| {name} | {span[1] - span[0]:.0f} | {rms(er):.2f} / {np.max(np.abs(er)):.1f} | "
            f"{rms(ep):.2f} / {np.max(np.abs(ep)):.1f} | {rms(r['Err']):.2f} | {rms(p['Err']):.2f} | "
            f"{rms(s['Ail']) / 45:.1f} / {np.max(np.abs(s['Ail'])) / 45:.0f} | "
            f"{rms(s['Elev']) / 45:.1f} / {np.max(np.abs(s['Elev'])) / 45:.0f} |")

    add("\n## Largest roll command step after takeoff\n")
    a = cut(data["ATT"], (ph["climb"][0], ph["cruise"][1]))
    jumps = np.abs(np.diff(a["DesRoll"]))
    i = int(np.argmax(jumps))
    t0, r0, r1 = a["t"][i + 1], a["Roll"][i], a["DesRoll"][i + 1]
    step = r1 - r0
    # window: until the demand moves more than 5 deg from the step target (max 8 s)
    w = cut(a, (t0, t0 + 8))
    moved = np.abs(w["DesRoll"] - r1) > 5
    t_end = w["t"][np.argmax(moved)] if np.any(moved) else t0 + 8
    w = cut(a, (t0, t_end))
    prog = (w["Roll"] - r0) / step
    t90 = w["t"][np.argmax(prog >= 0.9)] - t0 if np.any(prog >= 0.9) else float("nan")
    over = float(np.max((w["Roll"] - w["DesRoll"]) * np.sign(step)))
    late = cut(a, (t0 + 2, t_end))
    hold = f"{np.mean(late['DesRoll'] - late['Roll']):+.1f} deg" if len(late["t"]) else "n/a"
    add("| Step | Window | Time to 90% | Max overshoot past demand | Mean error from 2 s to window end |")
    add("|---|---|---|---|---|")
    add(f"| {r0:+.0f} -> {r1:+.0f} deg at {t0:.0f} s | {t_end - t0:.1f} s | {t90:.2f} s | {over:.1f} deg | {hold} |")

    cr = ph["cruise"]
    add("\n## Rate-controller terms in cruise (mean / RMS of each contribution)\n")
    add("| Axis | Tar mean, deg/s | FF | P | I | D | I share of output |")
    add("|---|---|---|---|---|---|---|")
    for ax, k in (("roll", "PIDR"), ("pitch", "PIDP")):
        d = cut(data[k], cr)
        tot = d["FF"] + d["P"] + d["I"] + d["D"]
        terms = " | ".join(f"{np.mean(d[t]):+.3f} / {rms(d[t]):.3f}" for t in ("FF", "P", "I", "D"))
        share = np.mean(np.abs(d["I"])) / max(np.mean(np.abs(tot)), 1e-9)
        add(f"| {ax} | {np.mean(d['Tar']):+.2f} | {terms} | {share:.0%} |")

    add("\n## Cruise steadiness (std after removing a 60 s moving mean; plain std shows slow drift)\n")
    a, te, ct, nt = (cut(data[k], cr) for k in ("ATT", "TECS", "CTUN", "NTUN"))
    add("| Signal | Fast std | Plain std | Note |")
    add("|---|---|---|---|")
    for label, d, x, unit, note in (
            ("Roll", a, a["Roll"], "deg", f"mean {np.mean(a['Roll']):+.1f} deg"),
            ("Pitch", a, a["Pitch"], "deg", f"mean {np.mean(a['Pitch']):+.1f} deg"),
            ("Height error h-hdem", te, te["h"] - te["hdem"], "m",
             f"max {np.max(np.abs(te['h'] - te['hdem'])):.1f} m"),
            ("Airspeed error sp-spdem", te, te["sp"] - te["spdem"], "m/s",
             f"max {np.max(np.abs(te['sp'] - te['spdem'])):.1f} m/s"),
            ("Throttle out", ct, ct["ThO"], "%",
             f"mean {np.mean(ct['ThO']):.1f} %, first/last 5 min "
             f"{np.mean(ct['ThO'][ct['t'] < ct['t'][0] + 300]):.1f}/{np.mean(ct['ThO'][ct['t'] > ct['t'][-1] - 300]):.1f} %"),
            ("Cross-track (orbit)", nt, nt["XT"], "m", f"mean {np.mean(nt['XT']):+.1f} m")):
        add(f"| {label} | {hp_std(d, x):.2f} {unit} | {np.std(x):.2f} {unit} | {note} |")

    add("\n## Oscillation peaks in cruise (frequency, RMS amplitude in the peak)\n")
    add("| Signal | Peak 1 | Peak 2 | Peak 3 |")
    add("|---|---|---|---|")
    spectra = {}
    for label, k, f, unit, fmin, nseg in (
            ("Roll rate error", "PIDR", "Err", "deg/s", 0.05, 1024),
            ("Pitch rate error", "PIDP", "Err", "deg/s", 0.05, 1024),
            ("Gyro X (roll)", "IMU", "GyrX", "deg/s", 0.3, 2048),
            ("Gyro Y (pitch)", "IMU", "GyrY", "deg/s", 0.3, 2048),
            ("Height error", "TECS", None, "m", 0.003, 8192),
            ("Airspeed error", "TECS", "spe", "m/s", 0.003, 8192),
            ("Throttle out", "CTUN", "ThO", "%", 0.003, 16384)):
        d = cut(data[k], cr)
        if f is None:
            x = d["h"] - d["hdem"]
        elif f == "spe":
            x = d["sp"] - d["spdem"]
        else:
            x = d[f]
        if k == "IMU":
            x = np.degrees(x)
        fq, p = welch(x, fs_of(d), nseg)
        spectra[label] = (fq, p)
        pk = peaks(fq, p, fmin)
        cells = " | ".join(f"{fr:.3f} Hz ({1 / fr:.1f} s), {amp:.3g} {unit}" for fr, amp in pk)
        add(f"| {label} | {cells} |")
    return "\n".join(lines), spectra


def plot(data, ph, spectra, path, title):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(3, 2, figsize=(14, 11))
    fig.suptitle(title)
    t0 = ph["takeoff"][0]
    a = cut(data["ATT"], (t0, ph["climb"][1] + 60))
    ax[0, 0].plot(a["t"] - t0, a["DesRoll"], label="DesRoll")
    ax[0, 0].plot(a["t"] - t0, a["Roll"], label="Roll")
    ax[0, 0].plot(a["t"] - t0, a["DesPitch"], label="DesPitch")
    ax[0, 0].plot(a["t"] - t0, a["Pitch"], label="Pitch")
    ax[0, 0].set(title="Takeoff and climb: attitude", xlabel="s from arming", ylabel="deg")
    ax[0, 0].legend(fontsize=8)
    c0 = ph["cruise"][0] + 600
    a = cut(data["ATT"], (c0, c0 + 60))
    ax[0, 1].plot(a["t"] - c0, a["DesRoll"] - a["Roll"], label="roll error")
    ax[0, 1].plot(a["t"] - c0, a["DesPitch"] - a["Pitch"], label="pitch error")
    ax[0, 1].set(title="Cruise: 60 s of attitude error", xlabel="s", ylabel="deg")
    ax[0, 1].legend(fontsize=8)
    for i, (lab, axx) in enumerate((("Roll rate error", ax[1, 0]), ("Pitch rate error", ax[1, 1]))):
        fq, p = spectra[lab]
        axx.semilogy(fq[1:], p[1:])
        axx.set(title=f"Cruise PSD: {lab.lower()}", xlabel="Hz", ylabel="(deg/s)^2/Hz")
    te = cut(data["TECS"], ph["cruise"])
    tt = (te["t"] - te["t"][0]) / 60
    ax[2, 0].plot(tt, te["h"] - te["hdem"], label="height error, m")
    ax[2, 0].plot(tt, te["sp"] - te["spdem"], label="airspeed error, m/s")
    ax[2, 0].set(title="Cruise: TECS errors", xlabel="min")
    ax[2, 0].legend(fontsize=8)
    for lab in ("Height error", "Airspeed error"):
        fq, p = spectra[lab]
        ax[2, 1].loglog(fq[1:], p[1:], label=lab)
    ax[2, 1].set(title="Cruise PSD: TECS", xlabel="Hz")
    ax[2, 1].legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=110)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("log", type=Path)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()
    out = args.out or args.log.parent.parent
    data, modes = load(args.log)
    ph = phases(data, modes)
    text, spectra = analyse(data, ph)
    run = args.log.parent.parent
    title = f"{run.parent.name}/{run.name}"
    spans = ", ".join(f"{k} {v[0]:.0f}-{v[1]:.0f} s" for k, v in ph.items())
    prm = ", ".join(f"{k} {v:g}" for k, v in data["params"].items())
    text = f"# Control-loop check: {title}\n\nPhases (log time): {spans}\n\nParameters: {prm}\n\n{text}\n"
    (out / "tuning.md").write_text(text)
    plot(data, ph, spectra, out / "tuning.png", title)
    print(text)


if __name__ == "__main__":
    sys.exit(main())
