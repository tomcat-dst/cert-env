"""Slide 12: the same roll command before and after AUTOTUNE (roll_step_traces.json) and the metrics
from slide 12 notes."""
import json

import chart as c
import diag as d

tr = json.load(open("compare/results/roll_step_traces.json"))
fig = c.figure(16, 16 * d.H / d.W)
ax = c.axes(fig, [0.05, 0.13, 0.55, 0.80], "секунди від команди", "крен, °", size=14)
m, a = tr["mfe"], tr["at"]
ax.plot(a["ts"], a["des"], color=c.GREY, lw=2, ls=(0, (4, 2.5)))
ax.plot(m["ts"], m["roll"], color=c.GREY, lw=2.4)
ax.plot(a["ts"], a["roll"], color=c.ACC, lw=3.2)
ax.axhline(-30, color=d.C["power"], lw=1, ls=":")
ax.set_xlim(-1, 6)
ax.set_ylim(-50, 22)
ax.text(0.95, -47.5, "MFE −45°", fontsize=14, color=c.GREY, fontweight="bold")
ax.text(4.2, -25.5, "AUTOTUNE", fontsize=15, color=c.ACC, fontweight="bold")
ax.text(4.2, -21.5, "команда", fontsize=13, color=c.GREY)
ax.text(-0.9, -31.5, "ліміт 30°", ha="left", va="top", fontsize=13, color=d.C["power"])

dax = fig.add_axes([0, 0, 1, 1])
dax.set_xlim(0, d.W)
dax.set_ylim(0, d.H)
dax.axis("off")
d.box(dax, 63, 1, 36.5, 41, "Той самий політ, та сама команда", title_size=17)
rows = [["показник", "MFE", "AUTOTUNE"],
        ["перерегулювання", "16,1°", "2,1°"],
        ["зміни знака", "9", "1"],
        ["макс. крен", "45°", "32°"],
        ["Starlink, перерег.", "10,3°", "2,2°"],
        ["крейсер, база", "167 Вт", "167 Вт"],
        ["крейсер, Starlink", "195 Вт", "195 Вт"]]
d.table(dax, 64, 37.0, [0, 17.5, 25.5], rows, size=16, row_h=4.1,
        colors=[None, None, None, None, None, d.MUTED, d.MUTED])
d.note(dax, 64, 7.5, "SITL · Believer 5,0 кг · Цунів · 300 м\n19 м/с · штиль · вхід у GUIDED", size=13.5, va="top")
d.save(fig, "deck_v2/s12_result.png")
