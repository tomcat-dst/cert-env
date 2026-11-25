"""Slide 2 (avionics): wiring of the H743-WING V3 in the left two thirds, ArduPilot / PX4 / iNav in the
right third (design, the aircraft exists only in SITL).

Wiring sources: UART order and defaults from libraries/AP_HAL_ChibiOS/hwdef/MatekH743/hwdef.dat
(SERIAL1 = UART7 telem1, SERIAL3 = USART2 GPS1, SERIAL7 = USART6 RC input; 7 UARTs, 2 I2C, CAN1);
outputs from MFE's Believer_V4.6.3.param (SERVO1/5 = 4 aileron, SERVO2 = 79 / SERVO4 = 80 V-tail,
SERVO3/6 = 70 throttle); Pi Zero 2 W UART pins from the standard 40-pin header.
Comparison sources: ArduPlane Parameters.cpp (FS_LONG_ACTN), PX4 safety docs (COM_RCL_EXCEPT),
iNav docs/Settings.md (failsafe_mission_delay -1), docs/Telemetry.md (MAVLink transmit-only),
docs/SITL/SITL.md (RealFlight / X-Plane, under development).
"""
import diag as d

d.H = 46.7                      # one-line title at 28 pt
fig, ax = d.canvas()
T, L, WL = 15, 12.5, 11.5       # box title, box line, wire label sizes
TOP = 46.2

# left column: sensors and RC
PAD = dict(size=10, color=d.MUTED, ha="center", va="top")
d.box(ax, 0.5, TOP - 6.6, 13, None, "Matek M10Q-5883", ["u-blox M10, UBX", "+ компас (I2C)"], title_size=T, line_size=L)
d.box(ax, 0.5, TOP - 13.1, 13, None, "ASPD-DLVR", ["трубка Піто"], title_size=T, line_size=L)
d.box(ax, 0.5, TOP - 21.2, 13, None, "ELRS RX4 · 433", ["LR1121, пульт TX4", "~5 км, далі без RC"],
      title_size=T, line_size=L)
d.wire(ax, [(13.5, TOP - 2.0), (22.5, TOP - 2.0)], "uart", "SERIAL3 · GPS", size=WL)
d.note(ax, 18, TOP - 2.4, "TX2 / RX2", **PAD)
d.wire(ax, [(13.5, TOP - 5.6), (22.5, TOP - 5.6)], "i2c", "I2C · компас", size=WL)
d.note(ax, 18, TOP - 6.0, "SDA / SCL", **PAD)
d.wire(ax, [(13.5, TOP - 10.6), (22.5, TOP - 10.6)], "i2c", "I2C · ARSPD 9", size=WL)
d.note(ax, 18, TOP - 11.0, "SDA / SCL", **PAD)
d.wire(ax, [(13.5, TOP - 18.4), (22.5, TOP - 18.4)], "rc", "SERIAL7 · CRSF", size=WL)
d.note(ax, 18, TOP - 18.8, "RX6 / TX6", **PAD)

# flight controller with its own PDB and current sensor; parameters for this wiring at the bottom
fc_lines = ["STM32H743, 480 МГц", "ICM-42688-P + ICM-42605", "7 UART · 2 I2C · CAN", "ArduPlane 4.7.3 · EKF3 · TECS",
            "PDB, датчик струму 132 А", "BEC серворейки 6 В", "логи .BIN на microSD"]
d.box(ax, 22.5, 20.5, 18.5, TOP - 20.5, "Matek H743-WING V3", fc_lines, title_size=17, line_size=L)
for j, ln in enumerate(["SERIAL1_PROTOCOL 2 · BAUD 460", "SERIAL3_PROTOCOL 5", "SERIAL7_PROTOCOL 23",
                        "ARSPD_TYPE 9 · BATT_MONITOR 4"]):
    d.note(ax, 23.3, 27.2 - j * 1.55, ln, size=10.5, color=d.C["uart"], va="top")

# power: battery -> board PDB (VBAT, current), ESCs and the BEC12S-PRO for the payload
d.box(ax, 0.5, 1, 13, None, "6S4P Molicel P50B", ["25,2 В · 20 А·год", "444 Вт·год"], ec=d.C["power"],
      title_size=T, line_size=L)
d.wire(ax, [(13.5, 2.8), (48, 2.8)], "power")
d.wire(ax, [(18, 2.8), (18, 22.0), (22.5, 22.0)], "power")
d.note(ax, 17.4, 13.5, "VBAT · CURR\nАЦП 66,7 А/В", size=WL, color=d.C["power"], ha="right", va="center")
d.wire(ax, [(43.0, 2.8), (43.0, 8.6)], "power")
d.note(ax, 43.6, 6.0, "6S", size=10.5, color=d.C["power"], va="center", bold=True)

# outputs on the 6 V servo rail, ESCs and motors
outs = [(23.7, "елерони", "S1 · S5 = 4", "2× ES3054"), (32.7, "V-хвіст", "S2 · S4 = 79/80", "2× ES3054"),
        (41.7, "2× ESC 60 А", "S3 · S6 = 70", "пік 44 А (SITL)")]
for x, what, fn, dev in outs:
    d.box(ax, x - 4.1, 8.6, 8.2, None, what, [fn, dev], align="center", title_size=13.5, line_size=11.5,
          ec=d.C["pwm"])
d.wire(ax, [(23.7, 20.5), (23.7, 15.2)], "pwm")
d.wire(ax, [(32.7, 20.5), (32.7, 15.2)], "pwm")
d.wire(ax, [(39.5, 20.5), (39.5, 17.6), (41.7, 17.6), (41.7, 15.2)], "pwm")
d.note(ax, 28.2, 17.9, "PWM · 6 В", size=WL, color=d.C["pwm"], ha="center", va="center", bold=True)
d.box(ax, 48, 8.6, 16.5, 6.2, "2× X3120 585KV", ["APC 11×7E · 65 А / 30 с"], ec=d.C["power"],
      title_size=13.5, line_size=11.5)
d.wire(ax, [(45.8, 11.9), (48, 11.9)], "power")
d.box(ax, 48, 1.0, 16.5, 5.6, None, ec=d.C["power"])
d.note(ax, 48.8, 5.9, "BEC12S-PRO · 5 В", size=13, color=d.INK, va="center", bold=True)
d.note(ax, 48.8, 3.2, "5 А, пік 9 А · навантаження", size=11, va="center")

# companion, the OTG hub and every USB device on it; 5 V from the BEC
d.box(ax, 48, TOP - 6.6, 16.5, None, "Pi Zero 2 W", ["companion, Linux", "pin 8 TXD · 10 RXD · 6 GND"],
      title_size=T, line_size=L)
d.wire(ax, [(41, TOP - 3.5), (48, TOP - 3.5)], "uart", "SERIAL1", size=WL)
d.note(ax, 44.5, TOP - 3.9, "TX7 / RX7\nMAVLink 2\n460800\nTX↔RX", size=10, color=d.C["uart"], ha="center",
       va="top")
d.box(ax, 48, 34.6, 16.5, 4.3, None)
d.note(ax, 48.8, 37.9, "USB-хаб · OTG Pi", size=13.5, color=d.INK, va="center", bold=True)
d.note(ax, 48.8, 35.7, "≈2 А, пік 4,5 А на 5 В", size=10.5, va="center")
d.wire(ax, [(56.2, TOP - 6.6), (56.2, 38.9)], "usb")
usb_devs = [(28.0, "tinySA", ["аналізатор спектра", "USB-C · ≤150 г · до 1,3 А"]),
            (21.7, "Quectel EG25-G", ["LTE → QGC: MAVLink, відео", "або Starlink Mini (варіант)"]),
            (15.4, "UVC-камера", ["відео H.264", "USB, драйвер UVC у Linux"])]
for y0, t, ls in usb_devs:
    d.box(ax, 50.2, y0, 14.3, 5.9, t, ls, title_size=12.5, line_size=10.5)
    d.wire(ax, [(49.1, y0 + 4.6), (50.2, y0 + 4.6)], "usb")
d.wire(ax, [(49.1, 34.6), (49.1, 15.4 + 4.6)], "usb")
d.wire(ax, [(64.5, 4.2), (65.4, 4.2), (65.4, TOP - 3.0), (64.5, TOP - 3.0)], "power")
d.wire(ax, [(65.4, 36.7), (64.5, 36.7)], "power")
d.note(ax, 65.0, 7.8, "5 В", size=10.5, color=d.C["power"], ha="right", va="center", bold=True)

# legend, in the free space of the left column
names = {"uart": "UART / MAVLink", "rc": "RC (CRSF)", "i2c": "I2C", "pwm": "PWM", "power": "живлення",
         "usb": "USB"}
for i, k in enumerate(names):
    yy = 23.4 - i * 1.6
    ax.plot([0.8, 3.0], [yy, yy], color=d.C[k], lw=3)
    d.note(ax, 3.6, yy, names[k], size=11, va="center")

# --- comparison, right third ---
X0, XW = 66.5, 33.0
d.box(ax, X0, 1, XW, TOP - 1, None)
d.note(ax, X0 + 1, TOP - 0.9, "Чому ArduPilot", size=16, color=d.INK, va="top", bold=True)
cols = [X0 + 1, X0 + 11.6, X0 + 22.2]
for cx, name, col in zip(cols, ["ArduPilot", "PX4", "iNav"], [d.GOOD, d.INK, d.INK]):
    d.note(ax, cx, TOP - 4.0, name, size=13, color=col, va="top", bold=True)
rows = [
    ("політ по місії", ["так", "так", "так, FPV-фокус"]),
    ("місія після втрати RC", ["FS_LONG_ACTN 0", "COM_RCL_EXCEPT", "failsafe_mission\n_delay −1"]),
    ("компаньйон", ["MAVLink + Lua", "MAVLink, uORB,\nROS 2", "MAVLink лише\nна передачу"]),
    ("архітектура", ["простіша\nінтеграція", "модульна (uORB),\nскладніша", "проста,\nменше функцій"]),
    ("SITL", ["нативна модель,\nGazebo, JSON", "Gazebo", "X-Plane, RealFlight,\nу розробці"]),
    ("логи", [".BIN (DataFlash)", "ULog", "Blackbox"]),
]
y = TOP - 6.6
for label, vals in rows:
    d.note(ax, X0 + 1, y, label, size=11.5, color=d.MUTED, va="top", bold=True)
    y -= 1.7
    n = max(v.count("\n") + 1 for v in vals)
    for cx, v, col in zip(cols, vals, [d.INK, d.MUTED, d.MUTED]):
        for j, ln in enumerate(v.split("\n")):
            d.note(ax, cx, y - j * 1.5, ln, size=11.5, color=col, va="top")
    y -= n * 1.5 + 0.8
ax.plot([X0 + 1, X0 + XW - 1], [y + 0.3, y + 0.3], color=d.LINE, lw=1)
for j, ln in enumerate(["Обрано ArduPilot: місія без RC одним", "параметром, Lua і MAVLink для компаньйона,",
                        "нативний SITL, логи .BIN.", "PX4 підійшов би теж, але в нього",
                        "складніша архітектура."]):
    d.note(ax, X0 + 1, y - 0.6 - j * 1.6, ln, size=12, color=d.GOOD if j < 3 else d.MUTED, va="top")
d.save(fig, "deck_v2/s04_wiring.png")
