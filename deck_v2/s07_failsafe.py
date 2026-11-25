"""Slide (parked): custom ArduPilot parameters - catapult take-off, failsafe behaviour as states and
transitions with the parameters that set them, plus the RC-link / mode timeline of the long QGC mission
(deck_v2/mission_profiles.json, from compare/results/mission-20261123-165646).

Take-off from sim/params/believer.parm / believer_5kg.parm and compare/launch.md (3.3 g catapult, 100 % for
5 s, rotation hold 5 deg to 15 m/s then <= 8 deg; 0 of 18 SITL ground contacts). Failsafe from
sim/params/believer_mission.parm and believer_5kg.parm, ArduPlane/events.cpp (FS_*_ACTN 0 in AUTO takes no
action), defaults FS_SHORT_TIMEOUT 1.5 s / FS_LONG_TIMEOUT 5 s, FS_GCS_ENABL 0; tested: RC loss 60 s and
1 h 15 min (SITL, stays AUTO). Battery and fence failsafes are configured, not flight-tested.
"""
import json

from matplotlib.patches import FancyArrowPatch, Rectangle

import diag as d

d.H = 46.7                      # one-line title at 28 pt
fig, ax = d.canvas()
B = 17
OY = 5.2                        # the state diagram sits above the timeline strip


def arrow(pts, kind):
    pts = [(x, y + OY) for x, y in pts]
    xs, ys = zip(*pts)
    ax.plot(xs, ys, color=d.C[kind], lw=2.6, zorder=1)
    ax.add_patch(FancyArrowPatch(pts[-2], pts[-1], arrowstyle="-|>", mutation_scale=24, color=d.C[kind], lw=0,
                                 zorder=1))


def box(x, y, w, h, *a, **k):
    return d.box(ax, x, y + OY, w, h, *a, **k)


# states
box(28, 28.5, 24, 9, "AUTO · місія", ["пункти 1…28, RC не потрібен", "≈ 99 км, пошук на 900 м", "AIRSPEED_MIN 14 (у MFE 12)"], title_size=19,
    line_size=14,
    ec=d.C["uart"], lw=2.4)
box(28, 4, 24, 8.5, "RTL", ["RTL_ALTITUDE −1:", "додому на поточній висоті"], title_size=19, line_size=13.5)
box(70, 4, 29.5, 8.5, "Посадка", ["DO_LAND_START → NAV_LAND", "смуга 28, автодизарм після дотику"],
    title_size=19, line_size=13.5)

# catapult take-off into AUTO (sim/params/believer*.parm, compare/launch.md)
box(0.5, 28.2, 23.5, 12.8, "Зліт з катапульти 3,3 g", [
    "TKOFF_THR_DELAY 2: мотор за 0,2 с", "TKOFF_THR_MAX 100 · _T 5: 100% 5 с,", "пік 87–89 А, далі ≤ 75% (Lua)",
    "ROTATE_SPD 15 · GND_PITCH 5,", "LVL_PITCH 8: тангаж ≤ 8°", "SITL: 0 з 18 торкань землі"],
    title_size=15.5, line_size=12.5, ec=d.C["usb"])
arrow([(24, 34.6), (28, 34.6)], "usb")

# RC loss keeps AUTO
box(0.5, 17.7, 23.5, 9.7, "Втрата RC", ["> 1,5 с: FS_SHORT_ACTN 0", "> 5 с: FS_LONG_ACTN 0", "THR_FAILSAFE 1",
                                        "→ режим не змінюється"], title_size=15.5, line_size=12.5, ec=d.C["rc"])
arrow([(24, 22.6), (26, 22.6), (26, 30.2), (28, 30.2)], "rc")
box(0.5, 4, 23.5, 12.9, "Перевірено в SITL", ["RC 60 с на 5 км: AUTO", "RC 1 год 15 хв: AUTO",
                                               "«RC Long Failsafe On:", "switched to Auto»",
                                               "кінець місії → посадка:", "дотик 0,56 м/с"],
    title_size=15.5, line_size=12.5, ec=d.GOOD)

# AUTO -> RTL on battery or fence
arrow([(40, 28.5), (40, 12.5)], "power")
box(43, 17.5, 18, 8.5, "Батарея < 10%", ["BATT_LOW_MAH 2000", "(Starlink 25 А·год: 2500)", "BATT_FS_LOW_ACT 1"],
    title_size=15.5,
    line_size=13, ec=d.C["power"])
box(63, 17.5, 19, 8.5, "Вихід за geofence", ["коло 35 км + стеля", "FENCE_TYPE 5 · ACTION 1"], title_size=15.5,
    line_size=13, ec=d.C["i2c"])
arrow([(43, 21.7), (40.4, 21.7)], "power")
arrow([(72.5, 17.5), (72.5, 15.5), (40.4, 15.5)], "i2c")

# AUTO -> landing at the end of the mission, RTL -> landing
arrow([(52, 30.5), (86, 30.5), (86, 12.5)], "uart")
d.note(ax, 69, 31.1 + OY, "кінець місії: DO_LAND_START", size=13, color=d.C["uart"], ha="center", va="bottom",
       bold=True)
arrow([(52, 8.2), (70, 8.2)], "uart")
d.note(ax, 61, 9.0 + OY, "RTL_AUTOLAND 1", size=13, color=d.C["uart"], ha="center", va="bottom", bold=True)

# the other links and sensors
box(56, 33.3, 43.5, 7.7, "Інші канали й датчики", [
    "телеметрія LTE / Starlink: FS_GCS_ENABL 0 → без дії",
    "GPS: EKF failsafe в ArduPlane лише для VTOL (ekf_check.cpp);",
    "літак тримає курс за компасом, швидкість за трубкою Піто"], title_size=14.5, line_size=12)

# --- RC link and mode over the long QGC mission ---
p = json.load(open("deck_v2/mission_profiles.json"))
ev = {m: t for t, m in p["events"]}
T_END = [t for t, m in p["events"] if m.startswith("SIM Hit ground")][0]
t_lost, t_back = ev["RC Short Failsafe On"], ev["RC Long Failsafe Cleared"]
t_land = ev["Mission: 25 LandStart"]
d.box(ax, 0.5, 0.5, 99, 8.4, None)
X0, X1 = 15.0, 97.5


def tx(t):
    return X0 + (X1 - X0) * t / T_END


d.note(ax, 1.4, 7.6, "Місія з QGC, SITL", size=12.5, color=d.INK, va="center", bold=True)
d.note(ax, 1.4, 5.0, "RC-зв'язок", size=11.5, va="center")
d.note(ax, 1.4, 2.6, "режим", size=11.5, va="center")
for a, b, col, lab in ((0, t_lost, d.GOOD, "є"), (t_lost, t_back, d.C["rc"], "немає 1 год 15 хв (> 5 км)"),
                       (t_back, T_END, d.GOOD, "є")):
    ax.add_patch(Rectangle((tx(a), 4.3), tx(b) - tx(a), 1.4, fc=col, alpha=0.85 if lab != "є" else 0.6, ec="none",
                           zorder=3))
    if lab != "є":
        d.note(ax, (tx(a) + tx(b)) / 2, 5.0, lab, size=11, color="#0E1411", ha="center", va="center", bold=True)
ax.add_patch(Rectangle((tx(0), 1.9), tx(T_END) - tx(0), 1.4, fc=d.C["uart"], alpha=0.75, ec="none", zorder=3))
d.note(ax, (tx(0) + tx(t_land)) / 2, 2.6, "AUTO весь політ: «RC Long Failsafe On: switched to Auto»", size=11,
       color="#0E1411", ha="center", va="center", bold=True)
for t, lab in ((t_lost, "+1 с short, +5 с long"), (t_land, "DO_LAND_START"), (T_END, "дотик 0,56 м/с")):
    ax.plot([tx(t), tx(t)], [1.6, 6.3], color=d.INK, lw=1.2, zorder=4)
    d.note(ax, tx(t) + (0.3 if t == t_lost else -0.3), 7.0, lab, size=10.5, color=d.INK,
           ha="left" if t == t_lost else "right", va="center")
for m in range(0, int(T_END / 60) + 1, 10):
    d.note(ax, tx(m * 60), 0.85, f"{m}", size=9.5, ha="center", va="center")
d.note(ax, 1.4, 0.85, "хвилини від пострілу", size=9.5, va="center")
d.save(fig, "deck_v2/s07_failsafe.png")
