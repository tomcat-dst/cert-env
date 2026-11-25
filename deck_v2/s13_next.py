"""Slide 13: done -> improve -> next, plus the skills used (from the project's work)."""
import diag as d

fig, ax = d.canvas()
cols = [
    ("Виконано", d.GOOD, ["модель Believer у SITL: мотор, гвинт,", "батарея, катапульта, AVL",
                             "3 виправлення SITL (патч до 4.7.3)", "AUTOTUNE: перерегулювання 16° → 2°",
                             "місія 1 год 23 хв, 101 км, без RC,", "автопосадка 0,56 м/с",
                             "логи, звіт, чекліст 80,65%"]),
    ("Покращити", d.C["power"], ["обміряти хвіст, елерони, центр мас", "→ уточнити модель AVL",
                                 "лонжерон: тест 1,5–2× навантаження", "GNSS L1 + L5 проти завад",
                                 "AIRSPEED_MIN 12 = 1,03 × звалювання", "реальний політ + AUTOTUNE"]),
    ("Далі", d.C["uart"], ["польоти з tinySA, запис спектра", "пеленг носовою патч-антеною:",
                           "коло в двох точках → тріангуляція", "телеметрія LTE / Starlink з втратами",
                           "підміна GPS: вплив на оцінку"]),
]
w = 31.5
h = max(d.fit_h(t, items, 23, 17.5) for t, _, items in cols)
for i, (t, col, items) in enumerate(cols):
    x = 0.5 + i * (w + 2.25)
    d.box(ax, x, 42 - h, w, h, t, items, title_size=23, line_size=17.5, ec=col, title_color=col, lw=2.2)
    if i < 2:
        d.wire(ax, [(x + w, 42 - h / 2), (x + w + 2.25, 42 - h / 2)], "uart", arrow="end")
top = 42 - h - 1.8
d.box(ax, 0.5, 1, 99, top - 1, "Навички", title_size=22)
d.table(ax, 1.8, top - 5.0, [0, 50], [
    ["ArduPilot SITL і C++: патч симулятора", "QGC: місії, geofence, параметри"],
    ["аналіз логів .BIN (pymavlink)", "AUTOTUNE і перевірка до/після"],
    ["ArduPlane: TECS, failsafe, посадка", "аеродинаміка в AVL, енергобюджет"]], size=19.5, row_h=4.6, header=False)
d.save(fig, "deck_v2/s13_next.png")
