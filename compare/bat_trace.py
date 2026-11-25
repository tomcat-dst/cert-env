"""Battery current from a dataflash log (BAT, ~10 Hz), timed from the catapult push (first IMU AccX > 15).

Usage: bat_trace.py RUN_DIR [MINUTES]  -> RUN_DIR/bat_trace.csv with t_min, amps, alt
"""
import csv
import sys
from pathlib import Path

from pymavlink import mavutil

run = Path(sys.argv[1])
span = float(sys.argv[2]) * 60 if len(sys.argv) > 2 else 660
m = mavutil.mavlink_connection(str(run / "logs/00000001.BIN"))
tl, alt, rows = None, 0.0, []
while True:
    msg = m.recv_match(type=["IMU", "BAT", "POS"])
    if msg is None:
        break
    t = msg.TimeUS / 1e6
    if tl is None:
        if msg.get_type() == "IMU" and msg.I == 0 and msg.AccX > 15:
            tl = t
        continue
    if t - tl > span:
        break
    if msg.get_type() == "POS":
        alt = msg.RelHomeAlt
    elif msg.get_type() == "BAT" and msg.Inst == 0:
        rows.append(dict(t_min=round((t - tl) / 60, 4), amps=round(msg.Curr, 2), alt=round(alt, 1)))
with open(run / "bat_trace.csv", "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=["t_min", "amps", "alt"])
    w.writeheader()
    w.writerows(rows)
print(run / "bat_trace.csv", len(rows), "rows, peak", max(r["amps"] for r in rows), "A")
