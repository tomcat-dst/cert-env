"""Slide (conclusions): done -> improve -> next, plus the skills used (from the project's work).

Numbers: RFSEARCH 78 of 78 sources / median 48 m from compare/rfsearch/circle_runs.json (30 flights); the two QGC
flights of 2026-11-25 (47-67 m and 73-434 m, 2.4 km ellipse) from deck_v2/s15_scenarios.py; RC loss 1 h 15 min and
touchdown 0.56 m/s from the 23.11 long mission; checklist 80.65 % (25 of 31)."""
import diag as d

d.H = 46.7                      # one-line title at 28 pt
fig, ax = d.canvas()
cols = [
    ("Виконано", d.GOOD, ["модель Believer у SITL: мотор, гвинт,", "батарея, катапульта, AVL",
                             "3 виправлення SITL (патч до 4.7.3)", "AUTOTUNE: перерегулювання 16° → 2°",
                             "режим RFSEARCH: 78 з 78 джерел", "у 30 польотах, медіана 48 м",
                             "автономність: 1 год 15 хв без RC,", "автопосадка 0,56 м/с",
                             "логи, звіт, чекліст 80,65%"]),
    ("Покращити", d.C["power"], ["обміряти хвіст, елерони, центр мас", "→ уточнити модель AVL",
                                 "лонжерон: тест 1,5–2× навантаження", "GNSS L1 + L5 проти завад",
                                 "джерела на одній лінії з маршрутом", "зливаються: еліпс до 2,4 км",
                                 "пауза пошуку після згасання", "сигналу не перевірена в польоті"]),
    ("Далі", d.C["uart"], ["польоти з tinySA: справжній спектр", "замість синтетичного",
                           "маршрут, що сам добирає пеленги", "з іншого боку від джерела",
                           "рельєф і відбиття в моделі каналу", "Lua: газ 100% → 75% після зльоту",
                           "реальний політ + AUTOTUNE"]),
]
w = 31.5
h = max(d.fit_h(t, items, 21, 15.5) for t, _, items in cols)
TOP = d.H - 0.5
for i, (t, col, items) in enumerate(cols):
    x = 0.5 + i * (w + 2.25)
    d.box(ax, x, TOP - h, w, h, t, items, title_size=21, line_size=15.5, ec=col, title_color=col, lw=2.2)
    if i < 2:
        d.wire(ax, [(x + w, TOP - h / 2), (x + w + 2.25, TOP - h / 2)], "uart", arrow="end")
top = TOP - h - 1.5
d.box(ax, 0.5, 0.5, 99, top - 0.5, "Навички", title_size=20)
d.table(ax, 1.8, top - 5.4, [0, 50], [
    ["ArduPilot SITL і C++: патч симулятора", "новий режим польоту в ArduPlane (C++)"],
    ["аналіз логів .BIN (pymavlink)", "QGC: місії, параметри, власна збірка з картою пеленгів"],
    ["ArduPlane: TECS, failsafe, посадка", "AUTOTUNE і перевірка до/після; AVL, енергобюджет"]], size=17.5,
    row_h=5.9, header=False)
d.save(fig, "deck_v2/s13_next.png")
