"""Summary of the RFSEARCH circle-sweep flights (RFS_TYPE 2, RFS_THR_DBM -90, RFS_STOP_DB 5) for the report and
the deck: per flight the sweeps, flight time, fix errors against the hidden sources and missed sources.
usage: python compare/rfsearch/summarise.py LOG... > compare/rfsearch/circle_runs.json
LOG is a mission.py console log; its results dir is read from the log."""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
runs = []
for log in sys.argv[1:]:
    text = Path(log).read_text()
    m = re.search(r"(compare/results/\S+?/believer-5kg-avl-at)", text)
    res = json.loads((ROOT / m.group(1) / "rf_result.json").read_text())
    tag = Path(log).stem.removeprefix("hyst_")
    plan, scen, seed = re.match(r"([EU])_(multi_b|multi|single)_s(\d+)", tag).groups()
    sweeps = len(re.findall(r"text: RFS: sweep \d+, course", text))
    dis = re.findall(r"t=\s*([\d.]+)\s+DISARMED", text)
    errs = [f["error_m"] for f in res["fixes"] if f.get("error_m") is not None]
    matched = {f.get("truth_index") for f in res["fixes"] if f.get("truth_index")}
    runs.append(dict(run=m.group(1), plan="ellipse" if plan == "E" else "user", scenario=scen, seed=int(seed),
                     sweeps=sweeps, flight_s=float(dis[-1]) if dis else None, fixes=len(res["fixes"]),
                     sources=len(res["truth"]), errors_m=[round(e) for e in errs],
                     missed=len(res["truth"]) - len(matched), extra=len(res["fixes"]) - len(matched)))
errs = sorted(e for r in runs for e in r["errors_m"])
summary = dict(flights=len(runs), sources=sum(r["sources"] for r in runs),
               found=sum(r["sources"] - r["missed"] for r in runs), extra=sum(r["extra"] for r in runs),
               median_m=errs[len(errs) // 2], p90_m=errs[int(0.9 * len(errs))], max_m=errs[-1],
               within_100=sum(e <= 100 for e in errs), errors=len(errs))
json.dump(dict(summary=summary, runs=runs), sys.stdout, indent=1, ensure_ascii=False)
print()
