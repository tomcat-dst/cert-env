"""Slide 9 (right panel): the flown long mission, altitude and distance from home vs time, with the
log events (compare/results/mission-20261123-165646, extracted to deck_v2/mission_profiles.json)."""
import json

import chart as c
import diag as d

p = json.load(open("deck_v2/mission_profiles.json"))
t = [r[0] / 60 for r in p["flight"]]
alt = [r[1] for r in p["flight"]]
home = [r[2] for r in p["flight"]]

fig = c.figure(7.6, 6.6)
ax = c.axes(fig, [0.13, 0.30, 0.74, 0.62], "хвилини від пострілу", "висота, м", size=13)
ax.plot(t, alt, color=c.ACC, lw=2.4)
ax.set_ylim(0, 1100)
ax.set_xlim(0, 85)
ax2 = ax.twinx()
ax2.plot(t, home, color=d.C["rc"], lw=1.8, ls=(0, (4, 2.5)))
ax2.axhline(5, color=d.C["rc"], lw=1)
ax2.set_ylim(0, 27.5)
ax2.tick_params(colors=d.C["rc"], labelsize=13)
ax2.set_ylabel("від дому, км", fontsize=13, color=d.C["rc"])
for sp in ("top", "left", "bottom"):
    ax2.spines[sp].set_visible(False)
ax2.spines["right"].set_color(d.C["rc"])
ev = {"RC Short Failsafe On": "RC втрачено", "RC Long Failsafe Cleared": "RC є", "Mission: 25 LandStart": "посадка",
      "SIM Hit ground": "дотик"}
marks = []
for ts, msg in p["events"]:
    for k, lab in ev.items():
        if msg.startswith(k):
            marks.append((ts / 60, lab))
ax.axvspan(marks[0][0], [m for m in marks if m[1] == "RC є"][0][0], color=d.C["rc"], alpha=0.10 if d.DARK else 0.07, lw=0)
for i, (x, lab) in enumerate(marks):
    ax.axvline(x, color=d.MUTED, lw=0.9, ls=":")
    ax.text(x + (0.8 if lab == "RC втрачено" else -0.8), 1080 - (i % 2) * 70, lab, fontsize=12,
            color=d.INK, ha="left" if lab == "RC втрачено" else "right", va="top")
ax.text(40, 470, "без RC 1 год 15 хв, AUTO", ha="center", fontsize=13, color=d.C["rc"], fontweight="bold")

dax = fig.add_axes([0, 0, 1, 1])
dax.axis("off")
dax.set_xlim(0, 1)
dax.set_ylim(0, 1)
facts = [("1 год 23 хв", "у повітрі"), ("101 км", "за QGC"), ("52%", "батареї"), ("0,56 м/с", "дотик")]
for i, (big, small) in enumerate(facts):
    x = 0.02 + i * 0.245
    dax.text(x, 0.115, big, fontsize=18, fontweight="bold", color=d.C["uart"], va="bottom")
    dax.text(x, 0.105, small, fontsize=12, color=d.MUTED, va="top")
d.save(fig, "deck_v2/s09_flight.png")
