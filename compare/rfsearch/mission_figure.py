"""Report figure: a QGC plan and the flight flown from it (plan with item numbers, flown track, hidden sources;
below, altitude against distance flown), Ukrainian labels.
usage: python compare/rfsearch/mission_figure.py out.png PLAN RESULTS_DIR MISSION_LOG"""
import sys, json, csv, math, re
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams['font.family'] = ['Noto Sans', 'DejaVu Sans']

out, plan, d, log = sys.argv[1:5]
p = json.load(open(plan))['mission']
home = p['plannedHomePosition'][:2]
k = math.cos(math.radians(home[0]))
xy = lambda la, lo: ((lo - home[1]) * 111.195 * k, (la - home[0]) * 111.195)
text = open(log).read()
t0 = float(re.findall(r"t=\s*([\d.]+)\s+ARMED", text)[-1])
t1 = float(re.findall(r"t=\s*([\d.]+)\s+landed and disarmed", text)[-1])
rows = [r for r in csv.DictReader(open(f'{d}/rf_samples.csv'))
        if abs(float(r['lat'])) > 1 and t0 <= float(r['t']) <= t1]
trk = [xy(float(r['lat']), float(r['lon'])) for r in rows]
alt = [float(r['alt']) for r in rows]
dist = [0.0]
for a, b in zip(trk, trk[1:]):
    dist.append(dist[-1] + math.dist(a, b))
res = json.load(open(f'{d}/rf_result.json'))

fig, (ax, bx) = plt.subplots(1, 2, figsize=(11.5, 5.2), gridspec_kw=dict(width_ratios=[1, 1.15]))
ax.plot(*zip(*trk), color='0.45', lw=1, label='трек польоту (з колами)')
wps = [(i, it) for i, it in enumerate(p['items'], 1) if it['command'] in (16, 21, 22)]
ax.plot(*zip(*[xy(it['params'][4], it['params'][5]) for _, it in wps]), color='tab:blue', lw=1.2, ls='--', label='план')
for i, it in wps:
    x, y = xy(it['params'][4], it['params'][5])
    ax.plot(x, y, 'o', color='tab:blue', ms=4)
    if 3 <= i <= 14:
        ax.annotate(str(i), (x, y), textcoords='offset points', xytext=(5, 4), fontsize=8, color='tab:blue')
for n, t in enumerate(res['truth']):
    ax.plot(*xy(t[0], t[1]), 'kx', ms=10, mew=2.3, label='джерело (приховане)' if n == 0 else None)
ax.plot(0, 0, 'g^', ms=9, label='дім, Цунів')
ax.set_aspect('equal'); ax.grid(alpha=0.3)
ax.set_xlabel('схід, км'); ax.set_ylabel('північ, км')
ax.legend(fontsize=8, loc='center')
ax.set_title('План і трек', fontsize=10)
bx.plot(dist, alt, color='tab:blue', lw=1.4)
bx.set_xlabel('пройдена відстань, км'); bx.set_ylabel('висота над домом, м')
bx.grid(alpha=0.3); bx.set_xlim(0, dist[-1]); bx.set_ylim(0, 1000)
bx.set_title('Профіль висоти', fontsize=10)
fig.tight_layout()
fig.savefig(out, dpi=110, bbox_inches='tight')
print(out, round(dist[-1], 1), max(alt))
