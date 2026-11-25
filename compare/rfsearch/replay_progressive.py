"""Replay stored RFSEARCH flights through the companion's estimator circle by circle, as the live companion
publishes them (stable source ids, bearing assignment, ellipses), and score how the estimates behave:
final error, how often a source's ellipse grows (> 20 % in area), how often its position jumps further than its
previous 2-sigma ellipse, and how often the true source lies inside the 2-sigma ellipse.

usage: python compare/rfsearch/replay_progressive.py [--v2] RESULTS_DIR... > out.json
RESULTS_DIR is a run's believer-* directory (rf_result.json, rf_samples.csv, events.txt). --v2 switches on the
estimator changes behind rf_companion.ESTIMATOR_V2, --v3 those behind ESTIMATOR_V3 as well. Bearing sigmas are the
ones stored in the run (so the signal-level factor is in them only for runs flown with it).
"""
import csv
import json
import math
import re
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import rf_companion as rc  # noqa: E402


class Null:
    """Stands in for the MAVLink connection: every attribute and call is a no-op."""
    def __getattr__(self, name):
        return self

    def __call__(self, *a, **k):
        return self


def load(d):
    d = Path(d)
    res = json.loads((d / "rf_result.json").read_text())
    ev = (d / "events.txt").read_text()
    st = {int(n): float(t) for t, n in re.findall(r"([\d.]+)\s+text: RFS: sweep (\d+), course", ev)}
    dn = {int(n): float(t) for t, n in re.findall(r"([\d.]+)\s+text: RFS: sweep (\d+) done", ev)}
    rec, legs = {}, []
    for r in csv.DictReader(open(d / "rf_samples.csv")):
        t = float(r["t"])
        s = dict(lat=float(r["lat"]), lon=float(r["lon"]), alt=float(r["alt"]), yaw=float(r["yaw"]),
                 dbm=float(r["dbm"]), bn=float(r["bn"]), be=float(r["be"]), bd=float(r["bd"]), t=t)
        k = next((k for k in st if st[k] <= t <= dn.get(k, st[k] + 40)), 0)
        if k:
            rec.setdefault(k, []).append(s)
        elif s["alt"] >= rc.LEG_MIN_ALT:
            legs.append(s)
    return res, st, dn, rec, legs


def mahal(f, p):
    """Distance of p from fix f in units of its 1-sigma ellipse."""
    a, b, ori = f.get("ellipse_m_deg", (f["sigma_m"], f["sigma_m"], 0.0))
    n, e = rc.ned(f["pos"], p)
    th = math.radians(ori)
    u = n * math.cos(th) + e * math.sin(th)       # along the major axis (azimuth ori)
    v = -n * math.sin(th) + e * math.cos(th)
    return math.hypot(u / max(a, 1.0), v / max(b, 1.0))


def replay(args):
    d, v2, v3 = args
    sys.stdout = sys.stderr                       # the companion's text() prints; keep stdout for the JSON
    rc.ESTIMATOR_V2 = v2
    rc.ESTIMATOR_V3 = v3
    res, st, dn, rec, legs = load(d)
    truth = res["truth"]
    gcs = rc.Gcs(Null())
    nmax = max(b["obs"] for b in res["bearings"])
    steps, prev = [], {}
    for n in range(3, nmax + 1):
        for b in res["bearings"]:
            if b["obs"] == n or (n == 3 and b["obs"] < 3):
                gcs.bearing({k: v for k, v in b.items() if k not in ("id", "source")})
        if n not in dn:
            continue
        bs = [dict(b) for b in gcs.bearings]
        samples = [s for k in sorted(rec) if k <= n for s in rec[k]][::3] + [s for s in legs if s["t"] <= dn[n]][::rc.LEG_STEP]
        pts = [b["pos"] for b in bs]
        c = (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))
        half = min(max(9000.0, max(math.hypot(*rc.ned(c, p)) for p in pts) + 3000.0), 20000.0)
        priors = [dict(pos=f["pos"], sigma_m=f["sigma_m"]) for f in gcs.fixes.values()]
        fixes, _ = rc.solve_multi(bs, samples, c, half, priors=priors) if v2 else rc.solve_multi(bs, samples, c, half)
        gcs.set_sources(fixes)
        step = dict(n=n, src={})
        for ti, t in enumerate(truth, 1):
            if not gcs.fixes:
                step["src"][ti] = None
                continue
            sid, f = min(gcs.fixes.items(), key=lambda kv: math.hypot(*rc.ned(kv[1]["pos"], t[:2])))
            a, b, _ = f.get("ellipse_m_deg", (f["sigma_m"], f["sigma_m"], 0.0))
            o = dict(id=sid, err=math.hypot(*rc.ned(f["pos"], t[:2])), area=math.pi * a * b, maj=a,
                     inside=mahal(f, t[:2]) <= 2.0, nb=len(f.get("bearings", [])))
            p = prev.get(sid)
            if p is not None:
                o["grew"] = o["area"] > 1.2 * p["area"]
                o["jump"] = mahal(p["fix"], f["pos"]) > 2.0
            prev[sid] = dict(area=o["area"], fix=dict(pos=f["pos"], sigma_m=f["sigma_m"],
                                                      ellipse_m_deg=f.get("ellipse_m_deg")))
            if prev[sid]["fix"]["ellipse_m_deg"] is None:
                del prev[sid]["fix"]["ellipse_m_deg"]
            step["src"][ti] = o
        steps.append(step)
    final = steps[-1]["src"]
    flat = [o for s in steps for o in s["src"].values() if o]
    late = [o for s in steps[-5:] for o in s["src"].values() if o]
    return dict(run=str(d), v2=v2, v3=v3, final=[round(o["err"]) if o else None for o in final.values()],
                updates=len(flat), grew=sum(o.get("grew", False) for o in flat),
                jumps=sum(o.get("jump", False) for o in flat), inside=sum(o["inside"] for o in flat),
                late_err=[round(o["err"]) for o in late], late_inside=sum(o["inside"] for o in late),
                steps=[dict(n=s["n"], src={k: (None if o is None else {kk: (round(vv, 1) if isinstance(vv, float) else vv)
                                                                    for kk, vv in o.items()}) for k, o in s["src"].items()})
                       for s in steps])


if __name__ == "__main__":
    v3 = "--v3" in sys.argv
    v2 = "--v2" in sys.argv or v3
    dirs = [a for a in sys.argv[1:] if not a.startswith("--")]
    with ProcessPoolExecutor(min(len(dirs), 15)) as ex:
        out = list(ex.map(replay, [(d, v2, v3) for d in dirs]))
    json.dump(out, sys.stdout, indent=1)
    print()
