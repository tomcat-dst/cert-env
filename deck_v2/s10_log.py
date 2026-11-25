"""Slide 10: the roll ringing with MFE gains (ATT, compare/results/roll_step_traces.json) and the
roll-rate loop that explains it (PIDR values from slide 10 notes: target limited by RLL2SRV_RMAX 75 deg/s,
FF 0.57 -> -74 % aileron, actual -124 deg/s while the target was -29 deg/s, P 0.12, I 0.02)."""
import json

import chart as c
import diag as d

tr = json.load(open("compare/results/roll_step_traces.json"))["mfe"]
t = tr["ts"]          # already relative to the command

fig = c.figure(16, 16 * d.H / d.W)
ax = c.axes(fig, [0.05, 0.13, 0.36, 0.78], "секунди від команди", "крен, °", size=14)
ax.plot(t, tr["des"], color=c.GREY, lw=2, ls=(0, (4, 2.5)))
ax.plot(t, tr["roll"], color=c.ACC, lw=3)
ax.axhline(-30, color=d.C["power"], lw=1, ls=":")
ax.set_xlim(-1, 6)
ax.set_ylim(-50, 22)
ax.text(-0.9, -31.5, "ліміт 30°", ha="left", va="top", fontsize=13, color=d.C["power"])
ax.text(0.95, -46.5, "−45°", fontsize=15, color=c.ACC, fontweight="bold")
ax.text(2.4, -20.5, "команда −29°", fontsize=13, color=c.GREY)
ax.text(-0.9, 19.5, "крен (ATT), коефіцієнти MFE", fontsize=14, color=d.INK, fontweight="bold", va="top")

dax = fig.add_axes([0, 0, 1, 1])
dax.set_xlim(0, d.W)
dax.set_ylim(0, d.H)
dax.axis("off")
# roll-rate loop, ArduPlane roll controller
Y = 33
d.box(dax, 44, Y - 4, 11, 8, "Ціль крену", ["−29° (вхід", "у GUIDED)"], title_size=15, line_size=13)
d.box(dax, 58, Y - 4, 13, 8, "RLL2SRV_TCONST", ["0,45 с → ціль", "швидкості ≤ 75°/с"], title_size=14, line_size=13)
d.box(dax, 74, Y - 4, 12, 8, "Σ → елерони", ["−74%", "(насичення)"], title_size=15, line_size=13,
      ec=d.C["power"])
d.box(dax, 89, Y - 4, 10.5, 8, "Літак", ["−124°/с", "при цілі −29°/с"], title_size=15, line_size=13)
for x0, x1 in ((55, 58), (71, 74), (86, 89)):
    d.wire(dax, [(x0, Y), (x1, Y)], "uart", arrow="end")
# gain terms feeding the sum
terms = [(58, "FF 0,57", "→ −74% елеронів", d.C["power"]), (70, "P 0,12", "× похибка", d.MUTED),
         (82, "I 0,02", "інтегратор", d.MUTED)]
for x, k, sub, col in terms:
    d.box(dax, x - 5.5, 18, 11, 7.5, k, [sub], title_size=16, line_size=12, ec=col, title_color=col)
    d.wire(dax, [(x, 25.5), (x, 27.5), (80, 27.5), (80, Y - 4)], "uart")
d.wire(dax, [(94, Y - 4), (94, 15), (49.5, 15), (49.5, Y - 4)], "uart", arrow="end")
d.note(dax, 72, 14.4, "зворотний зв'язок: крен −45°, коливання 9 разів за 6 с", size=13, color=d.C["uart"],
       ha="center", va="top")
d.box(dax, 44, 1, 55.5, 9.5, None)
d.table(dax, 45, 9.4, [0, 14, 28, 42], [
    ["дані: ATT, PIDR", "момент: 56,8 с", "період ≈ 1,25 с", "загасання 0,67–0,73"],
    ["EKF XKF4 ≤ 0,4", "HDOP 1,21", "Clip 0", "Starlink: 2–3 зміни"]], size=13.5, row_h=3.6, header=False)
d.note(dax, 44, 39.5, "Контур швидкості крену (ArduPlane)", size=17, color=d.INK, va="bottom", bold=True)
d.note(dax, 44, 41.4, "гіпотеза: FF завеликий, P та I замалі", size=14, color=d.C["power"], va="bottom")
d.save(fig, "deck_v2/s10_log.png")
