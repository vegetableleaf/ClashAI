"""Did the clump the iteration-1 rule Rocketed ever hurt a tower in BASE?  python diag_threat.py DIR [ARM=rv9]
Per first fire: my princess-tower hp (sum of hp_frac) in BASE at the fire and 6/10/15 s later, in ARM likewise, and the outcome pair;
the pairs are split by how much tower hp BASE lost in the next 10 s (what the Rocket could have saved)."""
import glob, json, os, sys
from collections import defaultdict
import numpy as np

DIR, ARM = sys.argv[1], (sys.argv[2] if len(sys.argv) > 2 else 'rv9')


def load(arm, c):
    out = defaultdict(list)
    for f in glob.glob(f'{DIR}/fires_{arm}_{c}/bw_*.jsonl'):
        for line in open(f):
            d = json.loads(line)
            out[d['tag']].append(d)
    for v in out.values():
        v.sort(key=lambda d: d['t'])
    return out


def res(arm, c):
    return {r['tag']: {'win': 1.0, 'draw': 0.5}.get(r['outcome'], 0.0)
            for r in map(json.loads, open(f'{DIR}/{arm}_{c}/matches.jsonl')) if r.get('arm') == 'plain'}


def tow(d): return sum((t[3] or 0) for t in d['towers'] if t[0] == 0 and t[1] == 'princess')


def at(rows, t):
    prev = None
    for d in rows:
        if d['t'] <= t + 1e-6:
            prev = d
    return prev


R = []
for c in ('evo', 'lad'):
    FA, FB, A, B = load('base', c), load(ARM, c), res('base', c), res(ARM, c)
    for tag, rows in FB.items():
        f = next((d for d in rows if d['play'] and d['why'] == 'rocket_value'), None)
        if f is None:
            continue
        t0 = f['t']
        rec = dict(tag=tag, b=A[tag], a=B[tag], y=f['cell'][1])
        for name, rr in (('base', FA.get(tag, [])), ('arm', rows)):
            x0 = at(rr, t0)
            rec[name] = [tow(x0) if x0 else None] + [tow(at(rr, t0 + dt)) if at(rr, t0 + dt) else None for dt in (6, 10, 15)]
        R.append(rec)


def s(label, sel):
    b = sum(r['a'] > r['b'] for r in sel); w = sum(r['a'] < r['b'] for r in sel)
    print(f'{label}: n={len(sel)} better {b} worse {w} net {b - w} ({(b - w) / max(len(sel), 1):+.3f}/fire)')


ok = [r for r in R if None not in r['base'] and None not in r['arm']]
print(len(R), 'fires,', len(ok), 'with all boards')
for k, dt in ((1, 6), (2, 10), (3, 15)):
    lb = np.array([r['base'][0] - r['base'][k] for r in ok]); la = np.array([r['arm'][0] - r['arm'][k] for r in ok])
    print(f'tower hp lost (princess hp_frac sum) in the next {dt}s: base {lb.mean():.3f} arm {la.mean():.3f}; share of fires where base lost >= .05: {(lb >= .05).mean():.2f}')
loss = np.array([r['base'][0] - r['base'][2] for r in ok])
for lo, hi in ((-9, 0.005), (0.005, 0.05), (0.05, 0.15), (0.15, 9)):
    s(f'base tower loss in 10 s in [{lo},{hi})', [r for r, l in zip(ok, loss) if lo <= l < hi])
