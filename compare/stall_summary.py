#!/usr/bin/env python3
"""
Stall exposure across runs: how long each flight spent past the model's stall angle, in how many
episodes, and what it cost in height and endurance.

  compare/stall_summary.py compare/results/<run>/<model> [...]

The stall angle comes from the model json's "alpha_stall" (radians) in the run folder, so a run
flown with different aerodynamics is still measured against its own stall. Counts start 1 s after
SITL truth altitude first exceeds 0.5 m, so the ground run of the catapult launch is excluded.
"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import log_health as lh  # noqa: E402
import log_tuning as lt  # noqa: E402

TUNED = ("TECS_PITCH_MAX", "TECS_SPDWEIGHT", "TECS_CLMB_MAX", "AIRSPEED_MIN", "AIRSPEED_CRUISE")
# log_health only records the names it needs for its own checks; add the ones compared here
lh.PARAMS = tuple(dict.fromkeys(lh.PARAMS + TUNED))


def episodes(t, mask):
    idx = np.where(mask)[0]
    if not len(idx):
        return []
    out, start, prev = [], idx[0], idx[0]
    for i in idx[1:]:
        if i != prev + 1:
            out.append((t[start], t[prev]))
            start = i
        prev = i
    out.append((t[start], t[prev]))
    return out


def stall_angle(run):
    """Angle of attack at CLmax for the run's model, in degrees.

    Not the json's "alpha_stall": that is the centre of SITL's sigmoid blend between the linear
    lift curve and the flat-plate model, and the blend pulls the peak well below it (10.0 deg
    against a 12.5 deg key for the Believer). Lift starts falling at CLmax, so that is the angle
    that matters. Mirrors liftCoeff() in SITL's SIM_Plane.cpp.
    """
    for j in Path(run).glob("*.json"):
        body = json.loads("\n".join(l for l in j.read_text().splitlines() if not l.startswith("#")))
        if "alpha_stall" not in body:
            continue
        a0, M, c0, ca = body["alpha_stall"], body["mcoeff"], body["c_lift_0"], body["c_lift_a"]
        al = np.radians(np.arange(0, 30, 0.05))
        al = np.clip(al, a0 - 0.8, a0 + 0.8)
        sig = ((1 + np.exp(-M * (al - a0)) + np.exp(M * (al + a0)))
               / (1 + np.exp(-M * (al - a0))) / (1 + np.exp(M * (al + a0))))
        cl = (1 - sig) * (c0 + ca * al) + sig * (2 * np.sin(al) ** 2 * np.cos(al))
        return float(np.degrees(al[np.argmax(cl)])), j.name
    return 10.0, "default"


def main():
    rows = []
    for run in sys.argv[1:]:
        run = Path(run)
        ang, src = stall_angle(run)
        data, modes, msgs, prm, _, _ = lh.load(run / "logs/00000001.BIN")
        sim = data["SIM"]
        lo = sim["t"][np.argmax(sim["Alt"] - sim["Alt"][0] > 0.5)]
        end = modes[-1][0] if modes[-1][1] == 11 else data["ATT"]["t"][-1]
        ao = lt.cut(data["AOA"], (lo + 1, end))
        dt = float(np.median(np.diff(ao["t"])))
        eps = episodes(ao["t"], ao["AOA"] > ang)
        long = [(a, b) for a, b in eps if b - a > 1.0]
        te = lt.cut(data["TECS"], (lo + 1, end))
        hits = [round(t) for t, m in msgs if "Hit ground" in m]
        rows.append(dict(
            run=f"{run.parent.name}/{run.name}", ang=ang, src=src,
            params={k: prm[k] for k in TUNED if k in prm},
            wind={k: (v[-1][1] if v else 0.0) for k, v in data["wind"].items()},
            flight=end - lo, stall_s=len(ao["AOA"][ao["AOA"] > ang]) * dt,
            n_eps=len(eps), n_long=len(long),
            longest=max((b - a for a, b in eps), default=0.0),
            worst_alt=float(np.min(te["h"] - te["hdem"])), hits=hits,
            first=long[0][0] if long else None))

    w = max(len(r["run"]) for r in rows)
    print(f"{'run':{w}}  {'flight':>7} {'stall':>7} {'%':>5} {'eps':>4} {'>1s':>4} "
          f"{'longest':>8} {'1st':>6} {'min h-hdem':>11} {'hits':>5}")
    for r in rows:
        print(f"{r['run']:{w}}  {r['flight']:7.0f} {r['stall_s']:7.1f} "
              f"{100 * r['stall_s'] / r['flight']:5.1f} {r['n_eps']:4d} {r['n_long']:4d} "
              f"{r['longest']:8.1f} {('%.0f' % r['first']) if r['first'] else '-':>6} "
              f"{r['worst_alt']:11.0f} {len(r['hits']):5d}")
    print("\nstall angle and parameters per run:")
    for r in rows:
        print(f"  {r['run']}: {r['ang']:.1f} deg from {r['src']}; "
              + ", ".join(f"{k} {v:g}" for k, v in r["params"].items())
              + "; " + ", ".join(f"{k} {v:g}" for k, v in r["wind"].items()))
    print("\nflight/stall/longest in seconds; % of airborne time past the stall angle; "
          "1st = start of the first episode over 1 s; min h-hdem = worst height shortfall, m.")


if __name__ == "__main__":
    main()
