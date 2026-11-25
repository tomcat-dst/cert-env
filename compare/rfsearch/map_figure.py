"""Report figure: several RFSEARCH flights side by side (track, bearings from the circles, hidden sources, fixes
with 1-sigma ellipses), Ukrainian labels.
usage: python compare/rfsearch/map_figure.py out.png label=results_dir ..."""
import sys, json, csv, math
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams['font.family'] = ['Noto Sans', 'DejaVu Sans']
from matplotlib.patches import Ellipse

out, runs = sys.argv[1], [a.split('=', 1) for a in sys.argv[2:]]
n = len(runs)
cols = 3 if n > 4 else n
rows = math.ceil(n / cols)
fig, axes = plt.subplots(rows, cols, figsize=(6.2 * cols, 4.8 * rows), squeeze=False)
for ax in axes.flat[n:]:
    ax.axis('off')
for ax, (label, d) in zip(axes.flat, runs):
    res = json.load(open(f'{d}/rf_result.json'))
    trk = [(float(r['lat']), float(r['lon'])) for r in csv.DictReader(open(f'{d}/track.csv'))
           if abs(float(r['lat'])) > 1]
    lat0, lon0 = trk[0]
    k = math.cos(math.radians(lat0))
    xy = lambda la, lo: ((lo - lon0) * 111.195 * k, (la - lat0) * 111.195)
    ax.plot(*zip(*[xy(*p) for p in trk]), color='0.45', lw=1, label="трек")
    for b in res['bearings']:
        x, y = xy(*b['pos'])
        L = 14
        ax.plot([x, x + L * math.sin(math.radians(b['bearing']))], [y, y + L * math.cos(math.radians(b['bearing']))],
                color='tab:orange', lw=0.6, alpha=0.35, label='пеленги' if b is res['bearings'][0] else None)
    for i, t in enumerate(res['truth'], 1):
        ax.plot(*xy(t[0], t[1]), 'kx', ms=11, mew=2.5, label='джерело' if i == 1 else None)
    errs = []
    for f in res['fixes']:
        x, y = xy(*f['pos'])
        a, bm, ang = f.get('ellipse_m_deg', [f['sigma_m']] * 2 + [0])
        ax.add_patch(Ellipse((x, y), 2 * a / 1000, 2 * bm / 1000, angle=90 - ang, fill=False, color='tab:blue', lw=1.5))
        ax.plot(x, y, 'o', color='tab:blue', ms=5, label='оцінка (1σ)' if not errs else None)
        errs.append(f.get('error_m'))
    missed = len(res['truth']) - sum(e is not None for e in errs) if res['truth'] else 0
    etxt = ' / '.join(f'{e:.0f}' for e in errs if e is not None)
    ax.set_title(f'{label}\nоцінок {len(res["fixes"])}, похибки {etxt} м, пропущено {max(missed, 0)}', fontsize=10)
    ax.plot(0, 0, 'g^', ms=9, label='дім')
    xs = [xy(*p)[0] for p in trk] + [xy(t[0], t[1])[0] for t in res['truth']]
    ys = [xy(*p)[1] for p in trk] + [xy(t[0], t[1])[1] for t in res['truth']]
    ax.set_xlim(min(xs) - 2, max(xs) + 2)
    ax.set_ylim(min(ys) - 2, max(ys) + 2)
    ax.set_aspect('equal')
    ax.grid(alpha=0.3)
    ax.set_xlabel('схід, км')
    ax.set_ylabel('північ, км')
    ax.legend(fontsize=7, loc='lower left')
fig.tight_layout()
fig.savefig(out, dpi=110, bbox_inches="tight")
print(out)
