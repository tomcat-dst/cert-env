"""Slide (AUTOTUNE, merged from the old "AUTOTUNE" and "result" slides): the same roll command before and after
AUTOTUNE (compare/results/roll_step_traces.json), the gains MFE -> AUTOTUNE, the check metrics and the caveats.

Numbers: sim/params/believer_5kg_avl_autotune.parm against sim/params/believer_mfe.parm; metrics from
compare/oscillations.md (runs endurance-20261122-185519/-185521 MFE, -191454/-191456 AUTOTUNE)."""
import json

import chart as c
import diag as d

d.H = 46.7                      # one-line title at 28 pt
tr = json.load(open("compare/results/roll_step_traces.json"))
fig = c.figure(16, 16 * d.H / d.W)
ax = c.axes(fig, [0.05, 0.13, 0.36, 0.78], "секунди від команди", "крен, °", size=14)   # same box as s10_log
m, a = tr["mfe"], tr["at"]
ax.plot(a["ts"], a["des"], color=c.GREY, lw=2, ls=(0, (4, 2.5)))
ax.plot(m["ts"], m["roll"], color=c.GREY, lw=2.4)
ax.plot(a["ts"], a["roll"], color=c.ACC, lw=3.2)
ax.axhline(-30, color=d.C["power"], lw=1, ls=":")
ax.set_xlim(-1, 6)
ax.set_ylim(-50, 22)
ax.text(0.95, -47.5, "MFE −45°", fontsize=14, color=c.GREY, fontweight="bold")
ax.text(3.2, 6.0, "AUTOTUNE", fontsize=15, color=c.ACC, fontweight="bold")
ax.text(3.2, 0.5, "команда (пунктир)", fontsize=13, color=c.GREY)
ax.text(-0.9, -31.5, "ліміт 30°", ha="left", va="top", fontsize=13, color=d.C["power"])
ax.text(-0.9, 21.7, "той самий політ, та сама команда крену −29°", fontsize=13, color=d.INK, fontweight="bold",
        va="top")

dax = fig.add_axes([0, 0, 1, 1])
dax.set_xlim(0, d.W)
dax.set_ylim(0, d.H)
dax.axis("off")
d.box(dax, 47, 27.0, 52.5, 19.2, "Коефіцієнти: MFE → AUTOTUNE (рівень 6, SITL)", title_size=15.5)
rows = [["", "P", "I", "D", "FF", "TCONST"],
        ["крен, MFE", "0,116", "0,024", "0", "0,571", "0,45"],
        ["крен, AUTOTUNE", "1,354", "0,297", "0,016", "0,297", "0,50"],
        ["тангаж, MFE", "0,108", "0,054", "0", "0,517", "0,45"],
        ["тангаж, AUTOTUNE", "0,746", "0,560", "0,016", "0,264", "0,75"]]
d.table(dax, 48, 42.2, [0, 17.5, 24.5, 31.5, 38.5, 45.5], rows, size=13.5, row_h=3.0,
        colors=[None, None, d.C["uart"], None, d.C["uart"]])

d.box(dax, 47, 0.5, 27.5, 25.3, "Перевірка", title_size=15.5, ec=d.GOOD, title_color=d.GOOD)
rows = [["показник", "MFE", "AUTOTUNE"],
        ["перерегулювання", "16,1°", "2,1°"],
        ["зміни знака", "9", "1"],
        ["макс. крен", "45°", "32°"],
        ["Starlink, перерег.", "10,3°", "2,2°"],
        ["крейсер, база", "167 Вт", "167 Вт"],
        ["крейсер, Starlink", "195 Вт", "195 Вт"]]
d.table(dax, 48, 21.8, [0, 13.5, 19.0], rows, size=12.5, row_h=2.85,
        colors=[None, d.INK, d.INK, d.INK, d.INK, d.MUTED, d.MUTED])

d.box(dax, 76, 0.5, 23.5, 25.3, "Що врахувати", [
    "Starlink: FF крену 0,415, P 1,76",
    "сталий перекрен ≈ 2°",
    "(−30,9° проти −29°)",
    "тангаж до 28° після відриву:",
    "інтегратор під час розбігу",
    "SITL по землі",
    "коефіцієнти — для моделі;",
    "на літаку AUTOTUNE повторити"], title_size=15.5, line_size=12.5)
d.save(fig, "deck_v2/s11_autotune.png")
