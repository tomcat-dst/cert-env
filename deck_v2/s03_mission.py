"""Slide 2 (mission): the planned route (tsuniv_search_long.plan) as a map in km from home and as an
altitude profile, the mission facts, and the jammer-search concept the route is built for (user's
design: nose patch antenna ~45°, a semi-loiter at two points, bearings crossed; RF data synthetic)."""
import json
import math

from matplotlib.patches import Arc, Circle, Rectangle, Wedge

import chart as c
import diag as d

d.H = 46.7                      # one-line title at 28 pt leaves a taller area
HOME = (49.825888, 23.689912)
K = (111195, 111195 * math.cos(math.radians(HOME[0])))
plan = json.load(open("sim/missions/tsuniv_search_long.plan"))
items = [it for it in plan["mission"]["items"] if it["frame"] == 3 and it["command"] != 189]
pts = [(HOME[0], HOME[1], 0.0)] + [(it["params"][4], it["params"][5], it["params"][6]) for it in items]
E = [(p[1] - HOME[1]) * K[1] / 1000 for p in pts]
N = [(p[0] - HOME[0]) * K[0] / 1000 for p in pts]
s, alt, home = [0.0], [0.0], [0.0]
for i in range(1, len(pts)):
    s.append(s[-1] + math.hypot(E[i] - E[i - 1], N[i] - N[i - 1]))
    alt.append(pts[i][2])
    home.append(math.hypot(E[i], N[i]))
# indices in pts: 0 home, 1 takeoff, 2 climb-out, 3-4 transit, 5..20 grid, 21 loiter centre, 22 return,
# 23-24 approach, 25 land
LOI = 21
fig = c.figure(16, 16 * d.H / d.W)

# --- map, km from home ---
m = c.axes(fig, [0.045, 0.41, 0.53, 0.52], None, "на північ, км", size=12)
m.grid(False)
m.set_aspect("equal")
m.set_xlim(-1.5, 24.5)
m.set_ylim(-12.2, 1.8)
m.add_patch(Rectangle((min(E[5:21]) - 0.4, min(N[5:21]) - 0.4), max(E[5:21]) - min(E[5:21]) + 0.8,
                      max(N[5:21]) - min(N[5:21]) + 0.8, fc=c.ACC, alpha=0.08, ec="none"))
m.add_patch(Circle((0, 0), 5, fc=d.C["rc"], alpha=0.08, ec=d.C["rc"], lw=1.2))
m.add_patch(Circle((E[LOI], N[LOI]), 0.5, fc="none", ec=c.ACC, lw=2, ls=(0, (3, 2))))
m.plot(E, N, color=c.ACC, lw=2.2)
m.plot(E[1:LOI] + E[LOI + 1:-1], N[1:LOI] + N[LOI + 1:-1], "o", color=c.ACC, ms=3.5)
m.plot([0], [0], "s", color=d.INK, ms=8)
m.text(-0.6, 0.6, "дім, смуга 28", fontsize=12, color=d.INK, ha="left", va="bottom")
m.text(0.2, -5.6, "RC ≈ 5 км", fontsize=12, color=d.C["rc"], ha="center", va="top", fontweight="bold")
m.text((min(E[5:21]) + max(E[5:21])) / 2, max(N[5:21]) + 0.6, "сітка 8 × 5 км, крок 1 км, 900 м",
       fontsize=12, color=c.ACC, ha="center", va="bottom", fontweight="bold")
m.text(E[LOI], min(N[5:21]) - 0.7, "3 кола r 500 м над центром сітки", fontsize=11.5, color=d.INK, ha="center", va="top")
m.text(9.0, -1.4, "транзит 22 м/с", fontsize=11.5, color=d.MUTED, ha="center", va="bottom", rotation=-17)
m.text(6.6, -3.5, "повернення 500 м", fontsize=11.5, color=d.MUTED, ha="center", va="top", rotation=-17)
m.plot([20.5, 23.5], [0.9, 0.9], color=d.INK, lw=2)
m.text(22, 1.1, "3 км", fontsize=11.5, color=d.INK, ha="center", va="bottom")
m.text(0.0, 1.04, "маршрут, км від дому · geofence: коло 35 км, за межами карти", transform=m.transAxes,
       fontsize=12, color=d.MUTED)

# --- altitude profile ---
ax = c.axes(fig, [0.06, 0.09, 0.515, 0.25], "відстань по маршруту, км", "висота, м", size=12)
ax.plot(s, alt, color=c.ACC, lw=2.4)
ax.set_ylim(0, 1100)
ax.set_xlim(0, s[-1] + 1)
out = [i for i, h in enumerate(home) if h > 5]
x0 = s[out[0] - 1] + (5 - home[out[0] - 1]) / (home[out[0]] - home[out[0] - 1]) * (s[out[0]] - s[out[0] - 1])
x1 = s[out[-1]] + (home[out[-1]] - 5) / (home[out[-1]] - home[out[-1] + 1]) * (s[out[-1] + 1] - s[out[-1]])
ax.axvspan(x0, x1, color=d.C["rc"], alpha=0.10, lw=0)
ax.text((x0 + x1) / 2, 1050, "без RC: AUTO за місією", ha="center", va="top", fontsize=12,
        color=d.C["rc"], fontweight="bold")
ax.text(s[-1] - 1, 600, "посадка,\nглісада 2,3°", ha="right", va="center", fontsize=11.5, color=d.INK)
ax.text(x0 + 1.5, 600, "набір\n120 → 900 м", ha="left", va="center", fontsize=11.5, color=d.INK)

# --- right column ---
dax = fig.add_axes([0, 0, 1, 1])
dax.set_xlim(0, d.W)
dax.set_ylim(0, d.H)
dax.axis("off")
facts = ["28 пунктів · ≈ 99 км · AUTO без RC",
         "катапульта, зліт до 120 м",
         "DO_CHANGE_SPEED 22 → 19 м/с",
         "сітка 16–24 км від дому, 900 м",
         "LOITER_TURNS 3 × r 500 м, 700 м",
         "DO_LAND_START → NAV_LAND, курс 289°",
         "geofence: коло 35 км + стеля"]
hf = d.fit_h("Місія (QGC, 28 пунктів)", facts, 17, 14)
d.box(dax, 61, 46.2 - hf, 38.5, hf, "Місія (QGC, 28 пунктів)", facts, title_size=17, line_size=14)
concept = ["патч-антена в носі, промінь ≈ 45°",
           "півкола над точкою: курс з макс.",
           "потужністю → азимут на джерело",
           "дві точки → перетин азимутів",
           "tinySA + Pi Zero пишуть спектр;",
           "РЕБ і зчитування синтетичні"]
top = 46.2 - hf - 1.2
d.box(dax, 61, 0.5, 38.5, top - 0.5, "Пошук РЕБ (концепт, наступний крок)", concept, title_size=17, line_size=14,
      ec=d.C["rc"], title_color=d.C["rc"])
# schematic: two semi-loiters, the 45° beam, bearings crossing at the source (not to scale)
J, P = (92.5, 10.8), [(67.5, 5.6), (80.5, 4.0)]
dax.plot(*J, marker="*", ms=20, color=d.C["power"], zorder=4)
d.note(dax, J[0], J[1] + 1.2, "РЕБ", size=13, color=d.C["power"], ha="center", bold=True)
for k, (px, py) in enumerate(P):
    a = math.degrees(math.atan2(J[1] - py, J[0] - px))
    dax.add_patch(Wedge((px, py), 7.5, a - 22.5, a + 22.5, fc=d.C["rc"], alpha=0.14, ec="none", zorder=3))
    dax.add_patch(Arc((px, py), 3.4, 3.4, theta1=a - 90, theta2=a + 90, color=d.C["rc"], lw=2, zorder=3))
    dax.plot([px, J[0]], [py, J[1]], color=d.C["rc"], lw=1.6, ls=(0, (4, 2.5)), zorder=3)
    dax.plot(px, py, "o", color=d.INK, ms=6, zorder=4)
    d.note(dax, px - 0.6, py - 1.9, f"точка {k + 1}", size=12, ha="center", va="top")
d.note(dax, 71.5, 10.4, "промінь 45°", size=12, color=d.C["rc"], ha="center")
d.save(fig, "deck_v2/s03_mission.png")
