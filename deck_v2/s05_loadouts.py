"""Slide 3: the two loadouts. Top view of the Starlink variant (root inserts, dish, battery), spec table,
SITL endurance (gusty bars: THR_MAX 75, climb 2 m/s, runs endurance-20261124-002019/-002024) and the power split (slide notes: 169 / 196 W motors at 900 m, 18 / 54 W consumption of the payload electronics,
90 % of 444 / 555 Wh). The top view is schematic: span and fuselage length to scale, chords are not."""
import numpy as np
from matplotlib.patches import Polygon, Rectangle, FancyBboxPatch

import chart as c
import diag as d

d.H = 46.7                      # one-line title at 28 pt
fig = c.figure(16, 16 * d.H / d.W)
dax = fig.add_axes([0, 0, 1, 1])
dax.set_xlim(0, d.W)
dax.set_ylim(0, d.H)
dax.axis("off")
INS = d.C["usb"]                # root inserts
DISH = d.C["rf"]

# --- top view, Starlink variant ---
d.box(dax, 0.5, 21.0, 48.5, 25.2, None)
d.note(dax, 1.5, 45.4, "Starlink-варіант, вид зверху", size=14, color=d.INK, va="top", bold=True)
d.note(dax, 1.5, 43.7, "розмах і довжина 1,07 м у масштабі, хорди схематично", size=10.5, va="top")
S, XC, YLE = 16.0, 24.75, 33.8             # units per metre, centre line, wing leading edge


def P(x, y):
    return XC + x * S, YLE + y * S


def poly(pts, **kw):
    dax.add_patch(Polygon([P(*p) for p in pts], closed=True, zorder=kw.pop("zorder", 3), **kw))


FW, CR, CT = 0.07, 0.28, 0.18              # half fuselage width, root and tip chord, m
for sgn in (-1, 1):
    poly([(sgn * FW, 0), (sgn * (FW + 0.2), 0), (sgn * (FW + 0.2), -CR), (sgn * FW, -CR)],
         fc=INS, alpha=0.35, ec=INS, lw=1.6)
    poly([(sgn * (FW + 0.2), 0), (sgn * 1.18, -0.03), (sgn * 1.18, -0.03 - CT), (sgn * (FW + 0.2), -CR)],
         fc=d.BOX, ec=d.INK, lw=1.4)
    # motor nacelle and prop on the panel
    nx = sgn * (FW + 0.2 + 0.12)
    poly([(nx - 0.03, 0.14), (nx + 0.03, 0.14), (nx + 0.03, -0.18), (nx - 0.03, -0.18)], fc=d.BOX, ec=d.INK, lw=1.2)
    dax.plot(*zip(P(nx - 0.12, 0.15), P(nx + 0.12, 0.15)), color=d.MUTED, lw=2, zorder=4)
    # V-tail, seen from above
    poly([(sgn * 0.02, -0.56), (sgn * 0.30, -0.66), (sgn * 0.30, -0.72), (sgn * 0.02, -0.69)],
         fc=d.BOX, ec=d.INK, lw=1.2)
poly([(-FW, 0.25), (-0.05, 0.36), (0.05, 0.36), (FW, 0.25), (FW, -0.30), (0.03, -0.69), (-0.03, -0.69), (-FW, -0.30)],
     fc=d.BOX, ec=d.INK, lw=1.4, zorder=4)
dax.add_patch(Rectangle(P(-0.05, -0.05), 0.10 * S, 0.24 * S, fc="none", ec=d.C["power"], lw=1.4, ls="--", zorder=6))
dax.add_patch(FancyBboxPatch(P(-0.13, -0.27), 0.26 * S, 0.30 * S, boxstyle="round,pad=0,rounding_size=0.5",
                             fc=DISH, alpha=0.30, ec=DISH, lw=1.6, zorder=5))
# span dimensions
for half, lab, yy in ((1.18, "2,36 м зі вставками", 42.0), (0.98, "1,96 м базова", 40.4)):
    x0, x1 = XC - half * S, XC + half * S
    dax.annotate("", (x0, yy), (x1, yy), arrowprops=dict(arrowstyle="<->", color=d.MUTED, lw=1.2))
    d.note(dax, x1, yy + 0.2, lab, size=10.5, color=d.INK, ha="right", va="bottom")
# callouts with leaders
def callout(xy, txt_xy, txt, col, ha):
    dax.plot([xy[0], txt_xy[0]], [xy[1], txt_xy[1]], color=col, lw=1, zorder=7)
    d.note(dax, txt_xy[0] + (0.3 if ha == "left" else -0.3), txt_xy[1], txt, size=10.5, color=col, ha=ha,
           va="center")


callout(P(0.17, -0.20), (36.0, 24.6), "вставки 2 × 20 см EPO,\nподовжений лонжерон", INS, "left")
callout(P(-0.10, -0.20), (12.0, 24.6), "Starlink Mini\n1,1 кг · 25–40 Вт", DISH, "right")
callout(P(0.05, 0.12), (36.0, 37.4), "батарея 6S5P\n(базова 6S4P)", d.C["power"], "left")

# --- spec table ---
rows = [["", "Базова", "Starlink"],
        ["маса", "5,0 кг", "5,9 кг (+0,4 понад MTOW)"],
        ["MTOW MFE", "5,5 кг (рекоменд. 4,2)", "5,5 кг на штатному крилі"],
        ["розмах · площа", "1,96 м · 0,514 м²", "2,36 м · 0,634 м²"],
        ["навантаж. на крило", "9,7 кг/м²", "9,3 кг/м² (при MTOW 10,7)"],
        ["батарея", "6S4P · 20 А·год · 444 Вт·год", "6S5P · 25 А·год · 555 Вт·год"],
        ["мотори · гвинти", "2× X3120 585KV · APC 11×7E", "2× X3120 585KV · APC 11×7E"],
        ["канал", "LTE (EG25-G)", "Starlink Mini"],
        ["звалювання · крейсер", "11,6 · 19 м/с", "11,2 · 19 м/с"],
        ["споживання", "18 Вт", "54 Вт (через DC-DC)"]]
d.box(dax, 0.5, 0.5, 48.5, 19.6, None)
d.table(dax, 1.4, 19.3, [0, 12.8, 30.0], rows, size=11.5, row_h=1.72)
d.note(dax, 48.3, 1.0, "MTOW: дані MFE; лонжерон під 5,9 кг ще не перевірено", size=9.5, color=d.C["power"],
       ha="right", va="bottom")

# --- endurance ---
ax = c.axes(fig, [0.555, 0.43, 0.425, 0.50], None, "хвилин польоту", size=12)
cats = ["300 м, штиль", "900 м, штиль", "900 м, пориви 5–10 м/с\n+ турб. 2 м/с, газ ≤ 75%"]
base, star = [127, 122, 122], [118, 114, 110]
x = np.arange(3)
b1 = ax.bar(x - 0.2, base, 0.38, color=c.ACC, label="базова")
b2 = ax.bar(x + 0.2, star, 0.38, color=c.ACC2, label="Starlink")
for bars in (b1, b2):
    for r in bars:
        m = int(r.get_height())
        ax.text(r.get_x() + r.get_width() / 2, m + 2, f"{m // 60}:{m % 60:02d}", ha="center", va="bottom",
                fontsize=12.5, color=d.INK, fontweight="bold")
ax.axhline(64, color=d.C["power"], lw=1.5, ls=(0, (4, 2.5)), label="місія 1:04, 38% батареї")
ax.set_xticks(x, cats, fontsize=12, color=d.INK)
ax.set_ylim(0, 145)
ax.legend(frameon=False, fontsize=11.5, labelcolor=d.MUTED, loc="upper right", ncol=3, bbox_to_anchor=(1.0, 1.13))

# --- power split ---
d.box(dax, 52.5, 0.5, 47, 15.4, None)
d.note(dax, 53.5, 15.1, "Потужність у крейсері на 900 м", size=13.5, color=d.INK, va="top", bold=True)
PX0, PS = 62.0, 0.088                      # bar origin, units per watt
for k, (name, mot, pay, energy, t) in enumerate([("базова", 169, 18, 400, "2:02"),
                                               ("Starlink", 196, 54, 500, "1:54")]):
    yy = 10.6 - k * 4.6
    d.note(dax, 53.5, yy + 0.9, name, size=12, color=d.INK, va="center", bold=True)
    dax.add_patch(Rectangle((PX0, yy), mot * PS, 1.8, fc=c.ACC if k == 0 else c.ACC2, ec="none", zorder=3))
    dax.add_patch(Rectangle((PX0 + mot * PS, yy), pay * PS, 1.8, fc=DISH if k else d.C["uart"], ec="none", zorder=3))
    d.note(dax, PX0 + 0.4, yy + 0.9, f"мотори {mot} Вт", size=10.5, color="#0E1411", va="center", bold=True)
    d.note(dax, PX0 + (mot + pay) * PS + 0.5, yy + 0.9, f"+{pay} Вт споживання = {mot + pay} Вт", size=10.5, va="center")
    d.note(dax, 53.5, yy - 0.9, f"{energy} Вт·год* · {t}", size=10.5, va="center")
d.note(dax, 53.5, 3.0, "* 90% ємності батареї: останні 10% — резерв під battery failsafe (RTL)", size=10,
       va="bottom")
d.note(dax, 53.5, 1.1, "Starlink: +34% потужності, +25% енергії → −8 хв на 900 м", size=11, color=d.C["power"],
       va="bottom")
d.save(fig, "deck_v2/s05_loadouts.png")
