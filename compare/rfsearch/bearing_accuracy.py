"""How bearing accuracy depends on signal level: every stored bearing against the direction to the nearest true
source, normalised by its own sigma, binned by peak dBm. If stronger bearings are more accurate than their sigma
says, a dB term belongs in the weight.
usage: python compare/rfsearch/bearing_accuracy.py RESULTS_DIR..."""
import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import rf_companion as rc  # noqa: E402

rows = []
for d in sys.argv[1:]:
    p = Path(d) / "rf_result.json"
    if not p.exists():
        continue
    r = json.loads(p.read_text())
    if len(r.get("truth", [])) < 2 or "bearings" not in r:
        continue
    for b in r["bearings"]:
        errs = []
        for t in r["truth"]:
            n, e = rc.ned(b["pos"], t[:2])
            errs.append((abs(((math.degrees(math.atan2(e, n)) - b["bearing"] + 180) % 360) - 180), math.hypot(n, e)))
        err, dist = min(errs)
        rows.append((b["dbm"], b["sigma"], err, dist))
a = np.array(rows)
print(f"{len(a)} bearings from {len(sys.argv) - 1} flights")
print(f"{'dBm':>11} {'n':>4} {'median err deg':>15} {'median sigma':>13} {'rms err/sigma':>14} {'median dist km':>15}")
for lo, hi in ((-200, -85), (-85, -80), (-80, -76), (-76, -72), (-72, -68), (-68, -60), (-60, 0)):
    m = (a[:, 0] >= lo) & (a[:, 0] < hi)
    if m.sum() < 5:
        continue
    z = a[m, 2] / a[m, 1]
    print(f"{lo:>5}..{hi:<5} {m.sum():>4} {np.median(a[m, 2]):>15.2f} {np.median(a[m, 1]):>13.2f} "
          f"{math.sqrt(np.mean(np.minimum(z, 10) ** 2)):>14.2f} {np.median(a[m, 3]) / 1000:>15.1f}")
