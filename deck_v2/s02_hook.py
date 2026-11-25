"""Slide 2: what stock SITL showed for the Believer (numbers from slide 8 notes and the 900 m runs).
Each card pairs the stock-SITL number with the value it should have had, as a pair of bars."""
import diag as d
from matplotlib.patches import FancyBboxPatch

d.H = 46.7                      # taller area: the title is one line at 28 pt
fig, ax = d.canvas()
BAD, OK = d.C["power"], d.GOOD


def bar(ax, x, y, length, label, value, col, size=13.5):
    """Label above a thin rounded bar, value at its end."""
    d.note(ax, x, y + 2.6, label, size=size, va="bottom")
    ax.add_patch(FancyBboxPatch((x, y), max(length, 0.4), 1.7, boxstyle="round,pad=0,rounding_size=0.5",
                                fc=col, ec="none", zorder=3))
    d.note(ax, x + max(length, 0.4) + 0.6, y + 0.85, value, size=size, color=col, va="center", bold=True)


cards = [
    ("Газ у крейсері", "7,8%", "замість ≈ 50%",
     [("SITL: тяга лінійна за газом", 7.8, "7,8%", BAD), ("модель X3120 + APC 11×7E", 50, "≈ 50%", OK)], 50,
     ["тяга не падає зі швидкістю,", "струм = 50 А × газ²:", "енергія на крейсер занижена"]),
    ("Трубка Піто", "−5,7%", "занижує на 1190 м",
     [("на 590 м", 2.8, "−2,8%", BAD), ("на 1190 м", 5.7, "−5,7%", BAD)], 6.5,
     ["похибка росте з висотою:", "швидкість двічі", "перераховано в EAS"]),
    ("Турбулентність", "−17%", "потужності при 2 м/с",
     [("штиль", 100, "100%", d.MUTED), ("пориви 2 м/с, SITL", 83, "83%", BAD)], 100,
     ["пориви мали б коштувати", "енергії, а «економили»;", "після виправлення: +5…14 хв"]),
    ("Звалювання", "16 м/с", "при 11,6 м/с у моделі",
     [("модель AVL", 11.6, "11,6 м/с", OK), ("SITL", 16, "16 м/с", BAD)], 16,
     ["з поривів не виходив:", "падіння з 900 м,", "3 удари за один політ"]),
]
w, gap, y0, y1 = 23.6, 1.2, 12.2, 46.2
for i, (head, big, sub, bars, vmax, lines) in enumerate(cards):
    x = 0.5 + i * (w + gap)
    d.box(ax, x, y0, w, y1 - y0, None, ec=BAD if i == 3 else d.LINE)
    d.note(ax, x + 1.2, 45.0, head, size=19, color=d.INK, va="top", bold=True)
    d.note(ax, x + 1.2, 41.6, big, size=42, color=BAD, va="top", bold=True)
    d.note(ax, x + 1.2, 36.0, sub, size=15.5, color=d.INK, va="top")
    span = w - 2.4 - 6.5                      # room for the value text after the bar
    for j, (label, v, txt, col) in enumerate(bars):
        bar(ax, x + 1.2, 28.4 - j * 5.4, span * v / vmax, label, txt, col)
    for j, ln in enumerate(lines):
        d.note(ax, x + 1.2, 20.4 - j * 2.55, ln, size=14, va="top")

d.box(ax, 0.5, 0.5, 99, 10.0, None, ec=d.LINE)
d.note(ax, 1.7, 7.6, "Наслідок", size=17, color=d.INK, va="center", bold=True)
d.note(ax, 12.0, 7.6, "з такою моделлю час польоту і запас до звалювання оцінити не можна → "
       "три виправлення SITL, слайд 8", size=15.5, color=d.INK, va="center")
d.note(ax, 1.7, 3.2, "Believer у стандартному SITL ArduPilot 4.7.3 · аеродинаміка AVL · 5,0 кг · "
       "сірі смуги: база, зелені: правильне значення, червоні: що показав SITL", size=13, va="center")
d.save(fig, "deck_v2/s02_hook.png")
