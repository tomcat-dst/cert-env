"""Side-by-side summary of two replay_progressive.py outputs.
usage: python compare/rfsearch/compare_replays.py replay_v1.json replay_v2.json"""
import json
import sys

a, b = (json.load(open(f)) for f in sys.argv[1:3])
print(f"{'flight':48} {'final errors, m (v1 -> v2)':34} {'grew':>9} {'jumps':>9} {'in 2sig':>13}")
tot = {k: [0, 0] for k in ("grew", "jumps", "inside", "updates", "late_inside", "late")}
fe = [[], []]
for x, y in zip(a, b):
    assert x["run"] == y["run"]
    name = x["run"].split("results/")[-1].split("/")[0]
    print(f"{name:48} {str(x['final']):>16} -> {str(y['final']):16} {x['grew']:>4}->{y['grew']:<4} "
          f"{x['jumps']:>4}->{y['jumps']:<4} {x['inside']:>3}/{x['updates']:<3}->{y['inside']:>3}/{y['updates']:<3}")
    for i, r in enumerate((x, y)):
        for k in ("grew", "jumps", "inside", "updates", "late_inside"):
            tot[k][i] += r[k]
        tot["late"][i] += len(r["late_err"])
        fe[i] += [e for e in r["final"] if e is not None]
med = lambda v: sorted(v)[len(v) // 2]
for i, tag in enumerate(("v1", "v2")):
    print(f"{tag}: final median {med(fe[i])} m, worst {max(fe[i])} m, >200 m: {sum(e > 200 for e in fe[i])}/{len(fe[i])}; "
          f"ellipse grew {tot['grew'][i]}, jumps {tot['jumps'][i]}, truth in 2-sigma {tot['inside'][i]}/{tot['updates'][i]} "
          f"({100 * tot['inside'][i] / tot['updates'][i]:.0f}%), last 5 updates {tot['late_inside'][i]}/{tot['late'][i]}")
