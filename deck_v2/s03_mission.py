"""Slide 2 (mission): why the aircraft must work alone, the mission as flown (the two-source RFSEARCH plan
sim/missions/tsuniv_rf_two.plan: route in km from home and altitude profile) and how the jammer is located
(nose helix, a circle on the signal gives a bearing, bearings from several circles cross).

Facts: plan items and altitudes from the plan file; catapult 3.3 g and the take-off block from
sim/params/believer_5kg.parm; RC range ~5 km and FS_*_ACTN 0 from sim/params/believer_mission.parm; fence
35 km / 1000 m from the plan and believer_mission_long.parm; antenna and sources from compare/rf_companion.py.
"""
import json
import math

from matplotlib.patches import Circle, Ellipse, Wedge

import chart as c
import diag as d

d.H = 46.7                      # one-line title at 28 pt
HOME = (49.825888, 23.689912)
K = (111195, 111195 * math.cos(math.radians(HOME[0])))
plan = json.load(open("sim/missions/tsuniv_rf_two.plan"))
items = [it for it in plan["mission"]["items"] if it["frame"] == 3 and it["command"] != 189]
pts = [(HOME[0], HOME[1], 0.0)] + [(it["params"][4], it["params"][5], it["params"][6]) for it in items]
E = [(p[1] - HOME[1]) * K[1] / 1000 for p in pts]
N = [(p[0] - HOME[0]) * K[0] / 1000 for p in pts]
s, alt, home = [0.0], [0.0], [0.0]
for i in range(1, len(pts)):
    s.append(s[-1] + math.hypot(E[i] - E[i - 1], N[i] - N[i - 1]))
    alt.append(pts[i][2])
    home.append(math.hypot(E[i], N[i]))
SRC = [(16.0, 2.5), (19.5, -2.0)]            # scenario "two" in rf_companion.py: (north, east) km
fig = c.figure(16, 16 * d.H / d.W)

# --- map, km from home ---
m = c.axes(fig, [0.05, 0.085, 0.27, 0.80], "на схід, км", "на північ, км", size=12)
m.grid(False)
m.set_aspect("equal")
m.set_xlim(-11.5, 11.5)
m.set_ylim(-3, 27.5)
m.add_patch(Circle((0, 0), 5, fc=d.C["rc"], alpha=0.10, ec=d.C["rc"], lw=1.2))
m.add_patch(Circle((0.0, 17.75), 4.6, fc=d.C["power"], alpha=0.10, ec=d.C["power"], lw=1.2, ls=(0, (4, 2.5))))
m.plot(E, N, color=c.ACC, lw=2.2)
m.plot(E[1:-1], N[1:-1], "o", color=c.ACC, ms=3.5)
m.plot([0], [0], "s", color=d.INK, ms=8)
for n, e in SRC:
    m.plot(e, n, marker="*", ms=15, color=d.C["power"])
m.text(0.9, -1.9, "дім: катапульта,\nпосадка із заходу", fontsize=11.5, color=d.INK, ha="left", va="center")
m.text(-0.6, 3.3, "RC ≈ 5 км", fontsize=12, color=d.C["rc"], ha="center", va="bottom", fontweight="bold")
m.text(0.0, 23.3, "район пошуку", fontsize=12, color=d.C["power"], ha="center", va="bottom", fontweight="bold")
m.text(9.6, 11.5, "900 м, 19 м/с", fontsize=11.5, color=c.ACC, ha="left", va="center", rotation=90)
m.text(0.0, 1.03, "маршрут, км від дому · geofence 35 км — за межами карти", transform=m.transAxes, fontsize=12,
       color=d.MUTED)

# --- altitude profile ---
ax = c.axes(fig, [0.405, 0.47, 0.245, 0.30], "відстань по маршруту, км", "висота, м", size=11.5)
ax.plot(s, alt, color=c.ACC, lw=2.4)
ax.set_ylim(0, 1100)
ax.set_xlim(0, s[-1] + 1)
out = [i for i, h in enumerate(home) if h > 5]
x0 = s[out[0] - 1] + (5 - home[out[0] - 1]) / (home[out[0]] - home[out[0] - 1]) * (s[out[0]] - s[out[0] - 1])
x1 = s[out[-1]] + (home[out[-1]] - 5) / (home[out[-1]] - home[out[-1] + 1]) * (s[out[-1] + 1] - s[out[-1]])
ax.axvspan(x0, x1, color=d.C["rc"], alpha=0.10, lw=0)
ax.text((x0 + x1) / 2, 1060, "без RC: місія йде далі", ha="center", va="top", fontsize=11.5, color=d.C["rc"],
        fontweight="bold")

dax = fig.add_axes([0, 0, 1, 1])
dax.set_xlim(0, d.W)
dax.set_ylim(0, d.H)
dax.axis("off")
# --- middle column: why alone, the mission ---
why = ["джерело завад може впливати на RC,", "LTE, GNSS. Це штатна ситуація"]
hw = d.fit_h("Місія без RC", why, 16, 13.5)
d.box(dax, 37, 46.2 - hw, 30, hw, "Місія без RC", why, title_size=16, line_size=13.5, ec=d.C["power"],
      title_color=d.C["power"])
facts = [f"{len(plan['mission']['items'])} пунктів · ≈ {s[-1]:.0f} км · ≈ 1 год 05 хв",
         "катапульта 3,3 g, зліт до 120 м",
         "набір до 900 м, крейсер 19 м/с",
         "RFSEARCH: місія як в AUTO + кола",
         "RC лише до ≈ 5 км: FS_*_ACTN 0",
         "DO_LAND_START → NAV_LAND, курс 109°",
         "geofence: коло 35 км, стеля 1000 м"]
d.box(dax, 37, 0.5, 30, None, "Місія (QGC, SITL)", facts, title_size=16, line_size=13.5)

# --- right column: how the source is located ---
concept = ["Helix-антена з кутом 30 градусів",
           "сигнал ≥ порога → коло 360°:",
           "антена оглядає всі напрямки,",
           "найсильніший напрямок = пеленг",
           "пеленги з кількох кіл перетинаються:",
           "оцінка з еліпсом похибки → QGC",
           "tinySA + Pi Zero; у SITL РЕБ синтетичний"]
d.box(dax, 69, 0.5, 30.5, 45.7, "Пошук РЕБ: пеленги з кіл", concept, title_size=16, line_size=13.5,
      ec=d.C["rc"], title_color=d.C["rc"])
# schematic (not to scale): a track with three circles, each giving a bearing to the source
J = (87.5, 27.5)
track = [(71.5, 6.5), (79.0, 5.0), (88.0, 7.5), (97.0, 14.0)]
dax.plot(*zip(*track), color=d.INK, lw=1.8, zorder=3)
dax.add_patch(Ellipse(J, 6.0, 3.4, angle=25, fc=d.C["power"], alpha=0.12, ec=d.C["power"], lw=1.6, zorder=4))
dax.plot(*J, marker="*", ms=20, color=d.C["power"], zorder=5)
d.note(dax, J[0], J[1] + 2.6, "РЕБ і еліпс похибки", size=12.5, color=d.C["power"], ha="center", bold=True)
for k, (px, py) in enumerate([(74.0, 6.0), (83.5, 6.2), (93.0, 11.1)]):
    cy = py + 1.6
    a = math.degrees(math.atan2(J[1] - cy, J[0] - px))
    if k == 0:
        dax.add_patch(Wedge((px, cy), 9.0, a - 15, a + 15, fc=d.C["rc"], alpha=0.16, ec="none", zorder=2))
    dax.add_patch(Circle((px, cy), 1.6, fc="none", ec=d.C["rc"], lw=2.2, zorder=4))
    dax.plot([px, J[0]], [cy, J[1]], color=d.C["rc"], lw=1.6, ls=(0, (4, 2.5)), zorder=3)
    d.note(dax, px, py - 0.6, f"коло {k + 1}", size=12, ha="center", va="top")
d.note(dax, 74.0, 16.8, "промінь 30°", size=12, color=d.C["rc"], ha="center")
d.note(dax, 95.5, 20.5, "пеленг", size=12, color=d.C["rc"], ha="center")
d.save(fig, "deck_v2/s03_mission.png")
