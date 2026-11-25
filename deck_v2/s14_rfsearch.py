"""Slide (new, after the SITL mission): RFSEARCH, the flight mode that circles while the companion hears the source,
and how well the companion's fixes matched the hidden sources in SITL.

Sources: src/ardupilot/ArduPlane/rf_search.{h,cpp} (RFS_ parameters and defaults), compare/rf_companion.py
(synthetic helix 15 dBi / 30 deg tilted 10 deg down, 47 dBm sources, 30 dB/decade, 1.5 dB fading, -110 dBm floor),
compare/rfsearch/circle_runs.json (circle sweeps, THR -90, STOP_DB 5: 30 flights, 2 routes x 5 layouts x 6 seeds),
compare/rfsearch/variants.md (the same 4 multi-source flights for each sweep variant), the map flight
compare/results/mission-20261124-214358-i1 (ellipse route, multi_b, seed 11).
"""
import csv
import json
import math

import diag as d

d.H = 46.7                      # one-line title at 28 pt
fig, ax = d.canvas()
ROOT = "/home/tomcat/cert-env/"
RUNS = json.load(open(ROOT + "compare/rfsearch/circle_runs.json"))
S = RUNS["summary"]
MAP_RUN = ROOT + "compare/results/mission-20261124-214358-i1/believer-5kg-avl-at"
SRC_COL = ["#6CB4FF", "#F0A640", "#B48CFF", "#3FD0C0"]

# --- left: what the mode does -------------------------------------------------------------------
d.box(ax, 0.5, 0.5, 31, 45.7, None, ec=d.LINE)
d.note(ax, 1.5, 45.2, "RFSEARCH = AUTO + коло", size=18, color=d.INK, va="top", bold=True)
d.note(ax, 1.5, 42.3, "новий режим ArduPlane (№ 27, локальний патч)", size=12.5, va="top")
steps = [
    ("1", "летить місію, як AUTO", ["зліт, посадка, failsafe, geofence: без змін"]),
    ("2", "RF_dBm ≥ −90 dBm → коло 360°", ["вправо, крен 30°, ≈ 23 с;", "останні 90° — вихід на курс до WP"]),
    ("3", "далі коло кожні 3 км", ["поки пік кола ≥ −95 dBm (гістерезис 5 дБ),", "що б не чула антена на прямій"]),
    ("4", "без кіл", ["на зльоті, посадці, у failsafe,", "ближче 500 м до WP"]),
]
y = 38.6
for num, head, lines in steps:
    ax.add_patch(d.FancyBboxPatch((1.5, y - 1.9), 2.2, 2.2, boxstyle="round,pad=0,rounding_size=0.5",
                                  fc=d.GOOD, ec="none", zorder=2))
    d.note(ax, 2.6, y - 0.8, num, size=14, color="#121C17", ha="center", va="center", bold=True)
    d.note(ax, 4.6, y + 0.2, head, size=14.5, color=d.INK, va="top", bold=True)
    for j, ln in enumerate(lines):
        d.note(ax, 4.6, y - 2.0 - j * 1.75, ln, size=12.5, va="top")
    y -= 3.4 + 1.75 * len(lines)

# the circle on the track: track arrow, circle to the right, back onto the course
cx, cy, r = 7.0, 6.2, 3.0
ax.plot([1.8, 15.0], [cy + r, cy + r], color=d.MUTED, lw=2.4, zorder=2)
ax.add_patch(d.FancyArrowPatch((13.6, cy + r), (15.4, cy + r), arrowstyle="-|>", mutation_scale=20,
                               color=d.MUTED, lw=0, zorder=2))
th = [math.radians(90 - k * 3) for k in range(121)]
ax.plot([cx + r * math.cos(t) for t in th], [cy + r * math.sin(t) for t in th], color=d.GOOD, lw=2.6, zorder=3)
d.note(ax, cx, cy, "360°\n23 с", size=12.5, color=d.GOOD, ha="center", va="center", bold=True)
d.note(ax, 1.8, cy + r + 0.6, "курс до WP", size=11.5)
d.note(ax, cx + r + 0.6, cy - 0.6, "крен 30°\nвправо", size=11.5, va="top")

d.table(ax, 15.6, 12.8, [0, 7.5], [
    ("RFS_TYPE", "2 (вправо)"),
    ("RFS_THR_DBM", "−90"),
    ("RFS_STOP_DB", "5"),
    ("RFS_SPACING", "3000 м"),
    ("RFS_MIN_LEG", "500 м"),
], size=11.5, row_h=1.85, header=False, colors=[d.INK] * 5)
d.note(ax, 1.5, 1.2, "MAVLink: RF_dBm 5 Гц → FC;  RFS_SWP (фаза кола) → Pi", size=11.5, color=d.C["uart"],
       bold=True)

# --- middle: one flight on the map --------------------------------------------------------------
X0, Y0, MW, MH = 32.5, 0.5, 33.5, 45.7
d.box(ax, X0, Y0, MW, MH, None, ec=d.LINE)
d.note(ax, X0 + 1, Y0 + MH - 0.5, "Один політ у SITL", size=18, color=d.INK, va="top", bold=True)
res = json.load(open(MAP_RUN + "/rf_result.json"))
n_circles = next(r["sweeps"] for r in RUNS["runs"] if MAP_RUN.endswith(r["run"]))
d.note(ax, X0 + 1, Y0 + MH - 3.4, f"еліпс 79 км, 3 приховані джерела, {n_circles} кіл", size=12.5, va="top")
trk = [(float(r["lat"]), float(r["lon"])) for r in csv.DictReader(open(MAP_RUN + "/track.csv"))
       if abs(float(r["lat"])) > 1]
lat0, lon0 = trk[0]
k = math.cos(math.radians(lat0))


def km(la, lo):
    return (lo - lon0) * 111.195 * k, (la - lat0) * 111.195


pts = [km(*p) for p in trk]
xs, ys = zip(*pts)
x_lo, x_hi, y_lo, y_hi = min(xs) - 1.5, max(xs) + 1.5, min(ys) - 1.5, max(ys) + 1.5
sc = min((MW - 2) / (x_hi - x_lo), (MH - 7.5) / (y_hi - y_lo))
ox = X0 + 1 + (MW - 2 - sc * (x_hi - x_lo)) / 2
oy = Y0 + 3 + (MH - 9.5 - sc * (y_hi - y_lo)) / 2


def P(x, y):
    return ox + (x - x_lo) * sc, oy + (y - y_lo) * sc


for b in res["bearings"]:
    x, y = km(*b["pos"])
    L = 12.0
    x1, y1 = x + L * math.sin(math.radians(b["bearing"])), y + L * math.cos(math.radians(b["bearing"]))
    # clip the ray to the map box
    for f in (1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3):
        xe, ye = x + (x1 - x) * f, y + (y1 - y) * f
        if x_lo <= xe <= x_hi and y_lo <= ye <= y_hi:
            break
    col = SRC_COL[(b.get("source", 1) - 1) % 4] if b.get("source") else d.MUTED
    ax.plot(*zip(P(x, y), P(xe, ye)), color=col, lw=1.0, alpha=0.55, zorder=2)
ax.plot(*zip(*[P(*p) for p in pts]), color=d.INK, lw=1.3, alpha=0.8, zorder=3)
hx, hy = P(0, 0)
ax.plot(hx, hy, marker="^", color=d.GOOD, ms=11, zorder=4)
d.note(ax, hx + 0.8, hy - 0.3, "Цунів", size=11.5, color=d.GOOD, va="top")
for f in res["fixes"]:
    tx, ty = P(*km(*res["truth"][f["truth_index"] - 1][:2]))
    fx, fy = P(*km(*f["pos"]))
    ax.plot(tx, ty, marker="x", color=d.INK, ms=13, mew=2.6, zorder=5)
    ax.plot(fx, fy, marker="o", mfc="none", mec=d.C["power"], ms=15, mew=2.2, zorder=5)
    d.note(ax, tx + 1.0, ty + 0.5, f"{f['error_m']:.0f} м", size=13, color=d.INK, bold=True)
lx, ly = X0 + 1, Y0 + 1.2
ax.plot(lx + 0.6, ly + 0.5, marker="x", color=d.INK, ms=10, mew=2.2)
d.note(ax, lx + 1.6, ly, "джерело", size=11.5)
ax.plot(lx + 9.0, ly + 0.5, marker="o", mfc="none", mec=d.C["power"], ms=11, mew=2)
d.note(ax, lx + 10.0, ly, "оцінка", size=11.5)
ax.plot([lx + 16.4, lx + 18.6], [ly + 0.5, ly + 0.5], color=SRC_COL[0], lw=2)
d.note(ax, lx + 19.2, ly, "пеленги з кіл", size=11.5)

# --- right: companion and results ---------------------------------------------------------------
RX = 67.0
d.box(ax, RX, 23.6, 32.5, 22.6, None, ec=d.LINE)
d.note(ax, RX + 1, 45.7, f"{S['flights']} польотів: знайдено {S['found']} з {S['sources']}", size=18,
       color=d.GOOD, va="top", bold=True)
d.note(ax, RX + 1, 42.6, "2 маршрути × 5 розкладок × 6 seed, без хибних джерел" if S["extra"] == 0 else
       f"2 маршрути × 5 розкладок × 6 seed, хибних: {S['extra']}", size=12.5, va="top")
big = [(f"{S['median_m']} м", "медіана похибки"), (f"{S['p90_m']} м", "у 90% оцінок"),
       (f"{S['max_m']} м", "найгірша")]
for i, (v, lab) in enumerate(big):
    x = RX + 1 + i * 10.6
    d.note(ax, x, 36.2, v, size=26, color=d.INK, bold=True)
    d.note(ax, x, 35.4, lab, size=12, va="top")
d.note(ax, RX + 1, 31.4, "Pi Zero (компаньйон) на кожному колі:", size=13, color=d.INK, va="top", bold=True)
for j, ln in enumerate(["пеленги: підгонка діаграми спіралі 30° (кілька піків)",
                        "кількість джерел: BIC по всіх сирих вимірах",
                        "еліпси похибки 1σ → QGC (DEBUG_FLOAT_ARRAY)"]):
    d.note(ax, RX + 1, 29.0 - j * 1.9, ln, size=12.5, va="top")

d.box(ax, RX, 0.5, 32.5, 22.3, None, ec=d.LINE)
d.note(ax, RX + 1, 22.2, "Як обрано розворот", size=16, color=d.INK, va="top", bold=True)
d.note(ax, RX + 1, 19.9, "ті самі 4 польоти, 3 джерела в кожному", size=12, va="top")
V = json.load(open(ROOT + "compare/rfsearch/variants.json"))
rows = [("розворот", "кола, с", "пропущ.", "медіана")]
cols = []
for v in V:
    rows.append((v["label"], f"{v['sweep_s']}", f"{v['missed']} з 12", f"{v['median_m']:.0f} м"))
    cols.append(d.GOOD if v.get("chosen") else (d.C["power"] if v["missed"] else None))
d.table(ax, RX + 1, 17.6, [0, 15.4, 20.6, 26.2], rows, size=12, row_h=2.3, colors=[None] + cols)
d.note(ax, RX + 1, 1.0, "у польоті не перевірено: пауза пошуку після згасання сигналу", size=11.5, va="bottom")
d.save(fig, "deck_v2/s14_rfsearch.png")
