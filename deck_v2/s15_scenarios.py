"""Slide (SITL missions, replaces the 23.11 long-mission slide): the two RFSEARCH flights flown from QGC on
2026-11-25 side by side: the simple scenario (two sources, 70 km plan) and the realistic one (four sources, the
south-west route reworked in QGC).

Sources: compare/results/mission-20261125-154716 (two sources: logs/mission-rfsearch-two-qgc-1547.out) and
compare/results/mission-20261125-151006 (four sources: logs/mission-rfsearch-sw4-qgc-1510.out): rf_result.json
(truth, fixes with error_m and ellipse_m_deg, bearings) and rf_samples.csv (track). Flight time is ARMED to
"landed and disarmed", distance is the flown track (circles included), both from those logs. The RC-loss line
is the 23.11 long mission (compare/results/mission-20261123-165646, in the report).
"""
import csv
import json
import math
import re

from matplotlib.patches import Ellipse

import diag as d

d.H = 46.7                      # one-line title at 28 pt
fig, ax = d.canvas()
ROOT = "/home/tomcat/cert-env/"
HOME = (49.825888, 23.689912)
K = math.cos(math.radians(HOME[0]))
SRC_COL = ["#6CB4FF", "#F0A640", "#B48CFF", "#3FD0C0"]
AMBER = d.C["usb"]


def km(la, lo):
    return (lo - HOME[1]) * 111.195 * K, (la - HOME[0]) * 111.195


def load(run, log):
    res = json.load(open(ROOT + run + "/believer-5kg-avl-at/rf_result.json"))
    text = open(ROOT + log).read()
    arm = float(re.findall(r"t=\s*([\d.]+)\s+ARMED", text)[-1])
    land = float(re.findall(r"t=\s*([\d.]+)\s+landed and disarmed", text)[-1])
    trk = [km(float(r["lat"]), float(r["lon"])) for r in csv.DictReader(open(ROOT + run + "/believer-5kg-avl-at/rf_samples.csv"))
           if abs(float(r["lat"])) > 1 and arm <= float(r["t"]) <= land]
    dist = sum(math.dist(a, b) for a, b in zip(trk, trk[1:]))          # km() works in km
    return dict(res=res, trk=trk[::5], minutes=round((land - arm) / 60), dist=dist, far=max(math.hypot(*p) for p in trk),
                circles=len(re.findall(r"RFS: sweep \d+, course", text)),
                stop=int(re.findall(r"landed and disarmed: (\d+) m from home", text)[-1]))


def draw_map(f, x0, y0, w, h, label_at=None, home_left=False):
    """label_at: {truth index: (dx, dy, ha)} for labels that would overlap at the default place."""
    label_at = label_at or {}
    res, trk = f["res"], f["trk"]
    truth = [km(t[0], t[1]) for t in res["truth"]]
    xs, ys = zip(*(trk + truth))
    x_lo, x_hi, y_lo, y_hi = min(xs) - 1.5, max(xs) + 1.5, min(ys) - 1.5, max(ys) + 1.5
    sc = min(w / (x_hi - x_lo), h / (y_hi - y_lo))
    ox, oy = x0 + (w - sc * (x_hi - x_lo)) / 2, y0 + (h - sc * (y_hi - y_lo)) / 2
    P = lambda x, y: (ox + (x - x_lo) * sc, oy + (y - y_lo) * sc)
    col = {fx["id"]: SRC_COL[(fx["truth_index"] - 1) % 4] for fx in res["fixes"]}
    for b in res["bearings"]:
        x, y = km(*b["pos"])
        L = 0.0
        for step in range(1, 61):                                 # ray up to 15 km, clipped to the map box
            xe, ye = x + 0.25 * step * math.sin(math.radians(b["bearing"])), y + 0.25 * step * math.cos(math.radians(b["bearing"]))
            if not (x_lo <= xe <= x_hi and y_lo <= ye <= y_hi):
                break
            L = 0.25 * step
        xe, ye = x + L * math.sin(math.radians(b["bearing"])), y + L * math.cos(math.radians(b["bearing"]))
        ax.plot(*zip(P(x, y), P(xe, ye)), color=col.get(b.get("source"), d.MUTED), lw=0.9, alpha=0.5, zorder=2)
    ax.plot(*zip(*[P(*p) for p in trk]), color=d.INK, lw=1.2, alpha=0.85, zorder=3)
    hx, hy = P(0, 0)
    ax.plot(hx, hy, marker="^", color=d.GOOD, ms=10, zorder=5)
    d.note(ax, hx + (0.9 if home_left else 0.7), hy + (0.9 if home_left else 0.5), "Цунів", size=11.5, color=d.GOOD,
           ha="left")
    for fx in res["fixes"]:
        t = truth[fx["truth_index"] - 1]
        tx, ty = P(*t)
        fxx, fyy = P(*km(*fx["pos"]))
        a, b, ori = fx["ellipse_m_deg"]
        ax.add_patch(Ellipse((fxx, fyy), 2 * a / 1000 * sc, 2 * b / 1000 * sc, angle=90 - ori, fill=False,
                             ec=col[fx["id"]], lw=1.8, zorder=5))
        ax.plot(tx, ty, marker="x", color=d.INK, ms=11, mew=2.4, zorder=6)
        dx, dy, ha = label_at.get(fx["truth_index"], (0.9, 0.6, "left"))
        d.note(ax, tx + dx, ty + dy, f"T{fx['truth_index']}  {fx['error_m']:.0f} м", size=12.5, color=d.INK, bold=True, ha=ha)
    # 5 km scale bar
    bx, by = x0 + 0.6, y0 + 0.5
    ax.plot([bx, bx + 5 * sc], [by, by], color=d.MUTED, lw=2.5, zorder=4)
    d.note(ax, bx + 5 * sc + 0.5, by - 0.5, "5 км", size=11)


def panel(x0, title, sub, accent, f, big, big_label, rows, row_cols, facts, why, **map_kw):
    top, y0, w = 46.2, 4.6, 49.25
    d.box(ax, x0, y0, w, top - y0, None, ec=d.LINE)
    d.note(ax, x0 + 1, top - 0.5, title, size=18, color=accent, va="top", bold=True)
    d.note(ax, x0 + 1, top - 3.4, sub, size=12.5, va="top")
    draw_map(f, x0 + 1, y0 + 0.8, 28.0, top - y0 - 6.6, **map_kw)
    sx = x0 + 30.2
    d.note(ax, sx, top - 9.0, big, size=27, color=accent, bold=True)
    d.note(ax, sx, top - 9.8, big_label, size=12.5, va="top")
    d.table(ax, sx, top - 13.6, [0, 2.8, 8.4, 15.6], [("", "похибка", "еліпс 1σ, м", "пел.")] + rows, size=12, row_h=2.25,
            colors=[None] + row_cols)
    y = top - 13.6 - 2.25 * (len(rows) + 1) - 1.2
    for ln in facts:
        d.note(ax, sx, y, ln, size=12.5, color=d.INK, va="top")
        y -= 2.0
    y -= 0.9
    for ln in why:
        d.note(ax, sx, y, ln, size=11.8, va="top")
        y -= 1.85


two = load("compare/results/mission-20261125-154716", "logs/mission-rfsearch-two-qgc-1547.out")
four = load("compare/results/mission-20261125-151006", "logs/mission-rfsearch-sw4-qgc-1510.out")


def rows_of(f, bad=()):
    out, cols = [], []
    for fx in sorted(f["res"]["fixes"], key=lambda fx: fx["truth_index"]):
        a, b, _ = fx["ellipse_m_deg"]
        out.append((f"T{fx['truth_index']}", f"{fx['error_m']:.0f} м", f"{a:.0f} × {b:.0f}", f"{len(fx['bearings'])}"))
        cols.append(AMBER if fx["truth_index"] in bad else d.INK)
    return out, cols


def facts_of(f):
    return [f"політ {f['minutes']} хв, {f['dist']:.0f} км, до {f['far']:.1f} км".replace(".", ","),
            f"{f['circles']} кіл, {len(f['res']['bearings'])} пеленгів",
            f"посадка: {f['stop']} м від точки старту"]


e2 = sorted(fx["error_m"] for fx in two["res"]["fixes"])
r2, c2 = rows_of(two)
panel(0.5, "Простий сценарій: 2 джерела", "план 69 км на північ, коло проти годинникової стрілки", d.GOOD, two,
      f"{e2[0]:.0f} і {e2[1]:.0f} м", "обидва джерела знайдено", r2, c2, facts_of(two),
      ["маршрут обходить обидва джерела,", "пеленги перетинаються під", "широкими кутами: еліпси малі"])
e4 = sorted(fx["error_m"] for fx in four["res"]["fixes"])
r4, c4 = rows_of(four, bad=(1, 4))
panel(50.25, "Реалістичний сценарій: 4 джерела", "маршрут на південний захід, складений у QGC", AMBER, four,
      f"{e4[0]:.0f}–{e4[-1]:.0f} м", "усі 4 знайдено, два — грубо", r4, c4, facts_of(four),
      ["T1 і T4 зі східного плеча лежать на", "одній лінії: кола 10–17 бачили їх як", "одне джерело; у T1 лише 5 майже",
       "паралельних пеленгів → еліпс 2,4 км"],
      label_at={1: (0.9, 1.0, "left"), 4: (-0.9, 0.8, "right"), 3: (-0.9, -2.2, "right"), 2: (0.9, -2.0, "left")},
      home_left=True)

d.box(ax, 0.5, 0.5, 99, 3.4, None, ec=d.LINE)
d.note(ax, 1.5, 2.2, "Обидва польоти: QGC + SITL, RFSEARCH від катапульти до автопосадки, ті самі параметри RFS_, "
       "синтетичні джерела.", size=12, color=d.INK, va="center")
d.note(ax, 98.5, 2.2, "Втрата RC — окремий політ 23.11: 1 год 15 хв в AUTO без RC", size=12, va="center", ha="right")
d.save(fig, "deck_v2/s15_scenarios.png")
