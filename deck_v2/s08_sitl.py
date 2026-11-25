"""Slide 5: what stock SITL showed (the symptom strip, formerly its own hook slide) and the three SITL
fixes, each with before/after numbers.

Sources: patches/ardupilot-sitl-plane-electric-propulsion.patch (header), patches/ardupilot-upstream/
PR_DESCRIPTION.md (stock model 7.8 % cruise throttle, 21 m/s climb, 52 m/s on take-off; patched 33 m/s,
11.2 m/s climb, 195 W loiter against a 193 W hand calculation), endurance-20261124-002019 / -002024
(cruise throttle 43.9 / 44.2 %, 172 / 194 W in gusts against 169 / 196 W calm, height 880-922 m),
compare/oscillations.md "Fixed gust model" (correlation 0.00083 s -> 27.3 s, -17 % power, 3 of 4
turbulence flights fell from 900 m, base 0 h 50 -> 1 h 54) and its margin rerun (8 more variants, no
in-flight ground contact). Pitot under-read is EAS2TAS: 2.8 % at 590 m AMSL, 5.7 % at 1190 m (ISA).
"""
import diag as d

d.H = 46.7                      # one-line title at 28 pt
fig, ax = d.canvas()

# what stock SITL showed (the former hook slide): one symptom above each fix card
BAD = d.C["power"]
symptoms = [(0.5, "7,8%", ["газу в крейсері", "замість ≈ 50%"]),
            (34, "−5,7%", ["Піто на 1190 м н.р.м.:", "летить швидше заданого"]),
            (67.5, "−17%", ["пориви давали енергію, а мали", "забирати; падав з 900 м на", "16–22 м/с (звалювання 11,6)"])]
for x, big, ls in symptoms:
    d.box(ax, x, 37.4, 32, 8.8, None, ec=BAD)
    d.note(ax, x + 1, 45.4, "стандартний SITL", size=11.5, color=BAD, va="top", bold=True)
    d.note(ax, x + 1, 39.0, big, size=30, color=BAD, va="bottom", bold=True)
    y0 = 42.6 if len(ls) == 2 else 43.6
    for j, ln in enumerate(ls):
        d.note(ax, x + 12.6, y0 - j * 2.0, ln, size=12.5 if len(ls) > 2 else 13, color=d.INK, va="top")

# three fixes, each: what was wrong, what changed, measured before/after
fixes = [
    (0.5, "1 · Рушій", "SIM_Plane",
     ["тяга лінійна за газом, не падає", "зі швидкістю; струм 50 А × газ²"],
     ["модель X3120 585KV + APC 11×7E", "+ батарея 6S; маса й інерція з JSON;", "катапульта 3,3 g, далі 100% газу 5 с"],
     [("газ у крейсері", "7,8%", "44–49%"), ("набір", "21 м/с", "11 м/с"), ("на зльоті", "52 м/с", "33 м/с"),
      ("крейсер: SITL / розрах.", "—", "195 / 193 Вт")]),
    (34, "2 · Трубка Піто", "датчики",
     ["EAS ділиться на EAS2TAS двічі", "(SIM_Aircraft + sitl_airspeed)"],
     ["перенесено виправлення", "з master ArduPilot;", "летить із заданою швидкістю"],
     [("Піто: 590 м н.р.м.", "−2,8%", "0"), ("Піто: 1190 м н.р.м.", "−5,7%", "0"),
      ("швидкість польоту", "вища", "задана"), ("час польоту (оцінка)", "занижено", "точно")]),
    (67.5, "3 · Пориви", "SIM_Plane",
     ["2·rand() переповнює int:", "напрямок — білий шум 1200 Гц"],
     ["Орнштейн–Уленбек, масштаб", "Драйдена (MIL-F-8785C),", "σ не залежить від частоти кадру"],
     [("кореляція пориву", "0,8 мс", "27 с"), ("потужність vs штиль", "−17%", "−1…+14%"),
      ("падіння з 900 м", "3 з 4", "0 з 15"), ("базова в поривах", "0:50", "1:54–2:02")]),
]
CX = [1, 16.4, 24.0]            # table columns inside a card
for x, title, where, before, after, rows in fixes:
    d.box(ax, x, 0.5, 32, 35.2, None, ec=d.LINE)
    d.note(ax, x + 1, 34.7, title, size=18, color=d.INK, va="top", bold=True)
    d.note(ax, x + 31, 34.5, where, size=12, color=d.MUTED, va="top", ha="right")
    d.note(ax, x + 1, 31.4, "було", size=12.5, color=d.C["power"], va="top", bold=True)
    for j, ln in enumerate(before):
        d.note(ax, x + 1, 29.4 - j * 1.95, ln, size=13, va="top")
    d.note(ax, x + 1, 25.3, "стало", size=12.5, color=d.GOOD, va="top", bold=True)
    for j, ln in enumerate(after):
        d.note(ax, x + 1, 23.3 - j * 1.95, ln, size=13, va="top")
    ax.plot([x + 1, x + 31], [17.2, 17.2], color=d.LINE, lw=1)
    for c, (h, col) in enumerate((("виміряно в SITL", d.INK), ("було", d.C["power"]), ("стало", d.GOOD))):
        d.note(ax, x + CX[c], 16.5, h, size=12, color=col, va="top", bold=True)
    for r, row in enumerate(rows):
        yy = 13.8 - r * 3.15
        for c, cell in enumerate(row):
            d.note(ax, x + CX[c], yy, cell, size=13.5 if c else 12.5, va="top", bold=c == 2,
                   color=d.GOOD if c == 2 else (d.INK if c == 1 else d.MUTED))
d.save(fig, "deck_v2/s08_sitl.png")
