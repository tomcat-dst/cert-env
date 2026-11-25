"""Slide 4: power distribution with peak currents and margins, plus the battery current SITL logged
at take-off and climb.

Peaks from SITL with the 3.3 g catapult, 100 % throttle for 5 s from motor start (TKOFF_THR_MAX 100,
TKOFF_THR_MAX_T 5, then 75 %), rotation hold (TKOFF_ROTATE_SPD 15, GND_PITCH 5, LVL_PITCH 8), climb 2 m/s,
gusts 5-10 m/s + turbulence 2 m/s: 88.8 A total (44 A per motor) for Starlink, 86.7 A for the base build
(endurance-20261124-015050 / -015048, BAT ~10 Hz via compare/bat_trace.py; compare/launch.md).
Cruise at 19 m/s, 900 m: 7.7 A total at 5.0 kg;
ratings ESC 60 A, motor 65 A for 30 s, cell 60 A continuous, current sensor 132 A, BEC12S-PRO 5 A / 9 A.
"""
import csv

import chart as c
import diag as d

d.H = 46.7                      # one-line title at 28 pt
fig = c.figure(16, 16 * d.H / d.W)
ax = fig.add_axes([0, 0, 1, 1])
ax.set_xlim(0, d.W)
ax.set_ylim(0, d.H)
ax.axis("off")
P = d.C["power"]
T, L = 17, 14

# battery -> current sensor -> 6S bus
d.box(ax, 0.5, 33.0, 15.5, None, "Батарея 6S4P", ["Molicel P50B, 24 шт.", "20 А·год · 444 Вт·год",
                                                 "25,2 В повна · 22,2 В ном.", "комірка: пік 21,7 А / 60 А"],
      ec=P, title_size=T, line_size=13)
d.wire(ax, [(16, 38.0), (18, 38.0)], "power", lw=5)
d.box(ax, 18, 33.5, 14, None, "Датчик струму", ["плата H743-WING", "до 132 А · 66,7 А/В", "пік 89 А (1,5×)"],
      ec=P, title_size=T - 1, line_size=13)
d.wire(ax, [(32, 38.0), (34.5, 38.0)], "power", lw=5)
d.wire(ax, [(34.5, 3.5), (34.5, 45.0)], "power", lw=5)          # 6S bus
d.note(ax, 33.8, 44.8, "шина 6S", size=13, color=P, ha="right", va="top", bold=True)

rows = [  # y, converter box, load box
    (35.0, ("ESC 1 · 60 А", ["пік 44 А (1,4×)", "крейсер ≈ 3,9 А (SITL)"]),
     ("X3120 585KV", ["APC 11×7E · 65 А/30 с", "пік 44 А на 4 с (1,5×)"])),
    (25.3, ("ESC 2 · 60 А", ["пік 44 А (1,4×)", "крейсер ≈ 3,9 А (SITL)"]),
     ("X3120 585KV", ["APC 11×7E · 65 А/30 с", "пік 44 А на 4 с (1,5×)"])),
    (15.6, ("BEC12S-PRO", ["9–55 В → 5,2 В", "5 А тривало / 9 А пік"]),
     ("Pi Zero 2 W + USB-хаб", ["tinySA ≤ 1,3 А · LTE · камера", "≈ 2 А, пік 4,5 А (2×)"])),
    (5.9, ("BEC плати H743", ["5 В: FC, GPS, ELRS, DLVR", "6 В: серворейка"]),
     ("4× ES3054", ["17 г · 3,5 кг·см при 6 В", "серворейка 6 В"])),
]
for y, (t1, l1), (t2, l2) in rows:
    h = d.fit_h(t1, l1, T, L)
    d.wire(ax, [(34.5, y + h / 2), (36.5, y + h / 2)], "power", lw=3)
    d.box(ax, 36.5, y, 18, h, t1, l1, title_size=T, line_size=L)
    d.wire(ax, [(54.5, y + h / 2), (56.5, y + h / 2)], "power", lw=3)
    d.box(ax, 56.5, y, 19.5, h, t2, l2, title_size=T, line_size=L)

# option: Starlink needs its own converter, the BEC12S-PRO cannot carry it
d.wire(ax, [(34.5, 45.0), (88, 45.0), (88, 42.5)], "power", lw=2.5, dashed=True)
d.box(ax, 77.5, 35.0, 22, 7.5, "Starlink Mini (варіант)", ["окремий DC-DC, 12–48 В", "25–40 Вт, пік до 75 Вт"],
      title_size=T - 1, line_size=L - 1, ec=P)

d.box(ax, 77.5, 5.9, 22, 27.6, "Запас по струму, А", title_size=T)
d.table(ax, 78.5, 29.6, [0, 8.2, 16.0], [
    ["вузол", "пік / ном.", "запас"],
    ["ESC", "44 / 60", "1,4×"],
    ["мотор", "44 / 65", "1,5×"],
    ["комірка", "21,7 / 60", "2,8×"],
    ["датчик", "89 / 132", "1,5×"],
    ["BEC", "4,5 / 9", "2×"]], size=14, row_h=3.0)
d.note(ax, 78.5, 12.0, "пік — 4 с зльоту на 100% газу;\nдалі THR_MAX 75: ≤ 42 А\n6S5P: 17,8 А на комірку (3,4×)", size=11.5,
       va="top")

# --- battery current at take-off, two SITL runs ---
d.box(ax, 0.5, 0.5, 32.5, 31.0, None)
d.note(ax, 1.4, 30.8, "Струм батареї: зліт і набір до 900 м, SITL", size=14, color=d.INK, va="top", bold=True)
RUNS = [("compare/results/endurance-20261124-015050/believer-avl-at/bat_trace.csv",
         "Starlink 5,9 кг, пориви + турб.", c.ACC2),
        ("compare/results/endurance-20261124-015048/believer-5kg-avl-at/bat_trace.csv",
         "базова 5,0 кг, пориви + турб.", c.ACC)]
cax = c.axes(fig, [0.05, 0.105, 0.27, 0.44], "хвилини від пострілу", "А, з батареї", size=11)
for path, label, col in RUNS:
    r = list(csv.DictReader(open(path)))
    t = [float(x["t_min"]) for x in r]
    a = [float(x["amps"]) for x in r]
    k = 15                                      # 3 s rolling mean (BAT ~10 Hz); keeps the ~4 s boost
    a = [sum(a[max(0, i - k):i + k + 1]) / len(a[max(0, i - k):i + k + 1]) for i in range(len(a))]
    cax.plot(t, a, color=col, lw=1.8, label=label)
cax.set_xlim(0, 9.5)
cax.set_ylim(0, 95)
cax.annotate("катапульта 3,3 g, далі 100% газу 5 с:\n87–89 А ≈ 4 с", (0.15, 86), (2.3, 72), fontsize=10.5,
             color=d.INK, va="center", arrowprops=dict(arrowstyle="-", color=d.MUTED, lw=1))
cax.text(9.4, 42, "далі газ ≤ 75%, набір 2 м/с до 900 м", ha="right", va="bottom", fontsize=10.5, color=d.MUTED)
cax.text(9.4, 52.5, "тангаж зльоту ≤ 8°: 0 падінь у 18 стартах\nSITL (при 15°: 2 з 19)", ha="right", va="bottom",
         fontsize=10.5, color=d.C["power"])
cax.legend(frameon=False, fontsize=10.5, labelcolor=d.MUTED, loc="upper right", bbox_to_anchor=(1.0, 1.0))
d.note(ax, 1.4, 28.6, "ESC 2 × 60 = 120 А і датчик 132 А — вище шкали · середнє за 3 с", size=10.5, va="top")
d.save(fig, "deck_v2/s06_power.png")
