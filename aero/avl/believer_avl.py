#!/usr/bin/env python3
"""
AVL model of the MFE Believer 1960 (base) and the 2x20 cm insert variant, and the mapping of
its derivatives into ArduPilot SITL's plane json.

  python3 aero/avl/believer_avl.py            # writes aero/avl/out/<variant>.{avl,st,sb} + summary
  python3 aero/avl/believer_avl.py --json     # also prints the SITL json keys for each variant

Published: span 1.96 m, wing area 0.514 m^2 (51.4 dm^2), fuselage 1.07 m x 0.185 m, V-tail.
Everything else is ESTIMATED (see GEOMETRY below); no tail, control-surface or CG data were
found in the manufacturer's page, the ArduPilot forum thread or the course lab sheets.

Estimates and how they were chosen:
- Wing: straight-tapered, root chord 0.300 m, tip 0.2245 m (area 0.514 m^2 with 1.96 m span),
  2 deg dihedral, 1 deg LE sweep, 2 deg washout, NACA 2412 camber line, 2 deg incidence.
  Leading edge at x = 0.36 m from the nose.
- V-tail: sized from tail volume coefficients Vh 0.45 and Vv 0.030 with a ~0.50 m tail arm;
  equivalent Sh 0.123 m^2 and Sv 0.060 m^2 give a 35 deg V angle and 0.183 m^2 total.
  Panels 0.42 m long, chord 0.25 -> 0.185 m, 15 deg LE sweep, root LE at x = 0.85 m.
  Tail incidence is solved so the base aircraft trims at cruise with zero elevator.
- Controls: ailerons 25% chord from 50% to 95% semispan, +-20 deg; ruddervators 35% chord full
  span, +-25 deg per panel, with ArduPilot's default MIXING_GAIN 0.5 -> 12.5 deg per axis.
- Fuselage: AVL slender body, 1.07 m long, 0.185 m max diameter (published height used as
  diameter).
- CG: 10% MAC ahead of the neutral point of each variant (operator balances the aircraft).
- Inserts variant: a constant 0.300 m chord centre section 0.20 m each side.
"""
import argparse
import json
import math
import re
import subprocess
from pathlib import Path

AVL = Path.home() / "cert-env/src/avl-dl/Avl/bin/avl"
OUT = Path(__file__).resolve().parent / "out"

RHO = 1.17            # kg/m^3, ~465 m AMSL (Tsuniv 290 m + 175 m working altitude)
V = 20.0              # m/s cruise
G = 9.80665
SM = 0.10             # static margin, fraction of MAC
AIL_MAX = math.radians(20)
RV_PANEL_MAX = math.radians(25)
MIX = 0.5             # ArduPilot MIXING_GAIN default
E_MAX = R_MAX = RV_PANEL_MAX * MIX

VARIANTS = {
    "believer_5kg": dict(mass=5.0, insert=0.0),
    "believer":     dict(mass=5.9, insert=0.20),
}

WING_X, CR, CT, SEMI = 0.36, 0.300, 0.2245, 0.98
DIHEDRAL, SWEEP_LE, WASHOUT, INCIDENCE = 2.0, 1.0, 2.0, 2.0
TAIL_X, TAIL_LEN, TAIL_CR, TAIL_CT, TAIL_V, TAIL_SWEEP = 0.85, 0.42, 0.25, 0.185, 35.0, 15.0
FUSE_L, FUSE_D = 1.07, 0.185


def fuselage_file(path):
    """Side profile for AVL BFIL: airfoil-style x/z, top TE->LE then bottom LE->TE (metres)."""
    n = 40
    xs = [FUSE_L * (1 - math.cos(math.pi * i / n)) / 2 for i in range(n + 1)]
    def r(x):
        t = x / FUSE_L
        # blunt nose, max diameter at ~35% length, tapering tail boom to ~25% of max
        return FUSE_D / 2 * (min(1.0, 2.2 * math.sqrt(t)) if t < 0.35 else 1.0 - 0.75 * ((t - 0.35) / 0.65) ** 1.3)
    pts = [(x, r(x)) for x in reversed(xs)] + [(x, -r(x)) for x in xs[1:]]
    path.write_text("Believer fuselage\n" + "".join(f"{x:.5f} {z:.5f}\n" for x, z in pts))


def wing_sections(insert):
    """(y, x_le, z, chord, twist) from root to tip; the insert shifts the original wing outboard."""
    secs = []
    if insert > 0:
        secs.append((0.0, WING_X, 0.0, CR, INCIDENCE))
    y0 = insert
    for frac in (0.0, 0.5, 0.95, 1.0):
        y = SEMI * frac
        secs.append((y0 + y,
                     WING_X + y * math.tan(math.radians(SWEEP_LE)),
                     (y0 + y) * math.tan(math.radians(DIHEDRAL)),
                     CR + (CT - CR) * frac,
                     INCIDENCE - WASHOUT * frac))
    return secs


def write_avl(path, insert, xcg, tail_inc):
    secs = wing_sections(insert)
    semi = secs[-1][0]
    area = 2 * sum((b[0] - a[0]) * (a[3] + b[3]) / 2 for a, b in zip(secs, secs[1:]))
    mac = 2 / area * sum(
        (b[0] - a[0]) / 3 * (a[3] ** 2 + a[3] * b[3] + b[3] ** 2) for a, b in zip(secs, secs[1:]))
    lines = [f"Believer insert={insert:.2f} m", "0.0", "0 0 0.0",
             f"{area:.5f} {mac:.5f} {2 * semi:.5f}", f"{xcg:.5f} 0 0", "0.0", "",
             "SURFACE", "Wing", "10 1.0 32 -1.1", "YDUPLICATE", "0.0", ""]
    ail_y0, ail_y1 = insert + 0.5 * SEMI, insert + 0.95 * SEMI
    for (y, x, z, c, tw) in secs:
        lines += ["SECTION", f"{x:.5f} {y:.5f} {z:.5f} {c:.5f} {tw:.3f}", "NACA", "2412"]
        if ail_y0 - 1e-6 <= y <= ail_y1 + 1e-6:
            # gain 1, hinge 75% chord, hinge axis along the hinge line, SgnDup -1 (antisymmetric)
            lines += ["CONTROL", "aileron 1.0 0.75 0 0 0 -1"]
        lines.append("")
    # V-tail panel: root on the centreline, tip out along the V
    gam = math.radians(TAIL_V)
    ty = TAIL_LEN * math.cos(gam)
    tz = TAIL_LEN * math.sin(gam)
    tx = TAIL_X + TAIL_LEN * math.tan(math.radians(TAIL_SWEEP))
    lines += ["SURFACE", "Vtail", "8 1.0 14 1.0", "YDUPLICATE", "0.0", "ANGLE", f"{tail_inc:.3f}", ""]
    for (x, y, z, c) in ((TAIL_X, 0.0, 0.03, TAIL_CR), (tx, ty, 0.03 + tz, TAIL_CT)):
        lines += ["SECTION", f"{x:.5f} {y:.5f} {z:.5f} {c:.5f} 0",
                  "CONTROL", "elevator 1.0 0.65 0 0 0 1",
                  "CONTROL", "rudder 1.0 0.65 0 0 0 -1", ""]
    lines += ["BODY", "Fuselage", "24 1.0", "BFIL", "fuselage.dat", ""]
    path.write_text("\n".join(lines) + "\n")
    return area, mac, 2 * semi


def run_avl(avl_file, cmds, cwd):
    p = subprocess.run([str(AVL), avl_file.name], input=cmds, text=True, cwd=cwd,
                       capture_output=True, timeout=120)
    return p.stdout


def parse(text):
    vals = {}
    for k, v in re.findall(r"([A-Za-z][A-Za-z0-9']*)\s*=\s*(-?[0-9]+\.?[0-9]*(?:[Ee][-+]?[0-9]+)?)", text):
        vals.setdefault(k, float(v))
    return vals


def analyse(name, cl, insert, xcg, tail_inc, trim=True):
    """Run AVL at the cruise CL; elevator trims Cm (if trim). Returns (st, sb, run output)."""
    OUT.mkdir(exist_ok=True)
    avl = OUT / f"{name}.avl"
    write_avl(avl, insert, xcg, tail_inc)
    for ext in ("st", "sb"):
        (OUT / f"{name}.{ext}").unlink(missing_ok=True)
    trim_cmd = "D1 PM 0\n" if trim else ""
    # controls: d1 aileron, d2 elevator, d3 rudder in AVL's order of first appearance
    trim_cmd = trim_cmd.replace("D1", "D2")
    cmds = (f"PLOP\nG F\n\nOPER\nA C {cl:.5f}\n{trim_cmd}X\n"
            f"ST {name}.st\nSB {name}.sb\n\nQUIT\n")
    out = run_avl(avl, cmds, OUT)
    st = parse((OUT / f"{name}.st").read_text())
    sb = parse((OUT / f"{name}.sb").read_text())
    return st, sb, out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    OUT.mkdir(exist_ok=True)
    fuselage_file(OUT / "fuselage.dat")

    # 1) tail incidence: base aircraft, CG at NP - SM*MAC, zero elevator at cruise CL
    base = VARIANTS["believer_5kg"]
    results = {}
    tail_inc = 0.0
    for name, var in VARIANTS.items():
        area, mac, span = write_avl(OUT / f"{name}.avl", var["insert"], WING_X, tail_inc)
        cl = 2 * var["mass"] * G / (RHO * V * V * area)
        # neutral point (independent of xref); iterate xcg once it is known
        st, _, _ = analyse(name, cl, var["insert"], WING_X + 0.25 * mac, tail_inc, trim=False)
        xnp = st["Xnp"]
        xcg = xnp - SM * mac
        if name == "believer_5kg":
            # solve tail incidence for zero elevator: secant on the trimmed elevator angle
            def elev(inc):
                st_, _, _ = analyse(name, cl, var["insert"], xcg, inc)
                return st_["elevator"]
            a, b = -2.0, 2.0
            fa, fb = elev(a), elev(b)
            for _ in range(8):
                if abs(fb) < 1e-3 or fb == fa:
                    break
                c = b - fb * (b - a) / (fb - fa)
                a, fa, b, fb = b, fb, c, elev(c)
            tail_inc = b
        st, sb, out = analyse(name, cl, var["insert"], xcg, tail_inc)
        results[name] = dict(area=area, mac=mac, span=span, cl=cl, xnp=xnp, xcg=xcg,
                             tail_inc=tail_inc, st=st, sb=sb)

    summary = {k: {kk: (round(vv, 5) if isinstance(vv, float) else vv) for kk, vv in r.items()
                   if kk not in ("st", "sb")} for k, r in results.items()}
    for k, r in results.items():
        summary[k]["alpha_deg"] = r["st"].get("Alpha")
        summary[k]["elevator_deg"] = r["st"].get("elevator")
        summary[k]["sitl"] = to_sitl(r)
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2) if args.json else
          json.dumps({k: {kk: vv for kk, vv in v.items() if kk != "sitl"} for k, v in summary.items()}, indent=2))


def to_sitl(r):
    """AVL derivatives -> SITL plane json keys. Lateral from SB (body axes, X fwd, Z down; v/V ~ beta),
    lift/pitch from ST (stability axes, as SITL applies lift). Controls are per unit servo throw."""
    sb, st = r["sb"], r["st"]
    d2r = 180 / math.pi
    # AVL control derivatives are per degree; positive deflection = trailing edge down for
    # elevator/aileron (right panel), right-hand rotation about the hinge for the rudder.
    # SITL (skywalker defaults): +aileron -> +roll, +elevator -> nose up, +rudder -> nose right.
    sa = -1 if sb["Cld01"] < 0 else 1
    se = -1 if sb["Cmd02"] < 0 else 1
    sr = -1 if sb["Cnd03"] < 0 else 1
    ka, ke, kr = sa * d2r * AIL_MAX, se * d2r * E_MAX, sr * d2r * R_MAX
    return {
        "s": round(r["area"], 4), "b": round(r["span"], 4), "c": round(r["mac"], 4),
        "c_lift_0": round(st["CLtot"] - st["CLa"] * math.radians(st["Alpha"]) - st["CLd02"] * st["elevator"], 4),
        "c_lift_a": round(st["CLa"], 4),
        "c_lift_q": round(st["CLq"], 4),
        "c_lift_deltae": round(st["CLd02"] * ke, 4),
        "c_y_b": round(sb["CYv"], 4), "c_y_p": round(sb["CYp"], 4), "c_y_r": round(sb["CYr"], 4),
        "c_y_deltaa": round(sb["CYd01"] * ka, 4), "c_y_deltar": round(sb["CYd03"] * kr, 4),
        "c_l_b": round(sb["Clv"], 4), "c_l_p": round(sb["Clp"], 4), "c_l_r": round(sb["Clr"], 4),
        "c_l_deltaa": round(sb["Cld01"] * ka, 4), "c_l_deltar": round(sb["Cld03"] * kr, 4),
        "c_m_0": round(st["Cmtot"] - st["Cma"] * math.radians(st["Alpha"]) - st["Cmd02"] * st["elevator"], 4),
        "c_m_a": round(st["Cma"], 4), "c_m_q": round(st["Cmq"], 4),
        "c_m_deltae": round(st["Cmd02"] * ke, 4),
        "c_n_b": round(sb["Cnv"], 4), "c_n_p": round(sb["Cnp"], 4), "c_n_r": round(sb["Cnr"], 4),
        "c_n_deltaa": round(sb["Cnd01"] * ka, 4), "c_n_deltar": round(sb["Cnd03"] * kr, 4),
        "CGOffset": [0, 0, 0],
    }


if __name__ == "__main__":
    main()
